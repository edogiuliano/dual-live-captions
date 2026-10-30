"""Read-only UIA adapters restricted to the two caption applications.

No screenshot, microphone, keyboard, click, desktop text enumeration or network.
"""
import ctypes
from ctypes import wintypes
import html
import re
import time
import psutil


class CaptionReadError(RuntimeError):
    pass


def caption_windows():
    user = ctypes.windll.user32
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.IsIconic.argtypes = [wintypes.HWND]
    identities = {p.info["pid"]: p.info["name"].casefold() for p in psutil.process_iter(["pid", "name"]) if p.info["name"] and p.info["name"].casefold() in ("livecaptions.exe", "duallivecaptions.exe")}
    found = {"windows": [], "dual": [], "overlay": []}
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def inspect(handle, _):
        pid = wintypes.DWORD()
        user.GetWindowThreadProcessId(handle, ctypes.byref(pid))
        executable = identities.get(pid.value)
        if not executable or not user.IsWindowVisible(handle) or user.IsIconic(handle):
            return True
        text = ctypes.create_unicode_buffer(256)
        user.GetWindowTextW(handle, text, 256)
        if executable == "livecaptions.exe":
            found["windows"].append(int(handle))
        elif text.value == "Dual Live Captions":
            found["dual"].append(int(handle))
        elif text.value.startswith("Dual Live Captions · Overlay"):
            found["overlay"].append(int(handle))
        return True
    callback = callback_type(inspect)
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user.EnumWindows(callback, 0)
    return found


def caption_plain(text):
    text = html.unescape(re.sub(r"<[^>]*>", "", text)).strip()
    if text.startswith(("Waiting for English speech", "Esperando voz en español")):
        return ""
    return text


class WindowCaptionReader:
    def __init__(self):
        import comtypes.client
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen import UIAutomationClient as uia
        self.uia = uia
        self.client = comtypes.client.CreateObject(uia.CUIAutomation, interface=uia.IUIAutomation)
        self.windows_node = None
        self.dual_nodes = {}
        self.follow_nodes = []
        self.binding = None
        self.last_probe = -10.0

    def bind(self, now):
        found = caption_windows()
        if len(found["windows"]) != 1:
            raise CaptionReadError("No hay una única ventana visible de Subtítulos en directo de Windows")
        preferred = found["overlay"] or found["dual"]
        if not 1 <= len(preferred) <= 2:
            raise CaptionReadError("Abrí Dual Live Captions o su overlay; no debe estar todo minimizado")
        binding = (found["windows"][0], *sorted(preferred))
        if binding == self.binding:
            return False
        uia, client = self.uia, self.client
        root = client.ElementFromHandle(binding[0])
        condition = client.CreatePropertyCondition(uia.UIA_AutomationIdPropertyId, "CaptionsTextBlock")
        node = root.FindFirst(uia.TreeScope_Descendants, condition)
        if not node:
            raise CaptionReadError("Windows no expone CaptionsTextBlock; no se puede medir esta ventana")
        nodes, follow_nodes = {}, []
        for handle in binding[1:]:
            dual_root = client.ElementFromHandle(handle)
            elements = dual_root.FindAll(uia.TreeScope_Descendants, client.CreateTrueCondition())
            for index in range(elements.Length):
                panel = elements.GetElement(index)
                if not panel.CurrentAutomationId.endswith(".captionPanel"):
                    continue
                children = panel.FindAll(uia.TreeScope_Descendants, client.CreateTrueCondition())
                language, caption = None, None
                for child_index in range(children.Length):
                    child = children.GetElement(child_index)
                    aid = child.CurrentAutomationId
                    if aid.endswith(".languageTag"):
                        language = {"EN": "en", "ES": "es"}.get(child.CurrentName)
                    elif aid.endswith(".QLabel"):
                        caption = child
                    elif aid.endswith(".captionFollowState"):
                        follow_nodes.append(child)
                if language and caption:
                    nodes[language] = caption
        if not nodes:
            raise CaptionReadError("No se localizaron los paneles de Dual en la ventana visible")
        self.binding, self.windows_node, self.dual_nodes = binding, node, nodes
        self.follow_nodes = follow_nodes
        return True

    def read(self):
        now = time.perf_counter()
        rebound = False
        if now - self.last_probe >= 2 or self.binding is None:
            rebound = self.bind(now)
            self.last_probe = now
        before = time.perf_counter()
        if any(node.CurrentName == "Releyendo" for node in self.follow_nodes):
            raise CaptionReadError("Subtítulos en modo relectura: pulsá Lo último para continuar midiendo")
        windows_text = self.windows_node.CurrentName or ""
        after = time.perf_counter()
        windows_time = (before + after) / 2
        dual_texts = {lang: caption_plain(node.CurrentName or "") for lang, node in self.dual_nodes.items()}
        finished = time.perf_counter()
        return windows_text, dual_texts, windows_time, (after + finished) / 2, (finished - before) * 1000, rebound

    def invalidate(self):
        self.binding = None
        self.windows_node = None
        self.dual_nodes = {}
        self.follow_nodes = []
