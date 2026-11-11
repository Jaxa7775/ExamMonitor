# -*- coding: utf-8 -*-
"""
TALABA KLIENTI — BULUTLI (WebSocket) versiya
============================================
LAN versiyasidan farqi: server endi internetdagi bulutli relay (Render va h.k.).
Klient UDP-discovery o'rniga to'g'ridan-to'g'ri wss:// manzilga ulanadi.

config.ini:
  [common] token = ...            (serverdagi EXAM_TOKEN bilan BIR XIL)
  [client] server = wss://sizning-app.onrender.com
           room   = 7-A           (o'qituvchi panelidagi sinf kodi bilan bir xil)

Qolgan hamma narsa LAN versiyasidek: ekran rasmi, oyna/URL nazorati,
bloklash/ochish, xabar, masofadan boshqaruv, "nazorat faol" belgisi.

SHAFFOFLIK: bu yashirin josus dastur emas. Talaba nazorat yoqilganini ko'radi.
Faqat o'z sinf kompyuterlaringizda, talabalar xabardor holatda ishlating.
"""

import json
import queue
import base64
import io
import os
import re
import sys
import time
import threading
import configparser
import ctypes
from ctypes import wintypes
import tkinter as tk

try:
    import websocket  # websocket-client
except ImportError:
    websocket = None

try:
    from PIL import ImageGrab, Image, ImageTk
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False


# ======================== CONFIG ========================
def base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def load_config():
    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(base_dir(), "config.ini"), encoding="utf-8")

    def get(section, key, default):
        try:
            return cfg.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default

    return {
        "token": get("common", "token", "change-me"),
        "server": get("client", "server", "").strip().rstrip("/"),
        "room": get("client", "room", "default").strip(),
        "name": get("client", "name", "").strip(),
        "status_interval": float(get("client", "status_interval", "1.0")),
        "screenshot_interval": float(get("client", "screenshot_interval", "3.0")),
        "screenshot_width": int(get("client", "screenshot_width", "480")),
        "show_banner": get("client", "show_banner", "true").strip().lower()
                       in ("1", "true", "yes", "ha", "on"),
    }


CFG = load_config()
NAME = CFG["name"] or f"{os.environ.get('COMPUTERNAME', 'PC')} / {os.environ.get('USERNAME', '')}"


def ws_url():
    base = CFG["server"]
    # http -> ws, https -> wss (agar foydalanuvchi http yozsa ham to'g'rilaymiz)
    if base.startswith("http://"):
        base = "ws://" + base[7:]
    elif base.startswith("https://"):
        base = "wss://" + base[8:]
    elif not base.startswith(("ws://", "wss://")):
        base = "wss://" + base
    from urllib.parse import quote
    return (f"{base}/ws/student?token={quote(CFG['token'])}"
            f"&room={quote(CFG['room'])}&name={quote(NAME)}")


# ======================== WINAPI ========================
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.mouse_event.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
user32.keybd_event.argtypes = [ctypes.c_ubyte, ctypes.c_ubyte, ctypes.c_uint, ctypes.c_void_p]
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.VkKeyScanW.argtypes = [ctypes.c_wchar]
user32.VkKeyScanW.restype = ctypes.c_short

ME_LEFTDOWN, ME_LEFTUP = 0x02, 0x04
ME_RIGHTDOWN, ME_RIGHTUP = 0x08, 0x10
ME_WHEEL = 0x0800
KEYEVENTF_KEYUP = 2
VK_SHIFT = 0x10
SPECIAL_KEYS = {"Return": 0x0D, "BackSpace": 0x08, "Tab": 0x09, "space": 0x20,
                "Escape": 0x1B, "Left": 0x25, "Up": 0x26, "Right": 0x27, "Down": 0x28,
                "Delete": 0x2E, "Home": 0x24, "End": 0x23, "Prior": 0x21, "Next": 0x22}


