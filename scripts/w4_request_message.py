"""W4 實驗：REQUEST_MESSAGE（指令 512）只要一次，不會持續推送。

先把 ATTITUDE 停掉，再各送 REQUEST_MESSAGE 一次，觀察 COMMAND_ACK 與收到的訊息筆數；
另外要一次平常不會主動送的 AUTOPILOT_VERSION（固件版本）。
先執行 scripts/sitl.sh；用法：vendor/venv/bin/python -u -I scripts/w4_request_message.py
"""
import time

from pymavlink import mavutil

mav = mavutil.mavlink  # MAVLink 的常數與訊息編號都在這個模組裡
WINDOW = 3.0  # 每次觀察的秒數

# m：MAVLink 連線；m.mav.*_send 送出訊息，m.recv_match 接收訊息
m = mavutil.mavlink_connection("tcp:127.0.0.1:5762")
m.wait_heartbeat(timeout=10)


def command(cmd, *params):
    """送 COMMAND_LONG；params 最多 7 個，不足補 0。"""
    m.mav.command_long_send(m.target_system, m.target_component, cmd, 0,
                            *(list(params) + [0] * (7 - len(params))))


def message_id(name):
    return getattr(mav, f"MAVLINK_MSG_ID_{name}")  # 訊息編號


def observe(name):
    """觀察 WINDOW 秒，回傳 (COMMAND_ACK 的結果或 None, 收到的 name 訊息列表, 第一筆延遲秒數)。"""
    acks, got, first = [], [], None
    start = time.time()
    while time.time() - start < WINDOW:
        msg = m.recv_match(type=["COMMAND_ACK", name], blocking=True, timeout=0.5)
        if msg is None:
            continue
        if msg.get_type() == "COMMAND_ACK":
            acks.append(msg)
        else:
            got.append(msg)
            first = first if first is not None else time.time() - start
    return acks, got, first


def request_once(name):
    command(mav.MAV_CMD_REQUEST_MESSAGE, message_id(name))
    return observe(name)


# 停掉所有持續推送，讓「收到幾筆」只反映 REQUEST_MESSAGE
m.mav.request_data_stream_send(m.target_system, m.target_component, mav.MAV_DATA_STREAM_ALL, 0, 0)
command(mav.MAV_CMD_SET_MESSAGE_INTERVAL, message_id("ATTITUDE"), -1)  # -1 表示停止
time.sleep(1)
while m.recv_match(blocking=False):  # 丟掉緩衝區裡剩下的
    pass

print("== 沒要求時：觀察 3 秒 ==")
_, got, _ = observe("ATTITUDE")
print(f"ATTITUDE 收到 {len(got)} 筆")

print("\n== REQUEST_MESSAGE ATTITUDE 一次 ==")
acks, got, first = request_once("ATTITUDE")
print(f"COMMAND_ACK：{[(a.command, a.result) for a in acks]}（result 0 = ACCEPTED）")
print(f"ATTITUDE 收到 {len(got)} 筆，第一筆在 {first:.3f} 秒後" if got else "ATTITUDE 收到 0 筆")

print("\n== 再要一次 ==")
acks, got, _ = request_once("ATTITUDE")
print(f"COMMAND_ACK {len(acks)} 個；ATTITUDE 收到 {len(got)} 筆")

print("\n== REQUEST_MESSAGE AUTOPILOT_VERSION（平常不會主動送）==")
acks, got, _ = request_once("AUTOPILOT_VERSION")
print(f"COMMAND_ACK：{[(a.command, a.result) for a in acks]}")
if got:
    v = got[0].flight_sw_version  # v：固件版本，4 個位元組，依序是 major、minor、patch、type
    print(f"固件版本 {v >> 24}.{(v >> 16) & 0xFF}.{(v >> 8) & 0xFF}（type 位元組 {v & 0xFF}）")
else:
    print("沒收到 AUTOPILOT_VERSION")
