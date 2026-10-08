"""W4 實驗 2：比較 REQUEST_DATA_STREAM 與 SET_MESSAGE_INTERVAL 實際得到的速率。

同一條連線依序做六個階段，每階段量 4 秒，印出 ATTITUDE、GLOBAL_POSITION_INT、LOCAL_POSITION_NED 的實際 Hz。
REQUEST_DATA_STREAM 以「群組」為單位（ATTITUDE 在 EXTRA1，位置類在 POSITION）；
SET_MESSAGE_INTERVAL 以單一訊息為單位。看兩者混用時誰蓋過誰。
速率設定會留在 SITL 的連接埠上、斷線也不會消失，所以開頭先重設，不必重啟 SITL；
先執行 scripts/sitl.sh；
用法：vendor/venv/bin/python -u -I scripts/w4_rates.py
"""
import time

from pymavlink import mavutil

mav = mavutil.mavlink  # MAVLink 的常數與訊息編號都在這個模組裡
NAMES = ["ATTITUDE", "GLOBAL_POSITION_INT", "LOCAL_POSITION_NED"]
WINDOW = 4.0

# m：MAVLink 連線；m.mav.*_send 送出訊息，m.recv_match 接收訊息
m = mavutil.mavlink_connection("tcp:127.0.0.1:5762")
m.wait_heartbeat(timeout=10)


def stream(stream_id, hz):
    """REQUEST_DATA_STREAM：以群組為單位；hz = 0 表示停止。"""
    m.mav.request_data_stream_send(m.target_system, m.target_component, stream_id, hz, 1 if hz else 0)


def interval(name, hz):
    """SET_MESSAGE_INTERVAL：單一訊息；hz = -1 表示停止，0 表示還原預設。"""
    mid = getattr(mav, f"MAVLINK_MSG_ID_{name}")  # mid：message id，訊息編號
    us = int(1e6 / hz) if hz > 0 else hz  # us：間隔（微秒）；-1 表示停止，0 表示還原預設
    m.mav.command_long_send(m.target_system, m.target_component, mav.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
                            mid, us, 0, 0, 0, 0, 0)


def measure():
    counts = dict.fromkeys(NAMES, 0)
    start = time.time()
    while time.time() - start < WINDOW:
        msg = m.recv_match(type=NAMES, blocking=True, timeout=1)  # 要持續讀取，否則 SITL 會卡住
        if msg is not None:
            counts[msg.get_type()] += 1
    return {k: v / WINDOW for k, v in counts.items()}


def reset():
    """清掉上次實驗留下的速率：停掉所有串流群組，並把三種訊息的間隔還原成預設。"""
    stream(mav.MAV_DATA_STREAM_ALL, 0)
    for name in NAMES:
        interval(name, 0)
    time.sleep(1)


reset()
stages = [
    ("0. 什麼都不要", lambda: None),
    ("1. DATA_STREAM EXTRA1 → 4 Hz", lambda: stream(mav.MAV_DATA_STREAM_EXTRA1, 4)),
    ("2. DATA_STREAM EXTRA1 → 20 Hz", lambda: stream(mav.MAV_DATA_STREAM_EXTRA1, 20)),
    ("3. 再加 INTERVAL ATTITUDE → 10 Hz", lambda: interval("ATTITUDE", 10)),
    ("4. DATA_STREAM POSITION → 2 Hz", lambda: stream(mav.MAV_DATA_STREAM_POSITION, 2)),
    ("5. 再加 INTERVAL GLOBAL_POSITION_INT → 10 Hz", lambda: interval("GLOBAL_POSITION_INT", 10)),
]

print(f"{'階段':<46}" + "".join(f"{n:>22}" for n in NAMES))
for label, action in stages:
    action()
    time.sleep(0.5)  # 讓新設定生效，並丟掉換速率瞬間的暫態
    rates = measure()
    print(f"{label:<44}" + "".join(f"{rates[n]:>19.1f} Hz" for n in NAMES))