def inject_input(msg):
    try:
        kind = msg.get("kind")
        if kind in ("move", "down", "up"):
            if "x" in msg and "y" in msg:
                sw = user32.GetSystemMetrics(0)
                sh = user32.GetSystemMetrics(1)
                user32.SetCursorPos(int(msg["x"] * sw), int(msg["y"] * sh))
            if kind == "down":
                user32.mouse_event(ME_LEFTDOWN if msg.get("btn") != "right" else ME_RIGHTDOWN, 0, 0, 0, None)
            elif kind == "up":
                user32.mouse_event(ME_LEFTUP if msg.get("btn") != "right" else ME_RIGHTUP, 0, 0, 0, None)
        elif kind == "scroll":
            user32.mouse_event(ME_WHEEL, 0, 0, int(msg.get("amount", 0)) & 0xFFFFFFFF, None)
        elif kind == "key":
            _inject_key(msg.get("char", ""), msg.get("keysym", ""))
    except Exception:
        pass


def _inject_key(ch, keysym):
    if keysym in SPECIAL_KEYS:
        vk = SPECIAL_KEYS[keysym]
        user32.keybd_event(vk, 0, 0, None)
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, None)
        return
    if ch and len(ch) == 1 and ch.isprintable():
        res = user32.VkKeyScanW(ch)
        if res == -1:
            return
        vk = res & 0xFF
        shift = (res >> 8) & 1
        if shift:
            user32.keybd_event(VK_SHIFT, 0, 0, None)
        user32.keybd_event(vk, 0, 0, None)
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, None)
        if shift:
            user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, None)


def active_window_title():
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def active_window_exe():
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not h:
        return ""
    try:
        size = wintypes.DWORD(4096)
        buf = ctypes.create_unicode_buffer(4096)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value)
    finally:
        kernel32.CloseHandle(h)
    return ""


BROWSERS = {"chrome.exe", "msedge.exe", "firefox.exe", "opera.exe", "brave.exe",
            "iexplore.exe", "yandex.exe", "browser.exe", "vivaldi.exe", "opera_gx.exe"}
URL_RE = re.compile(r'^(https?://|[\w-]+(\.[\w-]+)+)')


def is_browser(exe):
    return exe.lower() in BROWSERS


def get_browser_url():
    try:
        import uiautomation as auto
    except Exception:
        return ""
    try:
        win = auto.GetForegroundControl()
        if not win:
            return ""
        best = ""
        stack = [(win, 0)]
        visited = 0
        while stack and visited < 500:
            ctrl, depth = stack.pop()
            visited += 1
            if depth >= 10:
                continue
            try:
                children = ctrl.GetChildren()
            except Exception:
                children = []
            for ch in children:
                try:
                    if ch.ControlTypeName == "EditControl":
                        try:
                            val = (ch.GetValuePattern().Value or "").strip()
                        except Exception:
                            val = ""
                        if val and URL_RE.match(val):
                            return val
                        if val and not best:
                            best = val
                except Exception:
                    pass
                stack.append((ch, depth + 1))
        return best
    except Exception:
        return ""


def grab_screenshot_b64(width):
    if not HAVE_PIL:
        return None
    try:
        img = ImageGrab.grab()
        w, h = img.size
        img = img.convert("RGB").resize((width, max(1, int(h * width / w))))
        bio = io.BytesIO()
        img.save(bio, "JPEG", quality=50)
        return base64.b64encode(bio.getvalue()).decode("ascii")
    except (OSError, ValueError):
        return None


