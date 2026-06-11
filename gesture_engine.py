import os
import math
import time
import logging
import cv2
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage
import mediapipe as mp

log = logging.getLogger("VirtualMouse.GestureEngine")

# MediaPipe el landmark indeksleri
THUMB_TIP = 4
TIP_IDS = {"INDEX": 8, "MIDDLE": 12, "RING": 16, "PINKY": 20}

FINGER_TR = {"INDEX": "İşaret", "MIDDLE": "Orta", "RING": "Yüzük", "PINKY": "Serçe"}


class GestureEngine(QThread):
    """
    AirMouse V4 jest motoru.

    Mutlak konum + statik poz sistemi yerine pinch (çimdik) tabanlı,
    histerezisli durum makinesi kullanır:

      - Pinch-TAP  : Başparmak + bir parmak ucu kısa temas -> kısayol
      - Pinch-DRAG : Pinch'i tutup sürükleme:
          İşaret  -> sürekli scroll (joystick mantığı)
          Orta    -> yatay: Alt-Tab karuseli / dikey: tek seferlik swipe
          Yüzük   -> 4 yönlü tek seferlik swipe paleti
      - Yüz modu  : MediaPipe blendshape'leri (kaş, ağız, göz kırpma)
                    eşik + tutma süresi ile kısayollara bağlanır.
    """

    # GUI sinyalleri
    frame_ready = pyqtSignal(QImage, dict)
    status_message = pyqtSignal(str)
    fps_updated = pyqtSignal(float)

    # Jest olayları
    pinch_tap = pyqtSignal(str)        # INDEX / MIDDLE / RING / PINKY
    swipe_triggered = pyqtSignal(str)  # MIDDLE_UP, MIDDLE_DOWN, RING_LEFT, ...
    scroll_delta = pyqtSignal(int)     # ham mouse wheel deltası
    carousel_started = pyqtSignal()
    carousel_step = pyqtSignal(int)    # +1 ileri, -1 geri
    carousel_ended = pyqtSignal()
    mode_changed = pyqtSignal(str)     # overlay mod göstergesi metni ("" = kapalı)
    face_triggered = pyqtSignal(str)   # BROW_RAISE, JAW_OPEN, MOUTH_PUCKER, ...

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.running = True
        self.tracking_enabled = False
        self.face_enabled = config.get("face_mode_enabled", False)

        self.update_settings(config)

        # Pinch durum makinesi
        self.pinch_finger = None      # aktif pinch parmağı (None = yok)
        self.pinch_mode = "NONE"      # UNDECIDED / SCROLL / CAROUSEL / DONE
        self.pinch_anchor = None      # (x, y) px - pinch başlangıç noktası
        self.pinch_point = None       # (x, y) px - EMA ile yumuşatılmış güncel nokta
        self.pinch_start_t = 0.0
        self.carousel_last_x = 0.0
        self.last_scroll_emit = 0.0
        self.hand_seen_t = 0.0        # el ilk göründüğü an (stabilizasyon için)

        # Yüz ifadesi durum makinesi
        self.face_states = {}
        self.face_last_trigger_t = 0.0

    def update_settings(self, config):
        self.config = config
        self.camera_index = config.get("camera_index", 0)
        self.smoothing = config.get("smoothing_factor", 0.5)
        self.pinch_close_ratio = config.get("pinch_close_ratio", 0.40)
        # Histerezis: bırakma eşiği, basma eşiğinden belirgin şekilde geniş
        self.pinch_open_ratio = min(0.95, self.pinch_close_ratio * 1.5)
        self.tap_max_ms = config.get("tap_max_ms", 350)
        self.drag_threshold = config.get("drag_threshold_px", 40)
        self.scroll_speed = config.get("scroll_speed", 1.0)
        self.carousel_step_px = config.get("carousel_step_px", 70)
        self.face_threshold = config.get("face_threshold", 0.5)
        self.face_hold_ms = config.get("face_hold_ms", 250)

    # ------------------------------------------------------------------
    # Pinch durum makinesi
    # ------------------------------------------------------------------
    def process_hand(self, lms, w, h, frame, now):
        def d(a, b):
            return math.hypot(a.x - b.x, a.y - b.y)

        # El boyutuna normalizasyon: bilek (0) -> orta parmak MCP (9)
        hand_scale = d(lms[0], lms[9]) + 1e-6
        thumb = lms[THUMB_TIP]
        ratios = {f: d(thumb, lms[i]) / hand_scale for f, i in TIP_IDS.items()}

        def midpoint_px(finger):
            tip = lms[TIP_IDS[finger]]
            return ((thumb.x + tip.x) * 0.5 * w, (thumb.y + tip.y) * 0.5 * h)

        if self.pinch_finger is None:
            # Yeni pinch adayı: en küçük oranlı parmak
            finger = min(ratios, key=ratios.get)
            sorted_r = sorted(ratios.values())
            # Belirsizlik korumasi: ikinci parmak da kapaliysa (yumruk vb.) yok say
            unambiguous = sorted_r[1] > self.pinch_close_ratio * 1.25
            stabilized = (now - self.hand_seen_t) > 0.3
            if sorted_r[0] < self.pinch_close_ratio and unambiguous and stabilized:
                self.pinch_finger = finger
                mid = midpoint_px(finger)
                self.pinch_point = mid
                self.pinch_anchor = mid
                self.pinch_start_t = now
                self.pinch_mode = "UNDECIDED"
                log.info(f"Pinch started: {finger}")
        else:
            finger = self.pinch_finger
            ratio = ratios[finger]
            mid = midpoint_px(finger)
            a = self.smoothing
            self.pinch_point = (
                self.pinch_point[0] + (mid[0] - self.pinch_point[0]) * a,
                self.pinch_point[1] + (mid[1] - self.pinch_point[1]) * a,
            )
            dx = self.pinch_point[0] - self.pinch_anchor[0]
            dy = self.pinch_point[1] - self.pinch_anchor[1]

            if ratio > self.pinch_open_ratio:
                self.end_pinch(now)
            else:
                if self.pinch_mode == "UNDECIDED":
                    if math.hypot(dx, dy) > self.drag_threshold:
                        self.decide_drag_mode(finger, dx, dy)
                elif self.pinch_mode == "SCROLL":
                    self.do_scroll(dy, now)
                elif self.pinch_mode == "CAROUSEL":
                    self.do_carousel_steps()

                # Önizleme telemetrisi
                ax, ay = int(self.pinch_anchor[0]), int(self.pinch_anchor[1])
                px, py = int(self.pinch_point[0]), int(self.pinch_point[1])
                cv2.circle(frame, (ax, ay), 6, (0, 0, 255), -1)
                cv2.line(frame, (ax, ay), (px, py), (0, 255, 255), 2)
                cv2.putText(frame, f"PINCH {finger} [{self.pinch_mode}]",
                            (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1)

    def decide_drag_mode(self, finger, dx, dy):
        horizontal = abs(dx) > abs(dy)
        if finger == "INDEX":
            self.pinch_mode = "SCROLL"
            self.mode_changed.emit("⇅ SCROLL")
            log.info("Drag mode: SCROLL")
        elif finger == "MIDDLE":
            if horizontal:
                self.pinch_mode = "CAROUSEL"
                self.carousel_last_x = self.pinch_point[0]
                self.carousel_started.emit()
                self.mode_changed.emit("⇄ UYGULAMA GEÇİŞİ")
                log.info("Drag mode: CAROUSEL (Alt-Tab)")
            else:
                self.swipe_triggered.emit("MIDDLE_UP" if dy < 0 else "MIDDLE_DOWN")
                self.pinch_mode = "DONE"
        elif finger == "RING":
            if horizontal:
                name = "RING_RIGHT" if dx > 0 else "RING_LEFT"
            else:
                name = "RING_UP" if dy < 0 else "RING_DOWN"
            self.swipe_triggered.emit(name)
            self.pinch_mode = "DONE"
        else:
            self.pinch_mode = "DONE"

    def do_scroll(self, dy, now):
        if now - self.last_scroll_emit < 0.03:
            return
        deadzone = 15.0
        mag = abs(dy) - deadzone
        if mag > 0:
            delta = int(min(mag * 2.2 * self.scroll_speed, 400))
            # El yukarı (dy<0) -> sayfa yukarı (pozitif wheel delta)
            self.scroll_delta.emit(delta if dy < 0 else -delta)
        self.last_scroll_emit = now

    def do_carousel_steps(self):
        dxs = self.pinch_point[0] - self.carousel_last_x
        step = self.carousel_step_px
        while dxs > step:
            self.carousel_step.emit(1)
            self.carousel_last_x += step
            dxs -= step
        while dxs < -step:
            self.carousel_step.emit(-1)
            self.carousel_last_x -= step
            dxs += step

    def end_pinch(self, now, cancel=False):
        if self.pinch_finger is None:
            return
        duration_ms = (now - self.pinch_start_t) * 1000.0
        if self.pinch_mode == "CAROUSEL":
            # Alt tuşu mutlaka bırakılmalı (iptalde bile)
            self.carousel_ended.emit()
            log.info("Carousel ended.")
        elif self.pinch_mode == "UNDECIDED" and not cancel and duration_ms <= self.tap_max_ms:
            self.pinch_tap.emit(self.pinch_finger)
            log.info(f"Pinch tap: {self.pinch_finger}")
        self.pinch_finger = None
        self.pinch_mode = "NONE"
        self.pinch_anchor = None
        self.pinch_point = None
        self.mode_changed.emit("")

    # ------------------------------------------------------------------
    # Yüz ifadesi işleme (blendshape'ler)
    # ------------------------------------------------------------------
    def process_blendshapes(self, scores, now):
        thr = self.face_threshold
        off_thr = thr * 0.6

        vals = {
            "BROW_RAISE": scores.get("browInnerUp", 0.0),
            "JAW_OPEN": scores.get("jawOpen", 0.0),
            "MOUTH_PUCKER": scores.get("mouthPucker", 0.0),
            "SMILE": (scores.get("mouthSmileLeft", 0.0) + scores.get("mouthSmileRight", 0.0)) / 2.0,
        }
        # Wink: tek göz kapalı, diğeri açık olmalı (normal göz kırpmayı eler)
        bl = scores.get("eyeBlinkLeft", 0.0)
        br = scores.get("eyeBlinkRight", 0.0)
        vals["WINK_LEFT"] = bl if (bl > thr and br < 0.3) else 0.0
        vals["WINK_RIGHT"] = br if (br > thr and bl < 0.3) else 0.0

        active_expr = "NONE"
        for name, v in vals.items():
            st = self.face_states.setdefault(name, {"on": False, "start": 0.0, "fired": False})
            if not st["on"]:
                if v >= thr:
                    st["on"] = True
                    st["start"] = now
                    st["fired"] = False
            else:
                if v < off_thr:
                    st["on"] = False
                elif not st["fired"]:
                    active_expr = name
                    if (now - st["start"]) * 1000.0 >= self.face_hold_ms:
                        if now - self.face_last_trigger_t > 0.8:
                            st["fired"] = True
                            self.face_last_trigger_t = now
                            self.face_triggered.emit(name)
                            log.info(f"Face expression triggered: {name}")
        return active_expr

    # ------------------------------------------------------------------
    # Ana döngü
    # ------------------------------------------------------------------
    def run(self):
        log.info("Gesture engine thread started.")

        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        base_dir = os.path.dirname(os.path.abspath(__file__))
        hand_model_path = os.path.join(base_dir, "hand_landmarker.task")
        face_model_path = os.path.join(base_dir, "face_landmarker.task")

        if not os.path.exists(hand_model_path):
            log.critical("hand_landmarker.task model file not found!")
            self.status_message.emit("HATA: hand_landmarker.task dosyası bulunamadı!")
            return

        def make_hand_options(delegate=None):
            if delegate is not None:
                base = mp_python.BaseOptions(model_asset_path=hand_model_path, delegate=delegate)
            else:
                base = mp_python.BaseOptions(model_asset_path=hand_model_path)
            return vision.HandLandmarkerOptions(
                base_options=base,
                running_mode=vision.RunningMode.VIDEO,
                num_hands=1,
                min_hand_detection_confidence=0.4,
                min_hand_presence_confidence=0.4,
                min_tracking_confidence=0.3
            )

        try:
            landmarker = vision.HandLandmarker.create_from_options(
                make_hand_options(mp_python.BaseOptions.Delegate.GPU))
            log.info("MediaPipe HandLandmarker created successfully (GPU).")
        except Exception as e:
            log.warning(f"Failed to use GPU delegate: {e}. Falling back to CPU.")
            landmarker = vision.HandLandmarker.create_from_options(make_hand_options())

        # Yüz modeli tembel yüklenir (yüz modu ilk açıldığında)
        face_landmarker = None

        def load_face_landmarker():
            if not os.path.exists(face_model_path):
                log.error("face_landmarker.task model file not found!")
                self.status_message.emit("HATA: face_landmarker.task bulunamadı, yüz modu kapatıldı.")
                return None
            try:
                options = vision.FaceLandmarkerOptions(
                    base_options=mp_python.BaseOptions(model_asset_path=face_model_path),
                    running_mode=vision.RunningMode.VIDEO,
                    num_faces=1,
                    output_face_blendshapes=True
                )
                fl = vision.FaceLandmarker.create_from_options(options)
                log.info("MediaPipe FaceLandmarker created successfully.")
                return fl
            except Exception as e:
                log.error(f"Failed to create FaceLandmarker: {e}")
                return None

        self.status_message.emit("AI Modeli Yüklendi. Kamera Açılıyor...")

        cap = None
        current_cam_idx = self.camera_index
        prev_time = time.perf_counter()
        start_time = time.perf_counter()

        while self.running:
            # Reopen camera if needed
            if cap is None or current_cam_idx != self.camera_index:
                if cap is not None:
                    cap.release()
                log.info(f"Opening camera index {self.camera_index}...")
                cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
                # 640x480 (4:3) zorlamak 16:9 sensörlü webcam'lerde görüntünün
                # yanlarını kırpar ve görüş açısını daraltır. Sensörün doğal
                # 16:9 modunu (1280x720) MJPG ile iste; kamera desteklemezse
                # 640x480'e geri dön.
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                cap.set(cv2.CAP_PROP_FPS, 60)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                if actual_w < 640:
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                log.info(f"Camera negotiated resolution: {actual_w}x{actual_h}")
                current_cam_idx = self.camera_index

                if cap.isOpened():
                    self.status_message.emit(f"Kamera {self.camera_index} Hazır ({actual_w}x{actual_h})")
                else:
                    self.status_message.emit("Kamera açılamadı. 2 saniye sonra tekrar denenecek...")
                    time.sleep(2.0)
                    cap = None
                    continue

            success, frame = cap.read()
            if not success:
                self.status_message.emit("Kamera görüntüsü alınamadı...")
                time.sleep(0.5)
                continue

            # Geniş açı korunarak işleme maliyetini sabit tutmak için kareyi
            # 640 piksel genişliğe küçült (örn. 1280x720 -> 640x360). Piksel
            # tabanlı jest eşikleri (sürükleme mesafeleri) böylece değişmez.
            fh, fw = frame.shape[:2]
            if fw > 640:
                frame = cv2.resize(frame, (640, int(fh * 640 / fw)), interpolation=cv2.INTER_AREA)

            # Mirror the frame horizontally
            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            timestamp_ms = int((time.perf_counter() - start_time) * 1000)
            now = time.time()

            # ----------------------------------------------------------
            # 1. El takibi ve pinch durum makinesi
            # ----------------------------------------------------------
            results = landmarker.detect_for_video(mp_image, timestamp_ms)

            hand_detected = False
            gesture_text = "Yok"

            if results.hand_landmarks and len(results.hand_landmarks) > 0:
                hand_detected = True
                hand_landmarks = results.hand_landmarks[0]

                if self.hand_seen_t == 0.0:
                    self.hand_seen_t = now

                for lm in hand_landmarks:
                    cx, cy = int(lm.x * w), int(lm.y * h)
                    cv2.circle(frame, (cx, cy), 4, (57, 255, 20), -1)

                if self.tracking_enabled:
                    self.process_hand(hand_landmarks, w, h, frame, now)
                elif self.pinch_finger is not None:
                    # Dinleme kapatıldıysa aktif pinch'i güvenle sonlandır
                    self.end_pinch(now, cancel=True)

                if self.pinch_finger is not None:
                    gesture_text = f"{FINGER_TR.get(self.pinch_finger, self.pinch_finger)} Pinch ({self.pinch_mode})"
            else:
                self.hand_seen_t = 0.0
                if self.pinch_finger is not None:
                    self.end_pinch(now, cancel=True)
                    log.info("Pinch cancelled: hand lost.")

            # ----------------------------------------------------------
            # 2. Yüz modu (blendshape'ler)
            # ----------------------------------------------------------
            if self.face_enabled:
                if face_landmarker is None:
                    face_landmarker = load_face_landmarker()
                    if face_landmarker is None:
                        self.face_enabled = False
                if face_landmarker is not None:
                    try:
                        face_res = face_landmarker.detect_for_video(mp_image, timestamp_ms)
                        if face_res.face_blendshapes and len(face_res.face_blendshapes) > 0:
                            scores = {c.category_name: c.score for c in face_res.face_blendshapes[0]}
                            active_expr = self.process_blendshapes(scores, now)
                            if active_expr != "NONE":
                                gesture_text = f"Yüz: {active_expr}"
                                cv2.putText(frame, f"FACE: {active_expr}", (10, 85),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
                    except Exception as e:
                        log.error(f"Face detection error: {e}")

            # ----------------------------------------------------------
            # 3. Önizleme overlay yazıları
            # ----------------------------------------------------------
            state_text = f"MODE: {'DINLEMEDE' if self.tracking_enabled else 'BEKLEMEDE'}"
            state_color = (0, 255, 0) if self.tracking_enabled else (0, 165, 255)
            cv2.putText(frame, state_text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, state_color, 2)
            face_text = f"YUZ MODU: {'ACIK' if self.face_enabled else 'KAPALI'}"
            face_color = (255, 0, 255) if self.face_enabled else (128, 128, 128)
            cv2.putText(frame, face_text, (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, face_color, 2)

            # FPS Calculation
            curr_time = time.perf_counter()
            fps = 1.0 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0
            prev_time = curr_time
            self.fps_updated.emit(fps)

            rgb_out = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            q_img = QImage(rgb_out.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()

            status_dict = {
                "hand_detected": hand_detected,
                "gesture_text": gesture_text,
            }
            self.frame_ready.emit(q_img, status_dict)

            time.sleep(0.015)

        # Cleanup: aktif pinch varsa Alt tuşunun asılı kalmaması için bitir
        if self.pinch_finger is not None:
            self.end_pinch(time.time(), cancel=True)
        if cap is not None:
            cap.release()
        landmarker.close()
        if face_landmarker is not None:
            face_landmarker.close()
        log.info("Gesture engine thread stopped successfully.")
