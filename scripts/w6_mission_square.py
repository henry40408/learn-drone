"""W6 實驗 1：上傳正方形任務（pymavlink），切 AUTO 執行，觀察進度直到降落。

用法：vendor/venv/bin/python -u -I scripts/w6_mission_square.py
先執行 scripts/sitl.sh；本腳本連 tcp:127.0.0.1:5762。
任務：起飛 10 m → 四個角（北 20 m 起順時針）→ RTL。座標以腳本啟動時飛機的位置為 home。
上傳流程：MISSION_COUNT → 飛控逐項要（MISSION_REQUEST[_INT]）→ 回 MISSION_ITEM_INT → MISSION_ACK。
"""
import math
import time

from pymavlink import mavutil

CONN = "tcp:127.0.0.1:5762"
ALT = 10  # 起飛與航點高度，公尺（相對 home）
SIDE = 20  # 正方形邊長，公尺
M_PER_DEG_LAT = 111_320  # 每度緯度約幾公尺（近似值）
AUTO = 3  # ArduCopter 的 AUTO 模式編號
GUIDED = 4  # ArduCopter 的 GUIDED 模式編號
MISSION_TIMEOUT = 300  # 任務最多等幾秒

T = mavutil.mavlink  # T：MAVLink 常數的命名空間，只為了縮短下面的名稱
# m：MAVLink 連線；m.mav.*_send 送出訊息，m.recv_match 接收訊息
m = mavutil.mavlink_connection(CONN)
m.wait_heartbeat(timeout=10)
m.mav.request_data_stream_send(m.target_system, m.target_component, T.MAV_DATA_STREAM_ALL, 10, 1)
t0 = time.time()  # 腳本開始時刻


def log(msg):
    print(f"[{time.time() - t0:5.1f}s] {msg}")


def command(cmd, *params):
    """送 COMMAND_LONG 並等 COMMAND_ACK；回傳 result（0 = ACCEPTED）。"""
    p = list(params) + [0] * (7 - len(params))  # p：補滿 7 個的 COMMAND_LONG 參數（param1–param7）
    m.mav.command_long_send(m.target_system, m.target_component, cmd, 0, *p)
    ack = m.recv_match(type="COMMAND_ACK", condition=f"COMMAND_ACK.command=={cmd}",
                       blocking=True, timeout=5)
    return None if ack is None else ack.result


def set_mode(mode):
    m.mav.set_mode_send(m.target_system, T.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, mode)
    hb = m.recv_match(type="HEARTBEAT", condition=f"HEARTBEAT.custom_mode=={mode}", blocking=True, timeout=5)
    if hb is None:
        raise SystemExit(f"切換模式 {mode} 失敗")


# 1. 目前位置當作 home
g = m.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=10)  # g：GLOBAL_POSITION_INT 訊息
if g is None:
    raise SystemExit("收不到 GLOBAL_POSITION_INT")
lat0, lon0 = g.lat / 1e7, g.lon / 1e7  # home 的緯度、經度，度
alt0 = g.alt / 1000  # home 的海拔（AMSL），公尺
log(f"home：{lat0:.6f}, {lon0:.6f}，海拔 {alt0:.1f} m")


def offset(north, east):
    """home 往北 north 公尺、往東 east 公尺的 (緯度, 經度)，單位 1e7 度（MISSION_ITEM_INT 的格式）。"""
    lat = lat0 + north / M_PER_DEG_LAT
    lon = lon0 + east / (M_PER_DEG_LAT * math.cos(math.radians(lat0)))
    return int(lat * 1e7), int(lon * 1e7)


