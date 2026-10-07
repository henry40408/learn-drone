"""W4 實驗 1：持續接收 ATTITUDE 與 GLOBAL_POSITION_INT，每秒印出實際頻率與最新值。

先執行 scripts/sitl.sh；用法：vendor/venv/bin/python -u -I scripts/w4_telemetry.py [秒數]
5762 預設只送 HEARTBEAT，所以先用 SET_MESSAGE_INTERVAL 要求 ATTITUDE 10 Hz、GLOBAL_POSITION_INT 5 Hz（預設跑 10 秒）。
"""
import math
import sys
import time

from pymavlink import mavutil

DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0

m = mavutil.mavlink_connection("tcp:127.0.0.1:5762")
m.wait_heartbeat(timeout=10)
print(f"連線 system={m.target_system} component={m.target_component}")

for name, hz in (("ATTITUDE", 10), ("GLOBAL_POSITION_INT", 5)):
    mid = getattr(mavutil.mavlink, f"MAVLINK_MSG_ID_{name}")
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0, mid, int(1e6 / hz), 0, 0, 0, 0, 0)

counts = {"ATTITUDE": 0, "GLOBAL_POSITION_INT": 0}
latest = {}
start = last_print = time.time()

while time.time() - start < DURATION:
    msg = m.recv_match(type=list(counts), blocking=True, timeout=1)  # 要持續讀取，否則 SITL 會卡住
    if msg is not None:
        t = msg.get_type()
        counts[t] += 1
        latest[t] = msg
    now = time.time()
    if now - last_print >= 1.0 and len(latest) == len(counts):
        dt = now - last_print
        a, p = latest["ATTITUDE"], latest["GLOBAL_POSITION_INT"]
        print(f"ATTITUDE {counts['ATTITUDE'] / dt:5.1f} Hz  "
              f"roll={math.degrees(a.roll):6.2f}° pitch={math.degrees(a.pitch):6.2f}° "
              f"yaw={math.degrees(a.yaw):7.2f}° | "
              f"GLOBAL_POSITION_INT {counts['GLOBAL_POSITION_INT'] / dt:5.1f} Hz  "
              f"lat={p.lat / 1e7:.6f} lon={p.lon / 1e7:.6f} "
              f"alt={p.alt / 1000:.1f}m rel={p.relative_alt / 1000:.1f}m")
        counts = dict.fromkeys(counts, 0)
        last_print = now