# ======================== GUI (LAN versiyasi bilan bir xil) ========================
class ClientGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.cmd_queue = queue.Queue()
        self.stop = False
        self.lock_win = None
        self.lock_lbl = None
        self.control_mode = False
        self.notice = None

        self.banner = None
        self.blabel = None
        if CFG["show_banner"]:
            self.banner = tk.Toplevel(self.root)
            self.banner.overrideredirect(True)
            self.banner.attributes("-topmost", True)
            self.banner.configure(bg="#b00020")
            self.blabel = tk.Label(self.banner, text="●  Imtihon nazorati faol",
                                   fg="white", bg="#b00020",
                                   font=("Segoe UI", 9, "bold"), padx=12, pady=3)
            self.blabel.pack()
            self.root.update_idletasks()
            sw = self.root.winfo_screenwidth()
            self.banner.geometry(f"+{sw // 2 - 90}+0")
            self.root.after(1500, self.reassert_banner)

        self.root.after(150, self.poll)

    def reassert_banner(self):
        if not self.banner:
            return
        try:
            self.banner.attributes("-topmost", True)
            self.banner.lift()
        except tk.TclError:
            pass
        self.root.after(1500, self.reassert_banner)

    def set_connected(self, ok, info=""):
        if not self.banner:
            return
        if ok:
            self.blabel.config(text="●  Imtihon nazorati faol", bg="#b00020")
            self.banner.config(bg="#b00020")
        else:
            self.blabel.config(text=f"○  Serverga ulanmoqda... {info}", bg="#555555")
            self.banner.config(bg="#555555")

    def poll(self):
        try:
            while True:
                self.handle(self.cmd_queue.get_nowait())
        except queue.Empty:
            pass
        self.root.after(150, self.poll)

    def handle(self, msg):
        if "_conn" in msg:
            self.set_connected(msg["_conn"], msg.get("info", ""))
            if not msg["_conn"]:
                self.control_mode = False
                self.hide_notice()
            return
        cmd = msg.get("cmd")
        if cmd == "lock":
            self.show_lock(msg.get("message", ""))
        elif cmd == "unlock":
            self.hide_lock()
        elif cmd == "message":
            self.show_message(msg.get("text", ""))
        elif cmd == "control_start":
            self.control_mode = True
            self.show_notice()
        elif cmd == "control_stop":
            self.control_mode = False
            self.hide_notice()
        elif cmd == "input":
            inject_input(msg)

    def show_notice(self):
        if self.notice:
            return
        w = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.configure(bg="#c62828")
        tk.Label(w, text="⌨  Kompyuteringiz o'qituvchi tomonidan boshqarilyapti",
                 fg="white", bg="#c62828", font=("Segoe UI", 11, "bold"),
                 padx=22, pady=6).pack()
        w.update_idletasks()
        sw = w.winfo_screenwidth()
        ww = w.winfo_width()
        w.geometry(f"+{(sw - ww) // 2}+0")
        self.notice = w
        self.reassert_notice()

    def reassert_notice(self):
        if not self.notice:
            return
        try:
            self.notice.attributes("-topmost", True)
            self.notice.lift()
        except tk.TclError:
            pass
        self.root.after(1000, self.reassert_notice)

    def hide_notice(self):
        if self.notice:
            try:
                self.notice.destroy()
            except tk.TclError:
                pass
            self.notice = None

    def show_message(self, text):
        if not text:
            return
        w = tk.Toplevel(self.root)
        w.title("O'qituvchidan xabar")
        w.attributes("-topmost", True)
        w.configure(bg="#fff8e1")
        tk.Label(w, text="✉  O'qituvchidan xabar", font=("Segoe UI", 12, "bold"),
                 bg="#fff8e1", fg="#7a5c00").pack(padx=24, pady=(16, 4))
        tk.Label(w, text=text, font=("Segoe UI", 13), wraplength=440,
                 justify="left", bg="#fff8e1").pack(padx=24, pady=10)
        tk.Button(w, text="OK", width=12, command=w.destroy).pack(pady=(0, 16))
        w.update_idletasks()
        sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
        ww, wh = w.winfo_width(), w.winfo_height()
        w.geometry(f"+{(sw - ww) // 2}+{(sh - wh) // 3}")
        w.lift()
        w.focus_force()

    def show_lock(self, message):
        text = message or "Kompyuter o'qituvchi tomonidan bloklangan."
        if self.lock_win:
            self.lock_lbl.config(text=text)
            return
        w = tk.Toplevel(self.root)
        w.attributes("-fullscreen", True)
        w.attributes("-topmost", True)
        w.configure(bg="#0b1d3a")
        w.overrideredirect(True)
        w.protocol("WM_DELETE_WINDOW", lambda: None)
        lbl = tk.Label(w, text=text, fg="white", bg="#0b1d3a",
                       font=("Segoe UI", 30, "bold"), wraplength=1000, justify="center")
        lbl.pack(expand=True)
        for seq in ("<Escape>", "<Alt-F4>", "<Key>"):
            w.bind(seq, lambda e: "break")
        w.focus_force()
        self.lock_win = w
        self.lock_lbl = lbl
        self.reassert_lock()

    def reassert_lock(self):
        if self.lock_win:
            try:
                self.lock_win.attributes("-topmost", True)
                self.lock_win.lift()
                self.lock_win.focus_force()
            except tk.TclError:
                pass
            self.root.after(800, self.reassert_lock)

    def hide_lock(self):
        if self.lock_win:
            try:
                self.lock_win.destroy()
            except tk.TclError:
                pass
            self.lock_win = None
            self.lock_lbl = None

    def run(self):
        self.root.mainloop()


