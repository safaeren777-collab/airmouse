import os
import ctypes
import logging
import subprocess
import pyautogui

log = logging.getLogger("VirtualMouse.ActionExecutor")

# Windows user32 library for fast native mouse scrolling
user32 = ctypes.windll.user32
MOUSEEVENTF_WHEEL = 0x0800

# Safety settings for pyautogui to prevent lockups
pyautogui.FAILSAFE = False # We handle our own thread management
pyautogui.PAUSE = 0.02     # Karusel adımları için varsayılan 0.1s gecikme çok yavaş

# Alt-Tab karuseli durumu: Alt tuşunun asılı kalmaması için global takip
_alt_held = False

def execute_hotkey(hotkey_str):
    """
    Parse a shortcut string like 'ctrl+t' or 'win+d' and simulate the keys.
    """
    if not hotkey_str:
        return
        
    parts = [p.strip().lower() for p in hotkey_str.split("+")]
    log.info(f"Executing keyboard hotkey: {parts}")
    
    # Map friendly names to pyautogui keys if necessary
    key_mapping = {
        "win": "win",
        "ctrl": "ctrl",
        "control": "ctrl",
        "alt": "alt",
        "shift": "shift",
        "space": "space",
        "left": "left",
        "right": "right",
        "up": "up",
        "down": "down",
        "esc": "esc",
        "tab": "tab"
    }
    
    mapped_parts = [key_mapping.get(part, part) for part in parts]
    try:
        pyautogui.hotkey(*mapped_parts)
    except Exception as e:
        log.error(f"Failed to execute hotkey {hotkey_str}: {e}")

def execute_action(action_str):
    """
    Unified action runner:
      - "app:C:\\path\\program.exe" veya "app:spotify:" -> uygulama başlatır
      - diğer her şey ("ctrl+t", "playpause" vb.)        -> klavye kısayolu
    """
    if not action_str:
        return
    action_str = action_str.strip()
    if action_str.lower().startswith("app:"):
        execute_app_launch(action_str[4:])
    else:
        execute_hotkey(action_str)

def execute_scroll_raw(delta):
    """
    Simulate a native scroll using Windows API with a raw wheel delta.
    120 units = 1 tick; smaller/larger values give proportional smooth scroll.
    """
    try:
        user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, int(delta), 0)
    except Exception as e:
        log.error(f"Failed to simulate scroll: {e}")

def alt_tab_start():
    """
    Alt-Tab karuselini açar: Alt basılı tutulur, ilk Tab gönderilir.
    Pencere seçimi alt_tab_end() çağrılana kadar açık kalır.
    """
    global _alt_held
    if _alt_held:
        return
    try:
        pyautogui.keyDown("alt")
        _alt_held = True
        pyautogui.press("tab")
        log.info("Alt-Tab carousel opened.")
    except Exception as e:
        log.error(f"Failed to open Alt-Tab carousel: {e}")

def alt_tab_step(direction):
    """
    Karuselde bir pencere ileri (+1) veya geri (-1) gider.
    """
    if not _alt_held:
        return
    try:
        if direction >= 0:
            pyautogui.press("tab")
        else:
            pyautogui.keyDown("shift")
            pyautogui.press("tab")
            pyautogui.keyUp("shift")
    except Exception as e:
        log.error(f"Failed to step Alt-Tab carousel: {e}")

def alt_tab_end():
    """
    Alt'ı bırakır; karuselde seçili pencere öne gelir.
    """
    global _alt_held
    if _alt_held:
        try:
            pyautogui.keyUp("alt")
            log.info("Alt-Tab carousel closed (window selected).")
        except Exception as e:
            log.error(f"Failed to close Alt-Tab carousel: {e}")
        _alt_held = False

def release_all():
    """
    Güvenlik: uygulama kapanırken/dinleme durdurulurken basılı tuş bırakılmasın.
    """
    alt_tab_end()

def resolve_app_path(path):
    """
    Resolve common shortcuts and environment variables to avoid 'file not found' errors.
    """
    path = path.strip()
    path_lower = path.lower()
    
    # Check default apps
    if path_lower == "chrome.exe":
        common_chrome = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"chrome" # If registered globally
        ]
        for p in common_chrome:
            if os.path.exists(p) or p == "chrome":
                return p
                
    elif path_lower == "spotify.exe":
        appdata = os.environ.get("APPDATA", "")
        local_spotify = os.path.join(appdata, "Spotify", "Spotify.exe")
        if os.path.exists(local_spotify):
            return local_spotify
        # Microsoft Store / URI handler
        return "spotify:"
        
    elif path_lower == "notepad.exe":
        return "notepad.exe"
    elif path_lower == "calc.exe":
        return "calc.exe"
    elif path_lower == "mspaint.exe":
        return "mspaint.exe"
        
    # Expand environment variables if any
    return os.path.expandvars(path)

def execute_app_launch(app_path):
    """
    Launch a local application or run a system command.
    """
    app_path = app_path.strip()
    if not app_path:
        return
        
    # Launch via protocol directly if it looks like one (e.g. spotify:, http:)
    if ":" in app_path and not app_path[1] == ":": # not a drive letter like C:
        try:
            log.info(f"Opening protocol URI: {app_path}")
            os.startfile(app_path)
            return
        except Exception as e:
            log.warning(f"Failed to launch protocol {app_path}: {e}")
            
    resolved = resolve_app_path(app_path)
    log.info(f"Launching app: {resolved}")
    
    try:
        # os.startfile is native and handles execution contexts perfectly on Windows
        os.startfile(resolved)
    except Exception as e:
        log.warning(f"os.startfile failed for {resolved}, trying subprocess: {e}")
        try:
            # Fallback to subprocess shell launcher
            subprocess.Popen(resolved, shell=True)
        except Exception as e2:
            log.error(f"All application launch methods failed for {app_path}: {e2}")
