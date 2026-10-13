"""W6 實驗 2：觀察任務上傳協定的逾時與重送（pymavlink）。

用法：vendor/venv/bin/python -u -I scripts/w6_mission_timeout.py
先執行 scripts/sitl.sh；本腳本連 tcp:127.0.0.1:5762。
做法：送 MISSION_COUNT 後完全不回應，印出飛控之後送來的每一則 MISSION_REQUEST[_INT] / MISSION_ACK 與時間，
最後（逾時之後）再回一次 MISSION_ITEM_INT，看飛控怎麼處理遲到的項目。結束時清空任務。
"""
import time

from pymavlink import mavutil

CONN = "tcp:127.0.0.1:5762"
COUNT = 3  # 宣告的任務項目數
WATCH_SECONDS = 20  # 不回應時觀察幾秒
T = mavutil.mavlink  # T：MAVLink 常數的命名空間，只為了縮短下面的名稱
# m：MAVLink 連線；m.mav.*_send 送出訊息，m.recv_match 接收訊息
m = mavutil.mavlink_connection(CONN)
m.wait_heartbeat(timeout=10)
t0 = time.time()  # 腳本開始時刻


def log(msg):
    print(f"[{time.time() - t0:5.1f}s] {msg}")


def drain(seconds):
    """印出接下來 seconds 秒內收到的任務協定訊息與 STATUSTEXT。"""
    end = time.time() + seconds
    while time.time() < end:
        msg = m.recv_match(type=["MISSION_REQUEST", "MISSION_REQUEST_INT", "MISSION_ACK", "STATUSTEXT"],
                           blocking=True, timeout=0.5)
        if msg is None:
            continue
        if msg.get_type() == "STATUSTEXT":
            log(f"STATUSTEXT：{msg.text}")
        elif msg.get_type() == "MISSION_ACK":
            log(f"MISSION_ACK type={msg.type}")
        else:
            log(f"{msg.get_type()} seq={msg.seq}")


m.mav.mission_clear_all_send(m.target_system, m.target_component)
m.recv_match(type="MISSION_ACK", blocking=True, timeout=5)
m.mav.mission_count_send(m.target_system, m.target_component, COUNT)
log(f"送出 MISSION_COUNT = {COUNT}，之後不回應")
drain(WATCH_SECONDS)

# 遲到的項目：第 0 項（home 位置，內容隨便填）
log("逾時後才回 MISSION_ITEM_INT seq=0")
m.mav.mission_item_int_send(m.target_system, m.target_component, 0, T.MAV_FRAME_GLOBAL,
                            T.MAV_CMD_NAV_WAYPOINT, 0, 1, 0, 0, 0, 0, 0, 0, 0)
drain(5)

m.mav.mission_clear_all_send(m.target_system, m.target_component)
ack = m.recv_match(type="MISSION_ACK", blocking=True, timeout=5)
log(f"清空任務：{'無回應' if ack is None else f'MISSION_ACK type={ack.type}'}")
