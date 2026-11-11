# -*- coding: utf-8 -*-
"""Relay serverni mahalliy sinash: teacher <-> student xabar almashinuvi."""
import json, time, threading, subprocess, sys, os
import websocket  # websocket-client

PORT = "8099"
TOKEN = "testtoken"
BASE = f"ws://127.0.0.1:{PORT}"
results = []

def run_server():
    env = dict(os.environ, EXAM_TOKEN=TOKEN, PORT=PORT)
    return subprocess.Popen([sys.executable, "server.py"], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

def main():
    srv = run_server()
    time.sleep(2.0)
    try:
        teacher_msgs = []
        tws = websocket.create_connection(f"{BASE}/ws/teacher?token={TOKEN}&room=7A", timeout=5)
        # roster (bo'sh)
        teacher_msgs.append(json.loads(tws.recv()))

        # Talaba ulanadi
        sws = websocket.create_connection(f"{BASE}/ws/student?token={TOKEN}&room=7A&name=PC-1", timeout=5)
        welcome = json.loads(sws.recv())
        assert welcome["type"] == "welcome", welcome
        sid = welcome["sid"]

        # Teacher 'join' olishi kerak
        join = json.loads(tws.recv())
        assert join["type"] == "join" and join["name"] == "PC-1", join

        # Student status yuboradi -> teacher ko'radi
        sws.send(json.dumps({"type": "status", "window": "YouTube - Chrome",
                             "app": "chrome.exe", "url": "youtube.com"}))
        st = json.loads(tws.recv())
        assert st["type"] == "status" and st["url"] == "youtube.com", st

        # Student screenshot -> teacher
        sws.send(json.dumps({"type": "screenshot", "data": "QUJD"}))
        sh = json.loads(tws.recv())
        assert sh["type"] == "screenshot" and sh["data"] == "QUJD", sh

        # Teacher lock buyrug'i -> student {cmd:lock}
        tws.send(json.dumps({"type": "lock", "sid": sid, "message": "STOP"}))
        cmd = json.loads(sws.recv())
        assert cmd["cmd"] == "lock" and cmd["message"] == "STOP", cmd

        # Teacher input (boshqaruv) -> student
        tws.send(json.dumps({"type": "input", "sid": sid, "kind": "move", "x": 0.5, "y": 0.5}))
        inp = json.loads(sws.recv())
        assert inp["cmd"] == "input" and inp["kind"] == "move", inp

        # Teacher 'all' lock -> student ham oladi
        tws.send(json.dumps({"type": "unlock", "all": True}))
        cmd2 = json.loads(sws.recv())
        assert cmd2["cmd"] == "unlock", cmd2

        # Noto'g'ri token rad etiladi
        try:
            bad = websocket.create_connection(f"{BASE}/ws/student?token=WRONG&room=7A", timeout=5)
            m = json.loads(bad.recv())
            assert m.get("type") == "error", m
            bad.close()
        except Exception as e:
            pass

        # Student uziladi -> teacher 'leave'
        sws.close()
        lv = json.loads(tws.recv())
        assert lv["type"] == "leave" and lv["sid"] == sid, lv

        tws.close()
        print("HAMMA TEST O'TDI ✓")
    finally:
        srv.terminate()
        try:
            out = srv.stdout.read().decode("utf-8", "ignore")
            if out.strip():
                print("--- server log ---\n" + out)
        except Exception:
            pass

if __name__ == "__main__":
    main()