# ======================== WebSocket tarmoq sikli ========================
class Net:
    def __init__(self, gui):
        self.gui = gui
        self.ws = None
        self.connected = False
        self.last_status = 0.0
        self.last_shot = 0.0

    def on_open(self, ws):
        self.connected = True
        self.gui.cmd_queue.put({"_conn": True})

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
        except ValueError:
            return
        if data.get("type") == "error":
            self.gui.cmd_queue.put({"_conn": False, "info": "ruxsat yo'q (token/sinf?)"})
            return
        if "cmd" in data:
            self.gui.cmd_queue.put(data)

    def on_close(self, ws, *a):
        self.connected = False
        self.gui.cmd_queue.put({"_conn": False, "info": ""})

    def on_error(self, ws, err):
        self.connected = False

    def safe_send(self, obj):
        if not self.connected or not self.ws:
            return False
        try:
            self.ws.send(json.dumps(obj, ensure_ascii=False))
            return True
        except Exception:
            self.connected = False
            return False

    def sender_loop(self):
        """Doimiy: oyna holati va ekran rasmini yuboradi."""
        while not self.gui.stop:
            if not self.connected:
                time.sleep(0.3)
                continue
            now = time.time()
            if now - self.last_status >= CFG["status_interval"]:
                exe = active_window_exe()
                url = get_browser_url() if is_browser(exe) else ""
                self.safe_send({"type": "status", "window": active_window_title(),
                                "app": exe, "url": url})
                self.last_status = now
            if self.gui.control_mode:
                s_int, s_w = 0.3, max(CFG["screenshot_width"], 960)
            else:
                s_int, s_w = CFG["screenshot_interval"], CFG["screenshot_width"]
            if s_int > 0 and now - self.last_shot >= s_int:
                shot = grab_screenshot_b64(s_w)
                if shot:
                    self.safe_send({"type": "screenshot", "data": shot})
                self.last_shot = now
            time.sleep(0.1)

    def run(self):
        threading.Thread(target=self.sender_loop, daemon=True).start()
        while not self.gui.stop:
            self.gui.cmd_queue.put({"_conn": False, "info": "qidirilmoqda"})
            try:
                self.ws = websocket.WebSocketApp(
                    ws_url(),
                    on_open=self.on_open, on_message=self.on_message,
                    on_close=self.on_close, on_error=self.on_error)
                self.ws.run_forever(ping_interval=30, ping_timeout=10)
            except Exception:
                pass
            self.connected = False
            time.sleep(3)


if __name__ == "__main__":
    if websocket is None:
        ctypes.windll.user32.MessageBoxW(
            0, "websocket-client kutubxonasi topilmadi.\n\npy -m pip install websocket-client",
            "Imtihon nazorati — xato", 0x10)
        sys.exit(1)
    if not CFG["server"]:
        ctypes.windll.user32.MessageBoxW(
            0, "config.ini da server manzili ko'rsatilmagan.\n\n"
               "[client]\nserver = wss://sizning-app.onrender.com",
            "Imtihon nazorati — sozlash", 0x30)
        sys.exit(1)
    gui = ClientGUI()
    net = Net(gui)
    threading.Thread(target=net.run, daemon=True).start()
    gui.run()
