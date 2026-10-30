import ctypes
import sys
from ctypes import wintypes
from PySide6.QtCore import QAbstractNativeEventFilter


def parse_hotkey(value):
    mods, key = 0x4000, None  # MOD_NOREPEAT
    for token in value.upper().replace(" ", "").split("+"):
        if token in ("CTRL", "CONTROL"):
            mods |= 2
        elif token == "ALT":
            mods |= 1
        elif token == "SHIFT":
            mods |= 4
        elif token == "WIN":
            mods |= 8
        elif len(token) == 1 and token.isalnum():
            key = ord(token)
        elif token.startswith("F") and token[1:].isdigit() and 1 <= int(token[1:]) <= 24:
            key = 0x70 + int(token[1:]) - 1
        else:
            raise ValueError("Usá Ctrl/Alt/Shift/Win + letra, número o F1–F24")
    if key is None or not mods & 15:
        raise ValueError("El atajo debe incluir un modificador y una tecla")
    return mods, key


class Hotkeys(QAbstractNativeEventFilter):
    def __init__(self, widget, bindings):
        super().__init__()
        self.handle = int(widget.winId())
        self.actions = {}
        self.errors = []
        if sys.platform != "win32":
            self.errors = ["Atajos globales disponibles en Windows"]
            return
        user = ctypes.windll.user32
        user.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        user.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        for index, (sequence, action) in enumerate(bindings, 110):
            try:
                mods, key = parse_hotkey(sequence)
                if not user.RegisterHotKey(self.handle, index, mods, key):
                    raise ValueError("Atajo ocupado por otra aplicación")
                self.actions[index] = action
            except ValueError as exc:
                self.errors.append(f"{sequence}: {exc}")

    def nativeEventFilter(self, event_type, message):
        if sys.platform == "win32":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312 and msg.wParam in self.actions:
                self.actions[msg.wParam]()
                return True, 0
        return False, 0

    def close(self):
        if sys.platform == "win32":
            for index in self.actions:
                ctypes.windll.user32.UnregisterHotKey(self.handle, index)
        self.actions.clear()
