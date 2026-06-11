import sys
import os
import json
import logging
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QColor, QPainter, QAction
from PyQt6.QtCore import Qt, QObject

# Set environment variables for OpenCV stability
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"

# Setup Logging
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash_log.txt")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger("VirtualMouse.Main")

# Global Exception Hook to capture all unhandled crashes in crash_log.txt
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    log.critical("Uncaught exception:", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception

# Import modular components
from hotkey_listener import HotkeyListener
from gesture_engine import GestureEngine
from overlay_window import OverlayWindow
from settings_window import SettingsWindow
import action_executor

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

class AirMouseApp(QObject):
    def __init__(self):
        super().__init__()
        log.info("Initializing AirMouse V4 application...")

        # Load config
        self.load_config()

        # 1. Spawn Global Hotkey Listener (el takibi + yüz modu)
        self.hotkey_listener = HotkeyListener({
            "tracking": self.config.get("hotkey", "Ctrl+Space"),
            "face": self.config.get("face_hotkey", "Ctrl+Shift+Space"),
        })
        self.hotkey_listener.hotkey_pressed.connect(self.on_hotkey)
        self.hotkey_listener.start()

        # 2. Spawn Gesture Engine (MediaPipe Webcam worker)
        self.gesture_engine = GestureEngine(self.config)

        # 3. Create transparent desktop overlay window
        self.overlay = OverlayWindow(self.config)
        self.overlay.show()

        # 4. Create settings dashboard GUI window
        self.settings_window = SettingsWindow(self.config, CONFIG_PATH)
        self.settings_window.toggle_tracking_clicked.connect(self.toggle_tracking)
        self.settings_window.toggle_face_clicked.connect(self.toggle_face_mode)
        self.settings_window.settings_changed.connect(self.on_settings_changed)
        self.settings_window.exit_requested.connect(self.quit_application)
        self.settings_window.show()

        # Connect Gesture Engine signals to GUI & Overlay
        self.gesture_engine.frame_ready.connect(self.settings_window.on_frame_ready)
        self.gesture_engine.fps_updated.connect(self.settings_window.on_fps_updated)
        self.gesture_engine.status_message.connect(self.settings_window.on_status_message)
        self.gesture_engine.mode_changed.connect(self.overlay.set_mode_indicator)

        # Connect Gestures to Action Executor
        self.gesture_engine.pinch_tap.connect(self.on_pinch_tap)
        self.gesture_engine.swipe_triggered.connect(self.on_swipe_triggered)
        self.gesture_engine.scroll_delta.connect(self.on_scroll_delta)
        self.gesture_engine.carousel_started.connect(self.on_carousel_started)
        self.gesture_engine.carousel_step.connect(self.on_carousel_step)
        self.gesture_engine.carousel_ended.connect(self.on_carousel_ended)
        self.gesture_engine.face_triggered.connect(self.on_face_triggered)

        # 5. Initialize System Tray Menu
        self.setup_tray()

        # Start Gesture Engine
        self.gesture_engine.start()

        # Sync initial state (standby)
        self.set_tracking_state(self.config.get("tracking_enabled", True))
        self.set_face_state(self.config.get("face_mode_enabled", False), notify=False)

        log.info("Application initialized successfully.")

    def load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
                log.info("Loaded config.json successfully.")
                return
            except Exception as e:
                log.error(f"Failed to parse config.json: {e}")

        # Fallback structure
        self.config = {
            "camera_index": 0,
            "smoothing_factor": 0.5,
            "pinch_close_ratio": 0.40,
            "tap_max_ms": 350,
            "drag_threshold_px": 40,
            "scroll_speed": 1.0,
            "carousel_step_px": 70,
            "face_threshold": 0.5,
            "face_hold_ms": 250,
            "hotkey": "Ctrl+Space",
            "face_hotkey": "Ctrl+Shift+Space",
            "tracking_enabled": False,
            "face_mode_enabled": False
        }

    def save_config(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.update_tray_icon(False) # Initial red icon

        menu = QMenu()

        action_show = QAction("Ayarları Göster (Dashboard)", self)
        action_show.triggered.connect(self.show_dashboard)
        menu.addAction(action_show)

        self.action_listen = QAction("Dinleme Modunu Aç", self)
        self.action_listen.triggered.connect(self.toggle_tracking)
        menu.addAction(self.action_listen)

        self.action_face = QAction("Yüz Modunu Aç", self)
        self.action_face.triggered.connect(self.toggle_face_mode)
        menu.addAction(self.action_face)

        menu.addSeparator()

        action_quit = QAction("Uygulamadan Çık (Quit)", self)
        action_quit.triggered.connect(self.quit_application)
        menu.addAction(action_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

    def update_tray_icon(self, active):
        # Amber/Rose red (#e11d48) for standby, Neon green (#39ff14) for active
        color_hex = "#39ff14" if active else "#e11d48"
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter()
        if painter.begin(pixmap):
            painter.setBrush(QColor(color_hex))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(0, 0, 16, 16)
            painter.end()

        self.tray.setIcon(QIcon(pixmap))
        self.tray.setToolTip(f"AirMouse V4 ({'Dinlemede' if active else 'Uykuda'})")

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_dashboard()

    def show_dashboard(self):
        self.settings_window.show()
        self.settings_window.setWindowState(
            self.settings_window.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive
        )
        self.settings_window.activateWindow()

    # --------------------------------------------------------
    # Hotkey & Mode Toggles
    # --------------------------------------------------------
    def on_hotkey(self, name):
        if name == "tracking":
            self.toggle_tracking()
        elif name == "face":
            self.toggle_face_mode()

    def toggle_tracking(self):
        new_state = not self.gesture_engine.tracking_enabled
        self.set_tracking_state(new_state)

    def set_tracking_state(self, active):
        self.gesture_engine.tracking_enabled = active
        self.settings_window.set_tracking_state(active)
        self.update_tray_icon(active)

        # Show tray balloon bubble message
        if active:
            self.action_listen.setText("Dinleme Modunu Kapat")
            self.tray.showMessage(
                "AirMouse Dinlemede",
                "El hareketleriniz takip ediliyor! Uyutmak için: Ctrl+Space",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
            log.info("Tracking enabled.")
        else:
            self.action_listen.setText("Dinleme Modunu Aç")
            self.tray.showMessage(
                "AirMouse Uykuda",
                "Hareket takibi durduruldu.",
                QSystemTrayIcon.MessageIcon.Information,
                1500
            )
            # Güvenlik: basılı kalan tuş (Alt) bırakılsın, overlay temizlensin
            action_executor.release_all()
            self.overlay.set_mode_indicator("")
            log.info("Tracking disabled.")

        self.config["tracking_enabled"] = active
        self.save_config()

    def toggle_face_mode(self):
        new_state = not self.gesture_engine.face_enabled
        self.set_face_state(new_state)

    def set_face_state(self, active, notify=True):
        self.gesture_engine.face_enabled = active
        self.settings_window.set_face_state(active)
        self.action_face.setText("Yüz Modunu Kapat" if active else "Yüz Modunu Aç")

        if notify:
            if active:
                self.tray.showMessage(
                    "Yüz Modu Açık",
                    "Yüz ifadeleriniz kısayollara dönüştürülüyor. Kapatmak için: Ctrl+Shift+Space",
                    QSystemTrayIcon.MessageIcon.Information,
                    2000
                )
                log.info("Face mode enabled.")
            else:
                self.tray.showMessage(
                    "Yüz Modu Kapalı",
                    "Yüz ifadesi takibi durduruldu.",
                    QSystemTrayIcon.MessageIcon.Information,
                    1500
                )
                log.info("Face mode disabled.")

        self.config["face_mode_enabled"] = active
        self.save_config()

    def on_settings_changed(self):
        log.info("Config reloaded due to GUI settings change.")
        self.load_config()
        self.gesture_engine.update_settings(self.config)
        self.overlay.update_settings(self.config)

    # --------------------------------------------------------
    # Action Handlers from Gesture Engine
    # --------------------------------------------------------
    def on_pinch_tap(self, finger):
        taps = self.config.get("pinch_taps", {})
        action = taps.get(finger, {})
        label = action.get("label", finger)
        key = action.get("key", "")

        if key:
            log.info(f"Triggering pinch tap '{label}': {key}")
            action_executor.execute_action(key)
            self.overlay.trigger_toast(f"{label} [{key.upper()}]")

    def on_swipe_triggered(self, swipe_name):
        swipe_actions = self.config.get("swipe_actions", {})
        action = swipe_actions.get(swipe_name, {})
        label = action.get("label", swipe_name)
        key = action.get("key", "")

        if key:
            log.info(f"Triggering swipe action '{label}': {key}")
            action_executor.execute_action(key)
            self.overlay.trigger_toast(f"⚡ {label} [{key.upper()}]")

    def on_scroll_delta(self, delta):
        # Sürekli scroll: toast gösterilmez (ekranı spamlamamak için)
        action_executor.execute_scroll_raw(delta)

    def on_carousel_started(self):
        action_executor.alt_tab_start()

    def on_carousel_step(self, direction):
        action_executor.alt_tab_step(direction)

    def on_carousel_ended(self):
        action_executor.alt_tab_end()

    def on_face_triggered(self, expr_name):
        face_actions = self.config.get("face_actions", {})
        action = face_actions.get(expr_name, {})
        label = action.get("label", expr_name)
        key = action.get("key", "")

        if key:
            log.info(f"Triggering face action '{label}': {key}")
            action_executor.execute_action(key)
            self.overlay.trigger_toast(f"🙂 {label} [{key.upper()}]")

    # --------------------------------------------------------
    # Clean Application Exit
    # --------------------------------------------------------
    def quit_application(self):
        log.info("Application shutting down...")

        # Stop global hotkey listener
        if hasattr(self, 'hotkey_listener'):
            self.hotkey_listener.stop()

        # Stop MediaPipe worker
        if hasattr(self, 'gesture_engine'):
            self.gesture_engine.running = False
            self.gesture_engine.wait()

        # Güvenlik: basılı kalan tuş varsa bırak
        action_executor.release_all()

        log.info("All background threads stopped cleanly. Exiting GUI.")
        QApplication.quit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Essential: Don't quit if settings window is closed, as we live in tray!
    # But settings window exit_requested signal will quit app cleanly when intended.
    app.setQuitOnLastWindowClosed(False)

    app_instance = AirMouseApp()
    sys.exit(app.exec())
