import json
import logging
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QComboBox, QTabWidget, QFrame, QLineEdit,
    QFileDialog, QGridLayout, QScrollArea
)
from PyQt6.QtGui import QPixmap, QFont

log = logging.getLogger("VirtualMouse.SettingsWindow")

class SettingsWindow(QWidget):
    settings_changed = pyqtSignal()
    toggle_tracking_clicked = pyqtSignal()
    toggle_face_clicked = pyqtSignal()
    exit_requested = pyqtSignal()

    def __init__(self, config, config_path):
        super().__init__()
        self.config = config
        self.config_path = config_path
        self._loading = True  # init sırasında save tetiklenmesin

        self.setWindowTitle("AirMouse V4 - Akıllı Jest Asistanı")
        self.resize(880, 680)
        self.setMinimumSize(820, 620)

        self.setup_styling()
        self.init_ui()
        self._loading = False

    def setup_styling(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #0c0c0e;
                color: #f4f4f5;
                font-family: 'Segoe UI', sans-serif;
            }
            QTabWidget::pane {
                border: 1px solid #1f1f23;
                background-color: #0c0c0e;
                border-radius: 8px;
                padding: 12px;
            }
            QTabBar::tab {
                background-color: #141416;
                color: #a1a1aa;
                border: 1px solid #1f1f23;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 10px 18px;
                font-weight: 600;
                font-size: 13px;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background-color: #0c0c0e;
                color: #39ff14;
                border-bottom: 2px solid #39ff14;
            }
            QTabBar::tab:hover {
                color: #ffffff;
                background-color: #1a1a1e;
            }
            QFrame#Card {
                background-color: #121215;
                border: 1px solid #1f1f23;
                border-radius: 10px;
                padding: 15px;
            }
            QLabel {
                color: #f4f4f5;
                font-size: 13px;
            }
            QPushButton {
                background-color: #39ff14;
                color: #000000;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2ee610;
            }
            QPushButton:pressed {
                background-color: #25cc0c;
            }
            QPushButton#SecondaryButton {
                background-color: #1e1e24;
                border: 1px solid #2d2d34;
                color: #e4e4e7;
            }
            QPushButton#SecondaryButton:hover {
                background-color: #272730;
            }
            QLineEdit {
                background-color: #141418;
                border: 1px solid #2d2d34;
                border-radius: 5px;
                padding: 6px 10px;
                color: #f4f4f5;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #39ff14;
            }
            QSlider::groove:horizontal {
                height: 5px;
                background: #1f1f23;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #39ff14;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: #39ff14;
                border-radius: 2px;
            }
            QComboBox {
                background-color: #141418;
                border: 1px solid #2d2d34;
                border-radius: 5px;
                color: #f4f4f5;
                padding: 6px 12px;
            }
            QComboBox QAbstractItemView {
                background-color: #141418;
                selection-background-color: #39ff14;
                selection-color: #000000;
                color: #f4f4f5;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # Header Title
        header_layout = QHBoxLayout()
        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)

        main_title = QLabel("AIRMOUSE JEST ASİSTANI V4")
        main_title.setStyleSheet("font-size: 18px; font-weight: 800; letter-spacing: 1px; color: #39ff14;")
        sub_title = QLabel("Pinch Tabanlı Mikro-Jest ve Yüz İfadesi Kontrol Sistemi")
        sub_title.setStyleSheet("color: #71717a; font-size: 12px;")

        title_vbox.addWidget(main_title)
        title_vbox.addWidget(sub_title)
        header_layout.addLayout(title_vbox)

        # FPS Indicator
        self.fps_label = QLabel("Kamera: 0 FPS")
        self.fps_label.setStyleSheet("color: #a1a1aa; font-weight: bold; background: #141416; padding: 6px 12px; border-radius: 5px; border: 1px solid #1f1f23;")
        header_layout.addWidget(self.fps_label, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        main_layout.addLayout(header_layout)

        # Tabs Layout
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.setup_dashboard_tab()
        self.setup_general_settings_tab()
        self.setup_pinch_tab()
        self.setup_drag_tab()
        self.setup_face_tab()

        # Status Bar
        self.status_bar = QLabel("Sistem Çalışıyor | El Takibi: Ctrl+Space | Yüz Modu: Ctrl+Shift+Space")
        self.status_bar.setStyleSheet("color: #52525b; font-size: 11px; padding-top: 5px; border-top: 1px solid #121214;")
        main_layout.addWidget(self.status_bar)

    # ------------------------------------------------------------------
    # Sekmeler
    # ------------------------------------------------------------------
    def setup_dashboard_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setSpacing(15)

        # Left Column: Controller status & Quick Guide
        left_col = QVBoxLayout()
        left_col.setSpacing(15)

        status_card = QFrame()
        status_card.setObjectName("Card")
        sc_layout = QVBoxLayout(status_card)
        sc_layout.setSpacing(8)

        lbl_state_title = QLabel("KONTROLLER DURUMU")
        lbl_state_title.setStyleSheet("color: #71717a; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")

        self.lbl_status = QLabel("BEKLEMEDE (UYKUDA)")
        self.lbl_status.setStyleSheet("color: #e11d48; font-size: 24px; font-weight: 900;")

        self.lbl_gesture_feedback = QLabel("El Durumu: Algılanmadı  |  Aktif Jest: Yok")
        self.lbl_gesture_feedback.setStyleSheet("color: #e4e4e7; font-size: 13px; background-color: #1a1a20; padding: 8px 12px; border-radius: 5px; border: 1px solid #24242d;")

        sc_layout.addWidget(lbl_state_title)
        sc_layout.addWidget(self.lbl_status)
        sc_layout.addWidget(self.lbl_gesture_feedback)

        # Toggle buttons
        self.btn_toggle = QPushButton("DİNLEME MODUNU AÇ")
        self.btn_toggle.clicked.connect(self.toggle_tracking_clicked.emit)
        sc_layout.addWidget(self.btn_toggle)

        self.btn_face_toggle = QPushButton("YÜZ MODUNU AÇ")
        self.btn_face_toggle.setObjectName("SecondaryButton")
        self.btn_face_toggle.clicked.connect(self.toggle_face_clicked.emit)
        sc_layout.addWidget(self.btn_face_toggle)

        left_col.addWidget(status_card)

        # Quick gestures guide
        guide_card = QFrame()
        guide_card.setObjectName("Card")
        gc_layout = QVBoxLayout(guide_card)

        guide_title = QLabel("HIZLI JEST KILAVUZU")
        guide_title.setStyleSheet("font-weight: bold; font-size: 12px; color: #39ff14; margin-bottom: 5px;")
        gc_layout.addWidget(guide_title)

        grid = QGridLayout()
        grid.setSpacing(8)

        guides = [
            ("🤏 İşaret Pinch (tak):", "Onay / Enter"),
            ("🤏 İşaret Pinch + Sürükle:", "Sayfa Kaydırma (Sürekli Scroll)"),
            ("🤏 Orta Pinch + Yatay Sürükle:", "Alt-Tab Karuseli (bırakınca seçer)"),
            ("🤏 Orta Pinch + Dikey Sürükle:", "Görev Görünümü / Masaüstü"),
            ("🤏 Yüzük Pinch + Sürükle:", "Geri / İleri / Büyüt / Sekme Kapat"),
            ("🤏 Serçe Pinch (tak):", "Yapıştır"),
            ("🙂 Yüz Modu (Ctrl+Shift+Space):", "Kaş / Ağız / Göz Kırpma Kısayolları"),
        ]
        for idx, (gest, desc) in enumerate(guides):
            lbl_g = QLabel(gest)
            lbl_g.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 11px;")
            lbl_d = QLabel(desc)
            lbl_d.setStyleSheet("color: #a1a1aa; font-size: 11px;")
            grid.addWidget(lbl_g, idx, 0)
            grid.addWidget(lbl_d, idx, 1)

        gc_layout.addLayout(grid)
        left_col.addWidget(guide_card)
        layout.addLayout(left_col, 3)

        # Right Column: Webcam preview feed
        right_col = QVBoxLayout()

        preview_card = QFrame()
        preview_card.setObjectName("Card")
        pc_layout = QVBoxLayout(preview_card)

        self.preview_label = QLabel("Kamera Önizleme Yükleniyor...\n(Dinleme modu açıkken görünür)")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("color: #52525b; border: 1px dashed #2d2d34; border-radius: 6px; background: #070709;")
        self.preview_label.setMinimumSize(320, 240)

        pc_layout.addWidget(QLabel("<b>CANLI TELEMETRİ GÖRÜNTÜSÜ</b>"))
        pc_layout.addWidget(self.preview_label)

        right_col.addWidget(preview_card)
        layout.addLayout(right_col, 2)

        self.tabs.addTab(tab, "Dashboard")

    def _add_slider(self, parent_layout, title_html, lo, hi, value, fmt_func):
        """Slider + değer etiketi oluşturur, (slider, label) döner."""
        parent_layout.addWidget(QLabel(title_html))
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(lo, hi)
        slider.setValue(value)

        lbl = QLabel(fmt_func(value))
        lbl.setStyleSheet("color: #39ff14; font-weight: bold;")
        slider.valueChanged.connect(lambda v: (lbl.setText(fmt_func(v)), self.save_settings()))

        row = QHBoxLayout()
        row.addWidget(slider)
        row.addWidget(lbl)
        parent_layout.addLayout(row)
        return slider, lbl

    def setup_general_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        c_layout = QVBoxLayout(scroll_widget)
        c_layout.setSpacing(15)

        container = QFrame()
        container.setObjectName("Card")
        card_layout = QVBoxLayout(container)
        card_layout.setSpacing(15)

        # Camera index selection
        card_layout.addWidget(QLabel("<b>Kamera Kaynağı (Webcam Source):</b>"))
        self.combo_camera = QComboBox()
        for idx in range(4):
            self.combo_camera.addItem(f"Kamera (Webcam {idx})", idx)
        self.combo_camera.setCurrentIndex(self.config.get("camera_index", 0))
        self.combo_camera.currentIndexChanged.connect(self.save_settings)
        card_layout.addWidget(self.combo_camera)

        # Pinch hassasiyeti
        self.slider_pinch, self.lbl_pinch_val = self._add_slider(
            card_layout,
            "<b>Pinch Hassasiyeti:</b><br><span style='color:#71717a; font-size:11px;'>"
            "Düşük değer = parmak uçlarının daha çok yaklaşması gerekir (daha az yanlış tetikleme). "
            "Yüksek değer = daha kolay pinch.</span>",
            25, 55,
            int(self.config.get("pinch_close_ratio", 0.40) * 100),
            lambda v: f"Değer: {v / 100.0:.2f}"
        )

        # Tepki hızı (EMA)
        self.slider_smoothing, self.lbl_smoothing_val = self._add_slider(
            card_layout,
            "<b>Tepki Hızı (Smoothing):</b><br><span style='color:#71717a; font-size:11px;'>"
            "Yüksek değer = el hareketine anında tepki (hafif titreme olabilir). "
            "Düşük değer = daha yumuşak ama gecikmeli.</span>",
            10, 90,
            int(self.config.get("smoothing_factor", 0.5) * 100),
            lambda v: f"Değer: {v / 100.0:.2f}"
        )

        # Tap süresi
        self.slider_tap, self.lbl_tap_val = self._add_slider(
            card_layout,
            "<b>Tap Süresi (Maksimum):</b><br><span style='color:#71717a; font-size:11px;'>"
            "Pinch bu süreden kısa sürerse 'dokunuş' sayılır ve kısayol tetiklenir.</span>",
            20, 60,
            int(self.config.get("tap_max_ms", 350) / 10),
            lambda v: f"Değer: {v * 10} ms"
        )

        # Sürükleme eşiği
        self.slider_drag, self.lbl_drag_val = self._add_slider(
            card_layout,
            "<b>Sürükleme Eşiği:</b><br><span style='color:#71717a; font-size:11px;'>"
            "Pinch tutarken elin bu mesafeden (piksel) fazla hareket etmesi sürükleme modunu başlatır.</span>",
            25, 90,
            int(self.config.get("drag_threshold_px", 40)),
            lambda v: f"Değer: {v} px"
        )

        # Scroll hızı
        self.slider_scroll, self.lbl_scroll_val = self._add_slider(
            card_layout,
            "<b>Scroll Hızı:</b><br><span style='color:#71717a; font-size:11px;'>"
            "İşaret pinch ile sürükleme sırasında sayfa kaydırma hızı çarpanı.</span>",
            5, 30,
            int(self.config.get("scroll_speed", 1.0) * 10),
            lambda v: f"Değer: {v / 10.0:.1f}x"
        )

        # Karusel adımı
        self.slider_carousel, self.lbl_carousel_val = self._add_slider(
            card_layout,
            "<b>Alt-Tab Karusel Adımı:</b><br><span style='color:#71717a; font-size:11px;'>"
            "Karuselde bir sonraki pencereye geçmek için gereken yatay el hareketi mesafesi.</span>",
            40, 140,
            int(self.config.get("carousel_step_px", 70)),
            lambda v: f"Değer: {v} px"
        )

        c_layout.addWidget(container)

        btn_reset = QPushButton("Varsayılan Ayarlara Dön")
        btn_reset.setObjectName("SecondaryButton")
        btn_reset.clicked.connect(self.reset_defaults)
        c_layout.addWidget(btn_reset)

        c_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        self.tabs.addTab(tab, "Genel Ayarlar")

    def _build_action_rows(self, grid, names_tr, config_key, store_dict):
        """Etiket + kısayol giriş satırlarını oluşturur."""
        actions = self.config.get(config_key, {})
        for idx, (name, title) in enumerate(names_tr.items()):
            action_data = actions.get(name, {"label": "", "key": ""})

            lbl = QLabel(f"<b>{title}:</b>")
            lbl.setStyleSheet("color: #39ff14;")

            txt_label = QLineEdit(action_data.get("label", ""))
            txt_label.setPlaceholderText("Görünecek Etiket (Örn: Kopyala)")
            txt_label.textChanged.connect(self.save_settings)

            txt_key = QLineEdit(action_data.get("key", ""))
            txt_key.setPlaceholderText("Kısayol (Örn: ctrl+c veya app:notepad.exe)")
            txt_key.textChanged.connect(self.save_settings)

            grid.addWidget(lbl, idx, 0)
            grid.addWidget(QLabel("Etiket:"), idx, 1)
            grid.addWidget(txt_label, idx, 2)
            grid.addWidget(QLabel("Kısayol:"), idx, 3)
            grid.addWidget(txt_key, idx, 4)

            store_dict[name] = {"label": txt_label, "key": txt_key}

    def setup_pinch_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel("<b>Pinch Dokunuşları (Mikro-Jest Kısayolları)</b><br>"
                      "<span style='color:#71717a; font-size:11px;'>"
                      "Başparmağınızla bir parmak ucunuza kısaca dokunup bırakın — el havaya kalkmadan, "
                      "dinlenme pozisyonunda çalışır. Kısayol alanına <b>app:</b> öneki ile yazarsanız "
                      "uygulama başlatır (Örn: app:spotify: veya app:C:\\...\\program.exe).</span>")
        layout.addWidget(info)

        container = QFrame()
        container.setObjectName("Card")
        grid = QGridLayout(container)
        grid.setSpacing(10)

        self.pinch_inputs = {}
        pinch_tr = {
            "INDEX": "🤏 Başparmak + İşaret",
            "MIDDLE": "🤏 Başparmak + Orta",
            "RING": "🤏 Başparmak + Yüzük",
            "PINKY": "🤏 Başparmak + Serçe",
        }
        self._build_action_rows(grid, pinch_tr, "pinch_taps", self.pinch_inputs)
        layout.addWidget(container)

        note = QFrame()
        note.setObjectName("Card")
        n_layout = QVBoxLayout(note)
        n_layout.addWidget(QLabel("<b>💡 İPUCU</b>"))
        n_layout.addWidget(QLabel("<span style='color:#a1a1aa;'>Pinch'i kısa tutarsanız 'dokunuş' (tap) olur ve buradaki "
                                  "kısayol çalışır. Pinch'i tutup elinizi sürüklerseniz 'Sürükleme Jestleri' sekmesindeki "
                                  "davranışlar devreye girer.</span>"))
        layout.addWidget(note)

        layout.addStretch()
        self.tabs.addTab(tab, "Pinch Dokunuşları")

    def setup_drag_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel("<b>Pinch + Sürükleme Jestleri (Havadaki Touchpad)</b><br>"
                      "<span style='color:#71717a; font-size:11px;'>"
                      "Pinch yapın, tutun ve elinizi bir yöne çekin — touchpad'de parmak kaydırmak gibi. "
                      "Bırakınca jest tamamlanır.</span>")
        layout.addWidget(info)

        # Sabit davranışlar
        fixed_card = QFrame()
        fixed_card.setObjectName("Card")
        f_layout = QVBoxLayout(fixed_card)
        f_layout.addWidget(QLabel("<b>SABİT DAVRANIŞLAR</b>"))
        f_layout.addWidget(QLabel("<span style='color:#a1a1aa;'>"
                                  "⇅ <b>İşaret Pinch + Sürükle:</b> Sürekli sayfa kaydırma — el yukarı/aşağı gittikçe "
                                  "orantılı hızda scroll yapar (joystick mantığı).<br>"
                                  "⇄ <b>Orta Pinch + Yatay Sürükle:</b> Alt-Tab karuseli — Alt basılı kalır, sağa/sola "
                                  "kaydırdıkça pencereler arasında gezersiniz, pinch'i bırakınca seçilen pencere açılır.</span>"))
        layout.addWidget(fixed_card)

        container = QFrame()
        container.setObjectName("Card")
        grid = QGridLayout(container)
        grid.setSpacing(10)

        self.swipe_inputs = {}
        swipes_tr = {
            "MIDDLE_UP": "🤏⬆ Orta Pinch + Yukarı",
            "MIDDLE_DOWN": "🤏⬇ Orta Pinch + Aşağı",
            "RING_LEFT": "🤏⬅ Yüzük Pinch + Sola",
            "RING_RIGHT": "🤏➡ Yüzük Pinch + Sağa",
            "RING_UP": "🤏⬆ Yüzük Pinch + Yukarı",
            "RING_DOWN": "🤏⬇ Yüzük Pinch + Aşağı",
        }
        self._build_action_rows(grid, swipes_tr, "swipe_actions", self.swipe_inputs)
        layout.addWidget(container)

        layout.addStretch()
        self.tabs.addTab(tab, "Sürükleme Jestleri")

    def setup_face_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        s_layout = QVBoxLayout(scroll_widget)
        s_layout.setSpacing(12)

        info = QLabel("<b>Yüz Modu (Eller Tamamen Serbest)</b><br>"
                      "<span style='color:#71717a; font-size:11px;'>"
                      "Yüz ifadeleriniz (kaş kaldırma, ağız açma, göz kırpma...) kısayollara dönüştürülür. "
                      "Eller klavyedeyken bile çalışır. Açma/Kapatma: <b>Ctrl+Shift+Space</b></span>")
        s_layout.addWidget(info)

        # Ayarlar kartı
        tune_card = QFrame()
        tune_card.setObjectName("Card")
        t_layout = QVBoxLayout(tune_card)
        t_layout.setSpacing(15)

        self.slider_face_thr, self.lbl_face_thr_val = self._add_slider(
            t_layout,
            "<b>İfade Eşiği:</b><br><span style='color:#71717a; font-size:11px;'>"
            "Yüksek değer = ifadeyi daha belirgin yapmanız gerekir (daha az yanlış tetikleme).</span>",
            30, 80,
            int(self.config.get("face_threshold", 0.5) * 100),
            lambda v: f"Değer: {v / 100.0:.2f}"
        )

        self.slider_face_hold, self.lbl_face_hold_val = self._add_slider(
            t_layout,
            "<b>İfade Tutma Süresi:</b><br><span style='color:#71717a; font-size:11px;'>"
            "İfadenin tetiklenmesi için bu süre boyunca sabit tutulması gerekir "
            "(normal göz kırpma ~150ms olduğundan yanlış tetiklemeyi engeller).</span>",
            10, 60,
            int(self.config.get("face_hold_ms", 250) / 10),
            lambda v: f"Değer: {v * 10} ms"
        )

        s_layout.addWidget(tune_card)

        # İfade eşlemeleri
        container = QFrame()
        container.setObjectName("Card")
        grid = QGridLayout(container)
        grid.setSpacing(10)

        self.face_inputs = {}
        face_tr = {
            "BROW_RAISE": "🤨 Kaş Kaldırma",
            "JAW_OPEN": "😮 Ağız Açma",
            "MOUTH_PUCKER": "😗 Dudak Büzme",
            "SMILE": "🙂 Gülümseme",
            "WINK_LEFT": "😉 Sol Göz Kırpma",
            "WINK_RIGHT": "😉 Sağ Göz Kırpma",
        }
        self._build_action_rows(grid, face_tr, "face_actions", self.face_inputs)
        s_layout.addWidget(container)

        note = QFrame()
        note.setObjectName("Card")
        n_layout = QVBoxLayout(note)
        n_layout.addWidget(QLabel("<b>💡 İPUCU</b>"))
        n_layout.addWidget(QLabel("<span style='color:#a1a1aa;'>Gülümseme gündelik hayatta sık gerçekleştiği için "
                                  "varsayılan olarak boş bırakılmıştır. Konuşurken yanlış tetikleme yaşıyorsanız "
                                  "İfade Eşiğini yükseltin. Kısayol alanını boş bırakmak o ifadeyi devre dışı bırakır.</span>"))
        s_layout.addWidget(note)

        s_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        self.tabs.addTab(tab, "Yüz Modu")

    # ------------------------------------------------------------------
    # Durum güncellemeleri
    # ------------------------------------------------------------------
    def set_tracking_state(self, active):
        if active:
            self.lbl_status.setText("DİNLEMEDE (AÇIK)")
            self.lbl_status.setStyleSheet("color: #39ff14; font-size: 24px; font-weight: 900;")
            self.btn_toggle.setText("DİNLEME MODUNU KAPAT")
            self.btn_toggle.setStyleSheet("background-color: #e11d48; color: white;")
        else:
            self.lbl_status.setText("BEKLEMEDE (UYKUDA)")
            self.lbl_status.setStyleSheet("color: #e11d48; font-size: 24px; font-weight: 900;")
            self.btn_toggle.setText("DİNLEME MODUNU AÇ")
            self.btn_toggle.setStyleSheet("background-color: #39ff14; color: black;")

    def set_face_state(self, active):
        if active:
            self.btn_face_toggle.setText("YÜZ MODUNU KAPAT")
            self.btn_face_toggle.setStyleSheet("background-color: #d946ef; color: white; border: none;")
        else:
            self.btn_face_toggle.setText("YÜZ MODUNU AÇ")
            self.btn_face_toggle.setStyleSheet("")

    def on_status_message(self, msg):
        self.status_bar.setText(msg)

    # ------------------------------------------------------------------
    # Kaydetme / Sıfırlama
    # ------------------------------------------------------------------
    def save_settings(self):
        if self._loading:
            return

        self.config["camera_index"] = self.combo_camera.currentIndex()
        self.config["pinch_close_ratio"] = self.slider_pinch.value() / 100.0
        self.config["smoothing_factor"] = self.slider_smoothing.value() / 100.0
        self.config["tap_max_ms"] = self.slider_tap.value() * 10
        self.config["drag_threshold_px"] = self.slider_drag.value()
        self.config["scroll_speed"] = self.slider_scroll.value() / 10.0
        self.config["carousel_step_px"] = self.slider_carousel.value()
        self.config["face_threshold"] = self.slider_face_thr.value() / 100.0
        self.config["face_hold_ms"] = self.slider_face_hold.value() * 10

        def collect(inputs):
            out = {}
            for name, widgets in inputs.items():
                out[name] = {
                    "label": widgets["label"].text().strip(),
                    "key": widgets["key"].text().strip()
                }
            return out

        self.config["pinch_taps"] = collect(self.pinch_inputs)
        self.config["swipe_actions"] = collect(self.swipe_inputs)
        self.config["face_actions"] = collect(self.face_inputs)

        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            self.settings_changed.emit()
        except Exception as e:
            log.error(f"Failed to save settings: {e}")

    def reset_defaults(self):
        self._loading = True

        self.combo_camera.setCurrentIndex(0)
        self.slider_pinch.setValue(40)      # 0.40
        self.slider_smoothing.setValue(50)  # 0.5
        self.slider_tap.setValue(35)        # 350 ms
        self.slider_drag.setValue(40)       # 40 px
        self.slider_scroll.setValue(10)     # 1.0x
        self.slider_carousel.setValue(70)   # 70 px
        self.slider_face_thr.setValue(50)   # 0.50
        self.slider_face_hold.setValue(25)  # 250 ms

        defaults_pinch = {
            "INDEX": ("Onay / Enter", "enter"),
            "MIDDLE": ("Yeni Sekme", "ctrl+t"),
            "RING": ("Kopyala", "ctrl+c"),
            "PINKY": ("Yapıştır", "ctrl+v"),
        }
        for name, (lbl, key) in defaults_pinch.items():
            self.pinch_inputs[name]["label"].setText(lbl)
            self.pinch_inputs[name]["key"].setText(key)

        defaults_swipes = {
            "MIDDLE_UP": ("Görev Görünümü", "win+tab"),
            "MIDDLE_DOWN": ("Masaüstünü Göster", "win+d"),
            "RING_LEFT": ("Geri", "alt+left"),
            "RING_RIGHT": ("İleri", "alt+right"),
            "RING_UP": ("Pencereyi Büyüt", "win+up"),
            "RING_DOWN": ("Sekme Kapat", "ctrl+w"),
        }
        for name, (lbl, key) in defaults_swipes.items():
            self.swipe_inputs[name]["label"].setText(lbl)
            self.swipe_inputs[name]["key"].setText(key)

        defaults_face = {
            "BROW_RAISE": ("Uygulama Değiştir", "alt+tab"),
            "JAW_OPEN": ("Oynat / Duraklat", "playpause"),
            "MOUTH_PUCKER": ("Masaüstünü Göster", "win+d"),
            "SMILE": ("", ""),
            "WINK_LEFT": ("Geri", "alt+left"),
            "WINK_RIGHT": ("İleri", "alt+right"),
        }
        for name, (lbl, key) in defaults_face.items():
            self.face_inputs[name]["label"].setText(lbl)
            self.face_inputs[name]["key"].setText(key)

        self._loading = False
        self.save_settings()
        self.status_bar.setText("Ayarlar varsayılan değerlere sıfırlandı.")

    # ------------------------------------------------------------------
    # Motor geri bildirimleri
    # ------------------------------------------------------------------
    def on_frame_ready(self, q_img, status_dict):
        # Update preview label if Dashboard tab is selected
        if self.tabs.currentIndex() == 0:
            pixmap = QPixmap.fromImage(q_img)
            self.preview_label.setPixmap(
                pixmap.scaled(self.preview_label.size(),
                              Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
            )

            hand = "Algılandı" if status_dict.get("hand_detected") else "Algılanmadı"
            gesture = status_dict.get("gesture_text", "Yok")
            self.lbl_gesture_feedback.setText(f"El Durumu: {hand}  |  Aktif Jest: {gesture}")

    def on_fps_updated(self, fps):
        self.fps_label.setText(f"Webcam: {fps:.0f} FPS")

    def closeEvent(self, event):
        # Fully quit the application when the close (X) button is pressed
        log.info("Settings window closed. Requesting full application shutdown.")
        self.exit_requested.emit()
        event.accept()
