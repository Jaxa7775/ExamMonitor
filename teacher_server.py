# -*- coding: utf-8 -*-
"""
O'QITUVCHI SERVERI (teacher_server.py)  —  kengaytirilgan versiya
------------------------------------------------------------------
Imkoniyatlar:
  * Avtomatik topish: talaba klientlari serverni o'zi topadi (IP yozish shart emas).
  * config.ini: barcha sozlamalar shu faylda (kod tahrirlanmaydi).
  * Live ekran ko'rish: talaba ekranlari kichik rasm (thumbnail) ko'rinishida,
    bosib kattalashtirsa bo'ladi.
  * Faol oyna nazorati: ruxsatsiz oyna ochilsa — qizil + ovoz + jurnal.
  * Bloklash / ochish / ish stoliga fon qo'yish.
  * Imtihon jurnali: barcha hodisalar CSV faylga yoziladi (hisobot uchun).

Faqat ishonchli LAN ichida ishlating. Internetga ochmang.
"""

import socket
import threading
import json
import queue
import base64
import io
import os
import sys
import csv
import time
import struct
import configparser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

try:
    import winsound
except ImportError:
    winsound = None

try:
    from PIL import Image, ImageTk, ImageGrab
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
        "port": int(get("common", "port", "50200")),
        "discovery_port": int(get("common", "discovery_port", "50201")),
        "audio_port": int(get("common", "audio_port", "50202")),
        "log_dir": get("server", "log_dir", "logs"),
    }


CFG = load_config()

events = queue.Queue()
clients = {}
clients_lock = threading.Lock()
_next_id = [1]

audio_socks = []           # talabalarning ovoz ulanishlari (mikrofon eshittirish uchun)
audio_lock = threading.Lock()


def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


# ======================== DISCOVERY (UDP) ========================
def discovery_responder():
    """Talaba klienti so'rov yuborsa, server o'z TCP portini qaytaradi."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("", CFG["discovery_port"]))
    except OSError:
        return
    while True:
        try:
            data, addr = s.recvfrom(2048)
            msg = json.loads(data.decode("utf-8"))
        except (OSError, ValueError):
            continue
        if msg.get("q") == "exam_server" and msg.get("token") == CFG["token"]:
            reply = json.dumps({"exam_server": True, "port": CFG["port"]}).encode("utf-8")
            try:
                s.sendto(reply, addr)
            except OSError:
                pass


# ======================== OVOZ (AUDIO) LISTENER ========================
def audio_listener():
    """Talabalarning ovoz ulanishlarini qabul qiladi (mikrofon eshittirish uchun)."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind(("0.0.0.0", CFG["audio_port"]))
    except OSError:
        return
    srv.listen(60)
    while True:
        sock, addr = srv.accept()
        threading.Thread(target=audio_handle, args=(sock, addr), daemon=True).start()


def audio_handle(sock, addr):
    try:
        sock.settimeout(10)
        buf = b""
        while b"\n" not in buf:
            chunk = sock.recv(1024)
            if not chunk:
                sock.close()
                return
            buf += chunk
        hello = json.loads(buf.split(b"\n", 1)[0].decode("utf-8"))
        if hello.get("type") != "audio_hello" or hello.get("token") != CFG["token"]:
            sock.close()
            return
        sock.settimeout(None)
        with audio_lock:
            audio_socks.append(sock)
        while True:                       # ulanishni ushlab turamiz; yopilsa recv b"" qaytaradi
            if not sock.recv(1024):
                break
    except OSError:
        pass
    finally:
        with audio_lock:
            if sock in audio_socks:
                audio_socks.remove(sock)
        try:
            sock.close()
        except OSError:
            pass


# ======================== TCP SERVER ========================
class ClientConn:
    def __init__(self, sock, addr, cid):
        self.sock = sock
        self.addr = addr
        self.cid = cid
        self.name = addr[0]
        self.window = ""
        self.app = ""
        self.url = ""
        self.ok = True
        self.lock = threading.Lock()

    def send(self, obj):
        data = (json.dumps(obj) + "\n").encode("utf-8")
        with self.lock:
            self.sock.sendall(data)


