"""W6 專案 1：自動飛正方形並回家（pymavlink）。

用法：vendor/venv/bin/python -u -I scripts/w6_waypoint_mission.py
先執行 scripts/sitl.sh；本腳本連 tcp:127.0.0.1:5762。
流程：設安全參數（geofence + 低電量 RTL）→ 上傳任務 → arm → AUTO 執行 → 落地後印出驗收結果 → 還原參數。
任務：起飛 10 m → 四個角（北 20 m 起順時針）→ RTL。驗收：落地點離 Home 小於 ACCEPT_M 公尺、任務在 TIMEOUT 內結束。
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
TIMEOUT = 300  # 任務最多等幾秒
ACCEPT_M = 3  # 驗收：落地點離 Home 的水平距離上限，公尺
# 安全參數：圓柱圍欄（半徑 50 m、高度上限 20 m，越界 RTL）＋低電量 RTL
SAFETY = {"FENCE_ENABLE": 1, "FENCE_TYPE": 3, "FENCE_ACTION": 1, "FENCE_RADIUS": 50, "FENCE_ALT_MAX": 20,
          "BATT_FS_LOW_ACT": 2}

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


def get_param(name):
    m.mav.param_request_read_send(m.target_system, m.target_component, name.encode(), -1)
    msg = m.recv_match(type="PARAM_VALUE", condition=f"PARAM_VALUE.param_id=='{name}'", blocking=True, timeout=5)
    if msg is None:
        raise SystemExit(f"讀不到參數 {name}")
    return msg.param_value


def set_param(name, value):
    m.mav.param_set_send(m.target_system, m.target_component, name.encode(), value, T.MAV_PARAM_TYPE_REAL32)
    msg = m.recv_match(type="PARAM_VALUE", condition=f"PARAM_VALUE.param_id=='{name}'", blocking=True, timeout=5)
    if msg is None:
        raise SystemExit(f"設定參數 {name} 沒有回應")


def upload(items):
    """依 MAVLink 任務協定上傳 items：[(command, frame, lat, lon, alt), ...]。"""
    m.mav.mission_clear_all_send(m.target_system, m.target_component)
    m.recv_match(type="MISSION_ACK", blocking=True, timeout=5)
    m.mav.mission_count_send(m.target_system, m.target_component, len(items))
    deadline = time.time() + 30  # 上傳最多等幾秒
    while True:
        msg = m.recv_match(type=["MISSION_REQUEST_INT", "MISSION_REQUEST", "MISSION_ACK"],
                           blocking=True, timeout=5)
        if msg is None or time.time() > deadline:
            raise SystemExit("上傳逾時：飛控沒有回應")
        if msg.get_type() == "MISSION_ACK":
            if msg.type != T.MAV_MISSION_ACCEPTED:
                raise SystemExit(f"上傳失敗：MISSION_ACK type={msg.type}")
            return
        cmd, frame, lat, lon, alt = items[msg.seq]  # msg.seq：飛控現在要第幾項
        m.mav.mission_item_int_send(m.target_system, m.target_component, msg.seq, frame, cmd,
                                    0, 1, 0, 0, 0, 0, lat, lon, alt)  # current=0、autocontinue=1、param1–4=0


def local_xy():
    """回傳 (北, 東) 離 EKF 原點的距離，公尺；收不到就結束腳本。"""
    pos = m.recv_match(type="LOCAL_POSITION_NED", blocking=True, timeout=5)  # pos：LOCAL_POSITION_NED 訊息
    if pos is None:
        raise SystemExit("收不到 LOCAL_POSITION_NED")
    return pos.x, pos.y


originals = {n: get_param(n) for n in SAFETY}  # 結束時還原
try:
    # 1. 安全參數
    for name, value in SAFETY.items():
        set_param(name, value)
    log("安全參數已設定：" + "、".join(f"{k}={v}" for k, v in SAFETY.items()))

    # 2. 任務：以目前位置為 home
    g = m.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=10)  # g：GLOBAL_POSITION_INT 訊息
    if g is None:
        raise SystemExit("收不到 GLOBAL_POSITION_INT")
    lat0, lon0 = g.lat / 1e7, g.lon / 1e7  # home 的緯度、經度，度
    alt0 = g.alt / 1000  # home 的海拔（AMSL），公尺

    def offset(north, east):
        """home 往北 north 公尺、往東 east 公尺的 (緯度, 經度)，單位 1e7 度。"""
        lat = lat0 + north / M_PER_DEG_LAT
        lon = lon0 + east / (M_PER_DEG_LAT * math.cos(math.radians(lat0)))
        return int(lat * 1e7), int(lon * 1e7)

    corners = [offset(SIDE, 0), offset(SIDE, SIDE), offset(0, SIDE), offset(0, 0)]
    home_lat, home_lon = offset(0, 0)
    items = [
        (T.MAV_CMD_NAV_WAYPOINT, T.MAV_FRAME_GLOBAL, home_lat, home_lon, alt0),  # 第 0 項：home
        (T.MAV_CMD_NAV_TAKEOFF, T.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, 0, 0, ALT),
    ]
    items += [(T.MAV_CMD_NAV_WAYPOINT, T.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, la, lo, ALT) for la, lo in corners]
    items += [(T.MAV_CMD_NAV_RETURN_TO_LAUNCH, T.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, 0, 0, 0)]
    upload(items)
    log(f"任務已上傳（{len(items)} 項）")

    # 3. arm（EKF 還沒準備好會被拒絕，所以重試）→ AUTO → MISSION_START
    set_mode(GUIDED)
    for _ in range(60):
        if command(T.MAV_CMD_COMPONENT_ARM_DISARM, 1) == 0:
            break
        time.sleep(1)
    else:
        raise SystemExit("arm 失敗")
    home_n, home_e = local_xy()  # 起飛點離 EKF 原點的距離，公尺（驗收用）
    log("已 arm")
    set_mode(AUTO)
    log(f"AUTO；MISSION_START 結果：{command(T.MAV_CMD_MISSION_START, 0, 0)}")

    # 4. 觀察：記錄到達的項目與最遠距離，直到 disarm
    start = time.time()  # 任務開始時刻
    end = start + TIMEOUT
    max_dist = 0.0  # 離 Home 的最大水平距離，公尺
    reached = []  # 到達的項目編號
    while time.time() < end:
        msg = m.recv_match(type=["MISSION_ITEM_REACHED", "LOCAL_POSITION_NED", "HEARTBEAT", "STATUSTEXT"],
                           blocking=True, timeout=1)
        if msg is None:
            continue
        kind = msg.get_type()  # kind：訊息種類
        if kind == "MISSION_ITEM_REACHED":
            reached.append(msg.seq)
            log(f"到達第 {msg.seq} 項")
        elif kind == "STATUSTEXT":
            log(f"STATUSTEXT：{msg.text}")
        elif kind == "LOCAL_POSITION_NED":
            max_dist = max(max_dist, math.hypot(msg.x - home_n, msg.y - home_e))
        elif msg.get_srcSystem() == m.target_system \
                and not msg.base_mode & T.MAV_MODE_FLAG_SAFETY_ARMED:  # 連線上也有 GCS 的 HEARTBEAT，要略過
            break
    else:
        raise SystemExit("逾時：任務沒有在時限內結束")
    duration = time.time() - start  # 任務耗時，秒

    # 5. 驗收
    n, e = local_xy()
    land_dist = math.hypot(n - home_n, e - home_e)  # 落地點離 Home 的水平距離，公尺
    ok = land_dist <= ACCEPT_M and all(i in reached for i in range(2, 6))
    print("—— 驗收 ——")
    print(f"耗時 {duration:.0f} 秒；到達項目 {reached}；最遠離 Home {max_dist:.1f} m；落地點離 Home {land_dist:.1f} m")
    print("結果：" + ("通過" if ok else "未通過"))
finally:
    for name, value in originals.items():
        set_param(name, value)
    log("參數已還原")
