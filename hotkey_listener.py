import ctypes
from ctypes import wintypes
import time
import logging
from PyQt6.QtCore import QThread, pyqtSignal

log = logging.getLogger("VirtualMouse.Hotkey")
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Windows API Constants
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

class HotkeyListener(QThread):
    """
    Birden fazla global kısayolu dinler.
    hotkeys: {"tracking": "Ctrl+Space", "face": "Ctrl+Shift+Space", ...}
    Tetiklenince hotkey_pressed(name) sinyali yayar.
    """
    hotkey_pressed = pyqtSignal(str)

    def __init__(self, hotkeys):
        super().__init__()
        if isinstance(hotkeys, str):
            hotkeys = {"tracking": hotkeys}
        self.hotkeys = hotkeys
        self.running = True
        self.base_id = 99
        self.id_to_name = {}
        self.native_thread_id = None

    def parse_hotkey(self, hotkey_str):
        parts = [p.strip().lower() for p in hotkey_str.split("+")]
        fs_modifiers = 0
        vk = 0

        for part in parts:
            if part in ("ctrl", "control"):
                fs_modifiers |= MOD_CONTROL
            elif part == "alt":
                fs_modifiers |= MOD_ALT
            elif part == "shift":
                fs_modifiers |= MOD_SHIFT
            elif part == "win":
                fs_modifiers |= MOD_WIN
            elif part == "space":
                vk = 0x20  # VK_SPACE
            elif len(part) == 1:
                vk = ord(part.upper())

        # MOD_NOREPEAT prevents auto-repeating key triggers
        fs_modifiers |= MOD_NOREPEAT
        return fs_modifiers, vk

    def run(self):
        self.native_thread_id = kernel32.GetCurrentThreadId()

        self.id_to_name = {}
        for offset, (name, hk_str) in enumerate(self.hotkeys.items()):
            hk_id = self.base_id + offset
            fs_modifiers, vk = self.parse_hotkey(hk_str)
            user32.UnregisterHotKey(None, hk_id)
            if user32.RegisterHotKey(None, hk_id, fs_modifiers, vk):
                self.id_to_name[hk_id] = name
                log.info(f"Registered global hotkey '{name}': {hk_str}")
            else:
                log.error(f"Failed to register global hotkey '{name}': {hk_str}")

        if not self.id_to_name:
            return

        msg = wintypes.MSG()
        while self.running:
            # GetMessageW blocks until a message is received (0% CPU usage)
            res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if res != 0 and res != -1:
                if msg.message == WM_HOTKEY and msg.wParam in self.id_to_name:
                    name = self.id_to_name[msg.wParam]
                    log.info(f"Global hotkey event triggered: {name}")
                    self.hotkey_pressed.emit(name)
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            time.sleep(0.005)

    def stop(self):
        self.running = False
        for hk_id in self.id_to_name:
            user32.UnregisterHotKey(None, hk_id)
        # Wake up GetMessageW block by posting a dummy message (WM_NULL = 0)
        if self.native_thread_id:
            user32.PostThreadMessageW(self.native_thread_id, 0, 0, 0)
        self.wait()
