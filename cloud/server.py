# -*- coding: utf-8 -*-
"""
IMTIHON NAZORATI — BULUTLI RELAY SERVER
=======================================
Bitta HTTP port orqali ishlaydi (Render / Railway / VPS uchun mos).

  * O'qituvchi paneli  -> brauzerda  (GET  /          )
  * O'qituvchi WS      ->            (     /ws/teacher )
  * Talaba klienti WS  ->            (     /ws/student )
  * Sog'liqni tekshirish ->          (GET  /healthz    )

Server faqat "relay" (xabar uzatuvchi) vazifasini bajaradi — hech narsa
diskka yozilmaydi, hech qanday ma'lumot saqlanmaydi. Barcha xabarlar
o'qituvchi va talabalar o'rtasida real vaqtda uzatiladi.

XAVFSIZLIK:
  * token  — begona ulanmasligi uchun maxfiy so'z (server va mijozlarda bir xil).
  * room   — sinf kodi: har bir sinf o'z xonasida, bir-biriga aralashmaydi.
  * Render HTTPS/WSS beradi — trafik shifrlangan (LAN versiyasidan xavfsizroq).

Sozlash (muhit o'zgaruvchilari / environment variables):
  EXAM_TOKEN   — umumiy maxfiy token (default: "change-me")
  PORT         — Render avtomatik beradi (default: 8080)
"""

import os
import json
import asyncio
import time
from aiohttp import web, WSMsgType

TOKEN = os.environ.get("EXAM_TOKEN", "change-me")
PORT = int(os.environ.get("PORT", "8080"))

# Bitta talaba rasmi uchun eng katta hajm (himoya chegarasi) ~2 MB base64.
MAX_MSG = 3 * 1024 * 1024


# ============================================================
#  Xona (room) holati — xotirada, disksiz
# ============================================================
class Student:
    _seq = 0

    def __init__(self, ws, name):
        Student._seq += 1
        self.sid = Student._seq
        self.ws = ws
        self.name = name or f"PC-{self.sid}"
        self.window = ""
        self.app = ""
        self.url = ""
        self.joined = time.time()

    def info(self):
        return {"sid": self.sid, "name": self.name,
                "window": self.window, "app": self.app, "url": self.url}


class Room:
    def __init__(self, code):
        self.code = code
        self.teachers = set()        # o'qituvchi WS lari
        self.students = {}           # sid -> Student

    def empty(self):
        return not self.teachers and not self.students


ROOMS = {}


def get_room(code):
    r = ROOMS.get(code)
    if r is None:
        r = Room(code)
        ROOMS[code] = r
    return r


def drop_room_if_empty(code):
    r = ROOMS.get(code)
    if r and r.empty():
        ROOMS.pop(code, None)


async def send_json(ws, obj):
    try:
        await ws.send_str(json.dumps(obj, ensure_ascii=False))
        return True
    except (ConnectionResetError, RuntimeError):
        return False


async def broadcast_teachers(room, obj):
    dead = []
    for tws in list(room.teachers):
        if not await send_json(tws, obj):
            dead.append(tws)
    for d in dead:
        room.teachers.discard(d)


# ============================================================
#  Talaba klienti WebSocket
# ============================================================
async def ws_student(request):
    token = request.query.get("token", "")
    room_code = request.query.get("room", "").strip()
    name = request.query.get("name", "").strip()

    ws = web.WebSocketResponse(heartbeat=30, max_msg_size=MAX_MSG)
    await ws.prepare(request)

    if token != TOKEN or not room_code:
        await send_json(ws, {"type": "error", "reason": "auth"})
        await ws.close()
        return ws

    room = get_room(room_code)
    stu = Student(ws, name)
    room.students[stu.sid] = stu

    # O'qituvchilarga "ulandi" xabari
    await broadcast_teachers(room, {"type": "join", **stu.info()})
    await send_json(ws, {"type": "welcome", "sid": stu.sid})

    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                if msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                    break
                continue
            try:
                data = json.loads(msg.data)
            except ValueError:
                continue
            t = data.get("type")
            if t == "status":
                stu.window = data.get("window", "")
                stu.app = data.get("app", "")
                stu.url = data.get("url", "")
                await broadcast_teachers(room, {"type": "status", **stu.info()})
            elif t == "screenshot":
                await broadcast_teachers(room, {
                    "type": "screenshot", "sid": stu.sid, "data": data.get("data", "")})
    except asyncio.CancelledError:
        pass
    finally:
        room.students.pop(stu.sid, None)
        await broadcast_teachers(room, {"type": "leave", "sid": stu.sid})
        drop_room_if_empty(room_code)
    return ws


# ============================================================
#  O'qituvchi paneli WebSocket
# ============================================================
async def ws_teacher(request):
    token = request.query.get("token", "")
    room_code = request.query.get("room", "").strip()

    ws = web.WebSocketResponse(heartbeat=30, max_msg_size=MAX_MSG)
    await ws.prepare(request)

    if token != TOKEN or not room_code:
        await send_json(ws, {"type": "error", "reason": "auth"})
        await ws.close()
        return ws

    room = get_room(room_code)
    room.teachers.add(ws)

    # Hozirgi talabalar ro'yxatini yuboramiz (panel qayta tiklanishi uchun)
    await send_json(ws, {"type": "roster",
                         "students": [s.info() for s in room.students.values()]})

    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                if msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                    break
                continue
            try:
                data = json.loads(msg.data)
            except ValueError:
                continue
            await route_teacher_command(room, data)
    except asyncio.CancelledError:
        pass
    finally:
        room.teachers.discard(ws)
        drop_room_if_empty(room_code)
    return ws


# Panel yuboradigan buyruqni mos talaba(lar)ga klient tushunadigan {cmd:...}
# ko'rinishida uzatamiz (klient protokoli LAN versiyasi bilan bir xil).
CMD_MAP = {
    "lock": lambda d: {"cmd": "lock", "message": d.get("message", "")},
    "unlock": lambda d: {"cmd": "unlock"},
    "message": lambda d: {"cmd": "message", "text": d.get("text", "")},
    "control_start": lambda d: {"cmd": "control_start"},
    "control_stop": lambda d: {"cmd": "control_stop"},
    "input": lambda d: {"cmd": "input", **{k: v for k, v in d.items()
                                           if k not in ("type", "sid", "all")}},
}


async def route_teacher_command(room, data):
    t = data.get("type")
    builder = CMD_MAP.get(t)
    if not builder:
        return
    payload = builder(data)

    if data.get("all"):
        targets = list(room.students.values())
    else:
        sid = data.get("sid")
        stu = room.students.get(sid)
        targets = [stu] if stu else []

    for stu in targets:
        await send_json(stu.ws, payload)


# ============================================================
#  O'qituvchi paneli (statik HTML)
# ============================================================
async def index(request):
    html_path = os.path.join(os.path.dirname(__file__), "panel.html")
    return web.FileResponse(html_path)


async def healthz(request):
    total_students = sum(len(r.students) for r in ROOMS.values())
    return web.json_response({"ok": True, "rooms": len(ROOMS),
                              "students": total_students})


def make_app():
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/healthz", healthz)
    app.router.add_get("/ws/student", ws_student)
    app.router.add_get("/ws/teacher", ws_teacher)
    return app


if __name__ == "__main__":
    print(f"Imtihon nazorati relay serveri — port {PORT}")
    print(f"Token o'rnatilgan: {'HA' if TOKEN != 'change-me' else 'YO`Q (change-me)'}")
    web.run_app(make_app(), host="0.0.0.0", port=PORT)
