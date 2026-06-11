import logging
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QLinearGradient

log = logging.getLogger("VirtualMouse.Overlay")

class OverlayWindow(QWidget):
    """
    AirMouse V4 şeffaf overlay'i.
    - Üst neon ışık + mod pili: aktif sürükleme modunu gösterir (SCROLL, UYGULAMA GEÇİŞİ)
    - Toast: tetiklenen kısayolların anlık bildirimi
    """
    def __init__(self, config):
        super().__init__()
        self.config = config

        # Windows API Setup for Frameless Transparent Click-Through
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.SubWindow
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.set_click_through()

        # Fit to screen
        screen = QApplication.primaryScreen()
        scr_size = screen.size()
        self.width = scr_size.width()
        self.height = scr_size.height()
        self.setGeometry(0, 0, self.width, self.height)

        # Visual/Animation state variables
        self.top_light_height = 0.0   # 0.0 - 1.0
        self.mode_text = ""           # aktif mod pili metni ("" = gizli)
        self.mode_opacity = 0.0       # 0.0 - 1.0

        # Toast settings
        self.toast_msg = ""
        self.toast_opacity = 0        # 0 - 255
        self.toast_timer = QTimer()
        self.toast_timer.timeout.connect(self.fade_toast)

        # Timers for smooth transitions
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.update_animations)
        self.anim_timer.start(16)  # ~60 FPS update rate

    def set_click_through(self):
        """
        Apply WS_EX_TRANSPARENT and WS_EX_LAYERED window styles to pass all mouse events
        through the overlay window to underlying applications.
        """
        try:
            hwnd = int(self.winId())
            import ctypes
            GWL_EXSTYLE = -20
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_LAYERED = 0x00080000

            user32 = ctypes.windll.user32

            # Resolve function signatures for 32-bit vs 64-bit safety
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                GetWindowLong = user32.GetWindowLongPtrW
                SetWindowLong = user32.SetWindowLongPtrW
                GetWindowLong.argtypes = [ctypes.c_void_p, ctypes.c_int]
                GetWindowLong.restype = ctypes.c_void_p
                SetWindowLong.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
                SetWindowLong.restype = ctypes.c_void_p
            else:
                GetWindowLong = user32.GetWindowLongW
                SetWindowLong = user32.SetWindowLongW
                GetWindowLong.argtypes = [ctypes.c_void_p, ctypes.c_int]
                GetWindowLong.restype = ctypes.c_long
                SetWindowLong.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
                SetWindowLong.restype = ctypes.c_long

            style = GetWindowLong(hwnd, GWL_EXSTYLE)
            new_style = style | WS_EX_TRANSPARENT | WS_EX_LAYERED
            SetWindowLong(hwnd, GWL_EXSTYLE, new_style)
            log.info("Overlay click-through styles applied successfully.")
        except Exception as e:
            log.error(f"Failed to set window click-through: {e}")

    def update_settings(self, config):
        self.config = config

    def set_mode_indicator(self, text):
        """Aktif sürükleme modunu üst pilde göster; '' ile gizle."""
        self.mode_text = text or ""
        self.update()

    def trigger_toast(self, message):
        self.toast_msg = message
        self.toast_opacity = 255
        # Reset toast timer: show fully, then fade out after 1 second
        self.toast_timer.stop()
        QTimer.singleShot(1000, lambda: self.toast_timer.start(30))
        self.update()

    def fade_toast(self):
        if self.toast_opacity > 0:
            self.toast_opacity = max(0, self.toast_opacity - 15)
            self.update()
        else:
            self.toast_timer.stop()

    def update_animations(self):
        target = 1.0 if self.mode_text else 0.0

        # Smooth interpolation (EMA)
        self.top_light_height += (target - self.top_light_height) * 0.2
        self.mode_opacity += (target - self.mode_opacity) * 0.2

        if (abs(self.top_light_height - target) > 0.01 or
                abs(self.mode_opacity - target) > 0.01 or
                self.toast_opacity > 0):
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Neon top light panel
        if self.top_light_height > 0.01:
            self.draw_top_light(painter)

        # 2. Mode pill (aktif sürükleme modu)
        if self.mode_opacity > 0.02 and self.mode_text:
            self.draw_mode_pill(painter)

        # 3. Toast notification banner
        if self.toast_opacity > 0:
            self.draw_toast(painter)

    def draw_top_light(self, painter):
        panel_w = 400
        max_h = 24
        h = max_h * self.top_light_height
        x = (self.width - panel_w) / 2

        # Soft outer glow
        glow_rect = QRectF(x - 50, 0, panel_w + 100, h + 15)
        glow_grad = QLinearGradient(0, 0, 0, h + 15)
        glow_grad.setColorAt(0.0, QColor(57, 255, 20, int(80 * self.top_light_height)))
        glow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(glow_rect, QBrush(glow_grad))

        # Solid inner bar
        bar_rect = QRectF(x, 0, panel_w, h)
        bar_grad = QLinearGradient(0, 0, 0, h)
        bar_grad.setColorAt(0.0, QColor(57, 255, 20, int(230 * self.top_light_height)))
        bar_grad.setColorAt(1.0, QColor(57, 255, 20, int(120 * self.top_light_height)))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bar_grad))
        painter.drawRoundedRect(bar_rect, 6, 6)

    def draw_mode_pill(self, painter):
        opacity = self.mode_opacity
        pill_w = 320
        pill_h = 44
        x = (self.width - pill_w) / 2
        y = 38

        rect = QRectF(x, y, pill_w, pill_h)
        bg_color = QColor(12, 12, 16, int(225 * opacity))
        border_color = QColor(57, 255, 20, int(200 * opacity))

        painter.setPen(QPen(border_color, 2))
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(rect, pill_h / 2, pill_h / 2)

        painter.setPen(QColor(57, 255, 20, int(255 * opacity)))
        painter.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.mode_text)

    def draw_toast(self, painter):
        # Toast banner at the bottom center of the screen
        toast_w = 420
        toast_h = 55
        x = (self.width - toast_w) / 2
        y = self.height - 120  # Float above taskbar

        rect = QRectF(x, y, toast_w, toast_h)
        opacity = self.toast_opacity

        # Background: Glassmorphism dark card
        bg_color = QColor(15, 15, 20, int(230 * (opacity / 255.0)))
        border_color = QColor(57, 255, 20, int(150 * (opacity / 255.0)))

        painter.setPen(QPen(border_color, 2, Qt.PenStyle.SolidLine))
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(rect, 10, 10)

        # Text and icon
        painter.setPen(QColor(255, 255, 255, opacity))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        text_rect = QRectF(x + 20, y, toast_w - 40, toast_h)

        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, f"⚡ {self.toast_msg}")