# 2. 任務清單：(command, lat, lon, alt)；frame 除了第 0 項外都用相對 home 的高度
corners = [offset(SIDE, 0), offset(SIDE, SIDE), offset(0, SIDE), offset(0, 0)]
home_lat, home_lon = offset(0, 0)
items = [
    (T.MAV_CMD_NAV_WAYPOINT, T.MAV_FRAME_GLOBAL, home_lat, home_lon, alt0),  # 第 0 項：home
    (T.MAV_CMD_NAV_TAKEOFF, T.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, 0, 0, ALT),
]
items += [(T.MAV_CMD_NAV_WAYPOINT, T.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, la, lo, ALT) for la, lo in corners]
items += [(T.MAV_CMD_NAV_RETURN_TO_LAUNCH, T.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, 0, 0, 0)]
NAMES = {T.MAV_CMD_NAV_WAYPOINT: "WAYPOINT", T.MAV_CMD_NAV_TAKEOFF: "TAKEOFF",
         T.MAV_CMD_NAV_RETURN_TO_LAUNCH: "RTL"}  # 只用來印 log

# 3. 上傳：先清空，再依協定逐項回應
m.mav.mission_clear_all_send(m.target_system, m.target_component)
m.recv_match(type="MISSION_ACK", blocking=True, timeout=5)
m.mav.mission_count_send(m.target_system, m.target_component, len(items))
log(f"MISSION_COUNT：{len(items)} 項")
deadline = time.time() + 30  # 上傳最多等幾秒
while True:
    msg = m.recv_match(type=["MISSION_REQUEST_INT", "MISSION_REQUEST", "MISSION_ACK"],
                       blocking=True, timeout=5)
    if msg is None or time.time() > deadline:
        raise SystemExit("上傳逾時：飛控沒有回應")
    if msg.get_type() == "MISSION_ACK":
        if msg.type != T.MAV_MISSION_ACCEPTED:
            raise SystemExit(f"上傳失敗：MISSION_ACK type={msg.type}")
        log("上傳完成：MISSION_ACK ACCEPTED")
        break
    seq = msg.seq  # seq：飛控現在要第幾項
    cmd, frame, lat, lon, alt = items[seq]
    log(f"  收到 {msg.get_type()} seq={seq} → 回 {NAMES[cmd]}")
    m.mav.mission_item_int_send(m.target_system, m.target_component, seq, frame, cmd,
                                0, 1, 0, 0, 0, 0, lat, lon, alt)  # current=0、autocontinue=1、param1–4=0

# 4. GUIDED 下 arm（EKF 還沒準備好會被拒絕，所以重試），再切 AUTO
set_mode(GUIDED)
for _ in range(30):
    result = command(T.MAV_CMD_COMPONENT_ARM_DISARM, 1)
    if result == 0:
        break
    log(f"arm 被拒絕（result={result}），1 秒後重試")
    time.sleep(1)
else:
    raise SystemExit("arm 失敗")
log("已 arm")
set_mode(AUTO)
# 在地面上切到 AUTO 不會自己起飛（約 10 秒後還會因為沒起飛而自動 disarm），要再送 MISSION_START
log(f"模式：AUTO；MISSION_START 結果：{command(T.MAV_CMD_MISSION_START, 0, 0)}")

# 5. 觀察進度：MISSION_CURRENT（目前第幾項）、MISSION_ITEM_REACHED（到了第幾項）、直到 disarm
end = time.time() + MISSION_TIMEOUT
current = None  # 目前執行第幾項
while time.time() < end:
    msg = m.recv_match(type=["MISSION_CURRENT", "MISSION_ITEM_REACHED", "HEARTBEAT"],
                       blocking=True, timeout=1)
    if msg is None:
        continue
    t = msg.get_type()
    if t == "MISSION_CURRENT" and msg.seq != current:
        current = msg.seq
        log(f"目前執行第 {current} 項")
    elif t == "MISSION_ITEM_REACHED":
        log(f"到達第 {msg.seq} 項")
    elif t == "HEARTBEAT" and msg.get_srcSystem() == m.target_system \
            and not msg.base_mode & T.MAV_MODE_FLAG_SAFETY_ARMED:  # 連線上也有 GCS 的 HEARTBEAT，要略過
        log("任務結束：已 disarm")
        break
else:
    raise SystemExit("逾時：任務沒有在時限內結束")