def client_reader(conn, buf=b""):
    sock = conn.sock
    try:
        while True:
            chunk = sock.recv(131072)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line.decode("utf-8"))
                except ValueError:
                    continue
                t = msg.get("type")
                if t == "status":
                    events.put(("status", conn.cid,
                                {"window": msg.get("window", ""), "app": msg.get("app", ""),
                                 "url": msg.get("url", "")}))
                elif t == "screenshot":
                    events.put(("screenshot", conn.cid, {"data": msg.get("data", "")}))
    except OSError:
        pass
    finally:
        with clients_lock:
            clients.pop(conn.cid, None)
        try:
            sock.close()
        except OSError:
            pass
        events.put(("gone", conn.cid, {}))


def handle_new(sock, addr):
    try:
        # TCP keep-alive: o'lik ulanish (kompyuter o'chib qolsa) tez aniqlanadi.
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 10000, 3000))
        except (OSError, AttributeError):
            pass
        sock.settimeout(10)
        buf = b""
        while b"\n" not in buf:
            chunk = sock.recv(4096)
            if not chunk:
                sock.close()
                return
            buf += chunk
        line, rest = buf.split(b"\n", 1)
        hello = json.loads(line.decode("utf-8"))
        if hello.get("type") != "hello" or hello.get("token") != CFG["token"]:
            sock.close()
            return
        sock.settimeout(None)
        new_name = hello.get("name") or addr[0]
        old_socks = []
        with clients_lock:
            # Shu nomli eski (stale) ulanishlarni topamiz — bu kompyuter qayta ulanyapti.
            for oc in clients.values():
                if oc.name == new_name:
                    old_socks.append(oc.sock)
            cid = _next_id[0]
            _next_id[0] += 1
            conn = ClientConn(sock, addr, cid)
            conn.name = new_name
            clients[cid] = conn
        events.put(("hello", cid, {"name": conn.name, "ip": addr[0]}))
        # Eski ulanishlarni yopamiz: ularning reader thread'i "gone" beradi va eski katak o'chadi.
        for osk in old_socks:
            try:
                osk.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                osk.close()
            except OSError:
                pass
        client_reader(conn, rest)
    except (OSError, ValueError):
        try:
            sock.close()
        except OSError:
            pass


def accept_loop():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", CFG["port"]))
    srv.listen(60)
    while True:
        sock, addr = srv.accept()
        threading.Thread(target=handle_new, args=(sock, addr), daemon=True).start()


# ======================== GUI ========================
THUMB_W = 240
GRID_COLS = 4


class ServerGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Imtihon nazorati — O'qituvchi serveri")
        self.root.geometry("1100x700")
        self.allowed = []
        self.blocked = []
        self.photos = {}        # cid -> thumbnail PhotoImage (reference saqlash)
        self.cells = {}         # cid -> {frame,img_label,name_label}
        self.cell_order = []
        self.big = {}           # cid -> {win,label,photo}
        self.control = {}       # cid -> {win,label,photo,dw,dh,lastmove}
        self.sharing = False    # ekran ulashish holati
        self.share_all = False
        self.share_cids = None
        self.audio_on = False   # mikrofon eshittirish holati
        self.log_file = None
        self.log_writer = None
        self.log_path = None

        ip = get_lan_ip()
        top = tk.Frame(self.root, pady=4)
        top.pack(fill="x")
        tk.Label(top, text=f"Server: {ip} : {CFG['port']}  (avtomatik topish yoqilgan)",
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=8)

        flt = tk.Frame(self.root)
        flt.pack(fill="x", padx=8)
        tk.Label(flt, text="Ruxsat etilgan (oyna/sayt kalit so'zlari):").grid(row=0, column=0, sticky="w")
        self.allow_entry = tk.Entry(flt, width=46)
        self.allow_entry.grid(row=0, column=1, padx=4, pady=2)
        tk.Label(flt, text="Bloklangan saytlar/kalitlar:").grid(row=1, column=0, sticky="w")
        self.block_entry = tk.Entry(flt, width=46)
        self.block_entry.grid(row=1, column=1, padx=4, pady=2)
        tk.Button(flt, text="Saqlash", command=self.save_filters).grid(row=0, column=2, rowspan=2, padx=6, sticky="ns")

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=6, pady=4)
        self.tab_list = tk.Frame(nb)
        self.tab_screens = tk.Frame(nb)
        nb.add(self.tab_list, text="  Nazorat / Ro'yxat  ")
        nb.add(self.tab_screens, text="  Ekranlar  ")

        self._build_list_tab()
        self._build_screens_tab()

        self.start_new_log()
        self.root.after(200, self.poll)

    # ---------- Tab 1: ro'yxat ----------
    def _build_list_tab(self):
        cols = ("name", "ip", "window", "url", "app", "status", "seen")
        self.tree = ttk.Treeview(self.tab_list, columns=cols, show="headings", height=12)
        for c, t, w in [("name", "Talaba / Kompyuter", 170), ("ip", "IP", 100),
                        ("window", "Faol oyna", 210), ("url", "URL / sayt", 210),
                        ("app", "Dastur", 115), ("status", "Holat", 90), ("seen", "Oxirgi", 65)]:
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w)
        self.tree.tag_configure("bad", background="#ffd6d6")
        self.tree.tag_configure("ok", background="#d9ffd9")
        self.tree.pack(fill="both", expand=True, padx=6, pady=4)

        btns = tk.Frame(self.tab_list, pady=4)
        btns.pack(fill="x")
        tk.Button(btns, text="🔒 Tanlangan", command=lambda: self.lock(False)).pack(side="left", padx=3)
        tk.Button(btns, text="🔒 HAMMASI", command=lambda: self.lock(True)).pack(side="left", padx=3)
        tk.Button(btns, text="🔓 Tanlangan", command=lambda: self.unlock(False)).pack(side="left", padx=3)
        tk.Button(btns, text="🔓 HAMMASI", command=lambda: self.unlock(True)).pack(side="left", padx=3)
        tk.Button(btns, text="🖱 Boshqarish", command=self.control_selected).pack(side="left", padx=3)
        tk.Button(btns, text="🖼 Fon (tanlangan)", command=lambda: self.wallpaper(False)).pack(side="left", padx=3)
        tk.Button(btns, text="🖼 Fon (hammaga)", command=lambda: self.wallpaper(True)).pack(side="left", padx=3)
        tk.Button(btns, text="✉ Xabar (tanlangan)", command=lambda: self.message(False)).pack(side="left", padx=3)
        tk.Button(btns, text="✉ Xabar (hammaga)", command=lambda: self.message(True)).pack(side="left", padx=3)
        tk.Button(btns, text="🗒 Yangi jurnal", command=self.start_new_log).pack(side="left", padx=3)

        btns2 = tk.Frame(self.tab_list, pady=2)
        btns2.pack(fill="x")
        tk.Button(btns2, text="📺 Ekran ulash (tanlangan)", command=lambda: self.start_share(False)).pack(side="left", padx=3)
        tk.Button(btns2, text="📺 Ekran ulash (hammaga)", command=lambda: self.start_share(True)).pack(side="left", padx=3)
        tk.Button(btns2, text="⏹ Ulashni to'xtatish", command=self.stop_share).pack(side="left", padx=3)
        self.audio_btn = tk.Button(btns2, text="🎤 Mikrofon: OFF", command=self.toggle_audio)
        self.audio_btn.pack(side="left", padx=12)

        tk.Label(self.tab_list, text="Hodisalar jurnali:", anchor="w").pack(fill="x", padx=6)
        lf = tk.Frame(self.tab_list)
        lf.pack(fill="both", expand=False, padx=6, pady=(0, 6))
        self.log = tk.Text(lf, height=8, wrap="word")
        sb = tk.Scrollbar(lf, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)

    # ---------- Tab 2: ekranlar ----------
    def _build_screens_tab(self):
        if not HAVE_PIL:
            tk.Label(self.tab_screens,
                     text="Ekran ko'rish uchun Pillow kerak:\n\n   py -m pip install pillow",
                     font=("Segoe UI", 12), justify="center").pack(expand=True)
            return
        self.canvas = tk.Canvas(self.tab_screens, highlightthickness=0)
        vbar = ttk.Scrollbar(self.tab_screens, orient="vertical", command=self.canvas.yview)
        self.grid_frame = tk.Frame(self.canvas)
        self.grid_frame.bind("<Configure>",
                             lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=vbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")

    # ---------- allowed ----------
    def save_filters(self):
        self.allowed = [x.strip() for x in self.allow_entry.get().strip().lower().split(",") if x.strip()]
        self.blocked = [x.strip() for x in self.block_entry.get().strip().lower().split(",") if x.strip()]
        self.logline(f"Ruxsat etilgan: {self.allowed or 'cheklovsiz'} | Bloklangan: {self.blocked or 'yo‘q'}")

    def classify(self, window, app, url):
        hay = (window + " " + app + " " + url).lower()
        if self.blocked and any(b in hay for b in self.blocked):
            return False
        if self.allowed and not any(a in hay for a in self.allowed):
            return False
        return True

    # ---------- log ----------
    def start_new_log(self):
        d = os.path.join(base_dir(), CFG["log_dir"])
        os.makedirs(d, exist_ok=True)
        if self.log_file:
            try:
                self.log_file.close()
            except OSError:
                pass
        self.log_path = os.path.join(d, time.strftime("imtihon_%Y-%m-%d_%H-%M-%S.csv"))
        self.log_file = open(self.log_path, "w", newline="", encoding="utf-8-sig")
        self.log_writer = csv.writer(self.log_file)
        self.log_writer.writerow(["vaqt", "talaba", "ip", "hodisa", "tafsilot"])
        self.log_file.flush()
        self.logline(f"Yangi jurnal: {self.log_path}")

    def file_log(self, name, ip, event, detail=""):
        if self.log_writer:
            self.log_writer.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), name, ip, event, detail])
            self.log_file.flush()

    def logline(self, text):
        ts = time.strftime("%H:%M:%S")
        self.log.insert("end", f"[{ts}] {text}\n")
        self.log.see("end")

    # ---------- buyruqlar ----------
    def selected_cids(self):
        out = []
        for iid in self.tree.selection():
            try:
                out.append(int(iid))
            except ValueError:
                pass
        return out

    def targets(self, all_clients):
        with clients_lock:
            if all_clients:
                return list(clients.values())
            return [clients[c] for c in self.selected_cids() if c in clients]

    def lock(self, all_clients):
        msg = "Kompyuter o'qituvchi tomonidan vaqtincha bloklandi."
        n = 0
        for c in self.targets(all_clients):
            try:
                c.send({"cmd": "lock", "message": msg}); n += 1
            except OSError:
                pass
        self.logline(f"Bloklash yuborildi: {n} ta")

    def unlock(self, all_clients):
        n = 0
        for c in self.targets(all_clients):
            try:
                c.send({"cmd": "unlock"}); n += 1
            except OSError:
                pass
        self.logline(f"Blokdan chiqarildi: {n} ta")

    def wallpaper(self, all_clients):
        path = filedialog.askopenfilename(title="Fon rasmini tanlang",
                   filetypes=[("Rasm", "*.jpg *.jpeg *.png *.bmp"), ("Barchasi", "*.*")])
        if not path:
            return
        tgt = self.targets(all_clients)
        if not tgt:
            messagebox.showinfo("Eslatma", "Hech kim tanlanmagan / ulanmagan.")
            return
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("ascii")
        ext = os.path.splitext(path)[1] or ".jpg"
        n = 0
        for c in tgt:
            try:
                c.send({"cmd": "wallpaper", "ext": ext, "data": data}); n += 1
            except OSError:
                pass
        self.logline(f"Fon yuborildi: {n} ta")

    def message(self, all_clients):
        tgt = self.targets(all_clients)
        if not tgt:
            messagebox.showinfo("Eslatma", "Hech kim tanlanmagan / ulanmagan.")
            return
        text = simpledialog.askstring("Xabar yuborish", "Talabalarga xabar matni:", parent=self.root)
        if not text:
            return
        n = 0
        for c in tgt:
            try:
                c.send({"cmd": "message", "text": text}); n += 1
            except OSError:
                pass
        self.logline(f"Xabar yuborildi ({n} ta): {text}")

    # ---------- ekran ulashish (o'qituvchi -> talabalar) ----------
    def start_share(self, all_clients):
        if not HAVE_PIL:
            messagebox.showinfo("Eslatma", "Ekran ulash uchun Pillow kerak.")
            return
        self.share_all = all_clients
        self.share_cids = None if all_clients else self.selected_cids()
        if not all_clients and not self.share_cids:
            messagebox.showinfo("Eslatma", "Avval ro'yxatdan talaba(lar)ni tanlang.")
            return
        if self.sharing:
            return
        self.sharing = True
        threading.Thread(target=self._share_loop, daemon=True).start()
        self.logline("Ekran ulashildi" + (" (hammaga)" if all_clients else " (tanlangan)"))

    def _share_targets(self):
        with clients_lock:
            if self.share_all:
                return list(clients.values())
            return [clients[c] for c in (self.share_cids or []) if c in clients]

    def _share_loop(self):
        while self.sharing:
            t0 = time.time()
            b64 = None
            try:
                img = ImageGrab.grab()
                w, h = img.size
                img = img.convert("RGB").resize((1100, max(1, int(h * 1100 / w))))
                bio = io.BytesIO()
                img.save(bio, "JPEG", quality=45)
                b64 = base64.b64encode(bio.getvalue()).decode("ascii")
            except Exception:
                b64 = None
            if b64:
                for c in self._share_targets():
                    try:
                        c.send({"cmd": "teacher_screen", "data": b64})
                    except OSError:
                        pass
            time.sleep(max(0.0, 0.5 - (time.time() - t0)))

    def stop_share(self):
        if not self.sharing:
            return
        self.sharing = False
        for c in self._share_targets():
            try:
                c.send({"cmd": "teacher_screen_stop"})
            except OSError:
                pass
        self.logline("Ekran ulash to'xtatildi")

    # ---------- mikrofon (o'qituvchi ovozi -> talabalar) ----------
    def toggle_audio(self):
        if self.audio_on:
            self.audio_on = False
            self.audio_btn.config(text="🎤 Mikrofon: OFF")
            self.logline("Mikrofon o'chirildi")
        else:
            self.audio_on = True
            self.audio_btn.config(text="🎤 Mikrofon: ON (eshitilyapti)")
            threading.Thread(target=self._audio_loop, daemon=True).start()
            self.logline("Mikrofon yoqildi — talabalarga eshitilyapti")

    def _audio_loop(self):
        try:
            import pyaudio
        except Exception:
            self.audio_on = False
            events.put(("log", 0, {"text": "PyAudio topilmadi — ovoz ishlamaydi"}))
            return
        p = pyaudio.PyAudio()
        try:
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000,
                            input=True, frames_per_buffer=1024)
        except Exception:
            self.audio_on = False
            p.terminate()
            events.put(("log", 0, {"text": "Mikrofon ochilmadi (qurilma yo'qmi?)"}))
            return
        while self.audio_on:
            try:
                data = stream.read(1024, exception_on_overflow=False)
            except Exception:
                break
            header = struct.pack(">I", len(data))
            with audio_lock:
                socks = list(audio_socks)
            for s in socks:
                try:
                    s.sendall(header + data)
                except OSError:
                    with audio_lock:
                        if s in audio_socks:
                            audio_socks.remove(s)
        try:
            stream.stop_stream()
            stream.close()
        except Exception:
            pass
        p.terminate()

    # ---------- masofadan boshqarish ----------
    def control_selected(self):
        cids = self.selected_cids()
        if len(cids) != 1:
            messagebox.showinfo("Eslatma", "Boshqarish uchun ro'yxatdan bitta talabani tanlang.")
            return
        self.open_control(cids[0])

    def open_control(self, cid):
        if cid in self.control:
            self.control[cid]["win"].lift()
            return
        with clients_lock:
            conn = clients.get(cid)
        if not conn:
            return
        name = conn.name
        try:
            conn.send({"cmd": "control_start"})
        except OSError:
            pass
        win = tk.Toplevel(self.root)
        win.title(f"Boshqaruv — {name}")
        lbl = tk.Label(win, bg="#000", cursor="tcross")
        lbl.pack()
        tk.Label(win, text="Sichqoncha va klaviatura shu oyna orqali talabaga uzatiladi. "
                           "Yozish uchun avval rasm ustiga bosing. Oyna yopilsa — boshqaruv to'xtaydi.",
                 fg="#666").pack(pady=2)
        self.control[cid] = {"win": win, "label": lbl, "photo": None, "dw": 1, "dh": 1, "lastmove": 0.0}
        lbl.bind("<Motion>", lambda e, c=cid: self.ctrl_move(c, e))
        lbl.bind("<B1-Motion>", lambda e, c=cid: self.ctrl_move(c, e))
        lbl.bind("<ButtonPress-1>", lambda e, c=cid: self.ctrl_btn(c, e, "left", "down"))
        lbl.bind("<ButtonRelease-1>", lambda e, c=cid: self.ctrl_btn(c, e, "left", "up"))
        lbl.bind("<ButtonPress-3>", lambda e, c=cid: self.ctrl_btn(c, e, "right", "down"))
        lbl.bind("<ButtonRelease-3>", lambda e, c=cid: self.ctrl_btn(c, e, "right", "up"))
        lbl.bind("<MouseWheel>", lambda e, c=cid: self.ctrl_scroll(c, e))
        win.bind("<KeyPress>", lambda e, c=cid: self.ctrl_key(c, e))
        win.protocol("WM_DELETE_WINDOW", lambda c=cid: self.close_control(c))
        self.logline(f"Boshqaruv boshlandi: {name}")

    def _norm(self, cid, e):
        d = self.control[cid]
        return e.x / max(1, d["dw"]), e.y / max(1, d["dh"])

    def ctrl_move(self, cid, e):
        d = self.control.get(cid)
        if not d:
            return
        now = time.time()
        if now - d["lastmove"] < 0.04:
            return
        d["lastmove"] = now
        x, y = self._norm(cid, e)
        self.send_input(cid, {"kind": "move", "x": x, "y": y})

    def ctrl_btn(self, cid, e, btn, act):
        if cid not in self.control:
            return
        self.control[cid]["win"].focus_set()
        x, y = self._norm(cid, e)
        self.send_input(cid, {"kind": act, "btn": btn, "x": x, "y": y})

    def ctrl_scroll(self, cid, e):
        self.send_input(cid, {"kind": "scroll", "amount": int(e.delta)})

    def ctrl_key(self, cid, e):
        self.send_input(cid, {"kind": "key", "char": e.char, "keysym": e.keysym})

    def send_input(self, cid, payload):
        with clients_lock:
            conn = clients.get(cid)
        if conn:
            msg = {"cmd": "input"}
            msg.update(payload)
            try:
                conn.send(msg)
            except OSError:
                pass

    def close_control(self, cid, notify=True):
        d = self.control.pop(cid, None)
        if notify:
            with clients_lock:
                conn = clients.get(cid)
            if conn:
                try:
                    conn.send({"cmd": "control_stop"})
                except OSError:
                    pass
        if d:
            try:
                d["win"].destroy()
            except tk.TclError:
                pass
            self.logline(f"Boshqaruv tugadi: id={cid}")

    # ---------- ekran rasmlari ----------
    def ensure_cell(self, cid, name):
        if not HAVE_PIL or cid in self.cells:
            return
        f = tk.Frame(self.grid_frame, bd=1, relief="solid", padx=2, pady=2)
        img_lbl = tk.Label(f, text="(rasm kutilmoqda...)", width=34, height=9, bg="#222", fg="#bbb")
        img_lbl.pack()
        name_lbl = tk.Label(f, text=name, font=("Segoe UI", 9, "bold"))
        name_lbl.pack()
        img_lbl.bind("<Double-Button-1>", lambda e, c=cid: self.open_big(c))
        self.cells[cid] = {"frame": f, "img": img_lbl, "name": name_lbl, "name_text": name}
        self.cell_order.append(cid)
        self.relayout()

    def relayout(self):
        # Kataklarni kompyuter nomi bo'yicha tartiblaymiz — joyi o'zgarmay turadi.
        self.cell_order.sort(key=lambda c: (self.cells.get(c, {}).get("name_text", "").lower(), c))
        for i, cid in enumerate(self.cell_order):
            if cid in self.cells:
                self.cells[cid]["frame"].grid(row=i // GRID_COLS, column=i % GRID_COLS, padx=5, pady=5)

    def remove_cell(self, cid):
        if cid in self.cells:
            self.cells[cid]["frame"].destroy()
            del self.cells[cid]
        if cid in self.cell_order:
            self.cell_order.remove(cid)
        self.photos.pop(cid, None)
        self.relayout()

    def update_screenshot(self, cid, b64):
        if not HAVE_PIL or cid not in self.cells:
            return
        try:
            raw = base64.b64decode(b64)
            img = Image.open(io.BytesIO(raw))
        except (ValueError, OSError):
            return
        w, h = img.size
        th = img.resize((THUMB_W, max(1, int(h * THUMB_W / w))))
        photo = ImageTk.PhotoImage(th)
        self.photos[cid] = photo
        self.cells[cid]["img"].config(image=photo, text="", width=0, height=0)
        if cid in self.big:
            bw = 900
            bimg = img.resize((bw, max(1, int(h * bw / w))))
            bphoto = ImageTk.PhotoImage(bimg)
            self.big[cid]["photo"] = bphoto
            self.big[cid]["label"].config(image=bphoto)
        if cid in self.control:
            cw = 960
            cimg = img.resize((cw, max(1, int(h * cw / w))))
            cphoto = ImageTk.PhotoImage(cimg)
            d = self.control[cid]
            d["photo"] = cphoto
            d["dw"] = cphoto.width()
            d["dh"] = cphoto.height()
            d["label"].config(image=cphoto)

    def open_big(self, cid):
        if cid in self.big:
            self.big[cid]["win"].lift()
            return
        with clients_lock:
            conn = clients.get(cid)
        name = conn.name if conn else str(cid)
        win = tk.Toplevel(self.root)
        win.title(f"Ekran — {name}")
        lbl = tk.Label(win, bg="#000")
        lbl.pack(fill="both", expand=True)
        self.big[cid] = {"win": win, "label": lbl, "photo": None}
        win.protocol("WM_DELETE_WINDOW", lambda c=cid: self.close_big(c))

    def close_big(self, cid):
        if cid in self.big:
            try:
                self.big[cid]["win"].destroy()
            except tk.TclError:
                pass
            del self.big[cid]

    def sort_tree(self):
        # Ro'yxat qatorlarini kompyuter nomi bo'yicha tartiblaymiz (joyi o'zgarmaydi).
        rows = [(self.tree.set(iid, "name").lower(), iid) for iid in self.tree.get_children("")]
        rows.sort()
        for idx, (_, iid) in enumerate(rows):
            self.tree.move(iid, "", idx)

    # ---------- asosiy sikl ----------
    def poll(self):
        try:
            while True:
                kind, cid, p = events.get_nowait()
                iid = str(cid)
                if kind == "log":
                    self.logline(p.get("text", ""))
                    continue
                if kind == "hello":
                    self.tree.insert("", "end", iid=iid,
                                     values=(p["name"], p["ip"], "", "", "", "ulandi", ""), tags=("ok",))
                    self.sort_tree()
                    self.ensure_cell(cid, p["name"])
                    self.logline(f"ULANDI: {p['name']} ({p['ip']})")
                    self.file_log(p["name"], p["ip"], "ULANDI")
                elif kind == "gone":
                    with clients_lock:
                        conn = clients.get(cid)
                    if self.tree.exists(iid):
                        self.tree.delete(iid)
                    self.remove_cell(cid)
                    self.close_big(cid)
                    self.close_control(cid, notify=False)
                    self.logline(f"UZILDI: id={cid}")
                    self.file_log("", "", "UZILDI", f"id={cid}")
                elif kind == "screenshot":
                    self.update_screenshot(cid, p["data"])
                elif kind == "status":
                    if not self.tree.exists(iid):
                        continue
                    window, app, url = p["window"], p["app"], p.get("url", "")
                    ok = self.classify(window, app, url)
                    with clients_lock:
                        conn = clients.get(cid)
                    name = conn.name if conn else ""
                    ip = conn.addr[0] if conn else ""
                    was_ok = conn.ok if conn else True
                    changed = bool(conn) and (conn.window != window or conn.url != url)
                    if conn:
                        conn.window, conn.app, conn.url, conn.ok = window, app, url, ok
                    seen = time.strftime("%H:%M:%S")
                    self.tree.item(iid, values=(name, ip, window, url, app,
                                   "OK" if ok else "⚠ SHUBHALI", seen),
                                   tags=("ok" if ok else "bad",))
                    detail = f"{window} | {url} [{app}]"
                    if changed:
                        self.file_log(name, ip, "OYNA", detail)
                    if (not ok) and was_ok:
                        self.logline(f"⚠ OGOHLANTIRISH — {name}: '{window}' {url} [{app}]")
                        self.file_log(name, ip, "OGOHLANTIRISH", detail)
                        if winsound:
                            try:
                                winsound.Beep(1200, 250)
                            except RuntimeError:
                                pass
        except queue.Empty:
            pass
        self.root.after(200, self.poll)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    threading.Thread(target=accept_loop, daemon=True).start()
    threading.Thread(target=discovery_responder, daemon=True).start()
    threading.Thread(target=audio_listener, daemon=True).start()
    ServerGUI().run()
