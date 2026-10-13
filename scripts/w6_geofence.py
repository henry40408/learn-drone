"""W6 實驗 3：設圓柱 geofence（pymavlink），Guided 往外飛，觀察越界時飛控自己做什麼。

用法：vendor/venv/bin/python -u -I scripts/w6_geofence.py
先執行 scripts/sitl.sh；本腳本連 tcp:127.0.0.1:5762。
做法：圍欄半徑 30 m、高度上限 20 m，越界動作 RTL；起飛到 10 m 後以速度指令往北飛，越界後只觀察。
每次位置更新印出北向距離。結束時還原參數。
注意：
- Guided 的 goto 目標若在圍欄外會被飛控直接拒絕（飛機不動），所以改用速度指令往北飛。
- Home 每次 arm 都會重設，圍欄圓心跟著動；要從起點（北 0 m）起飛才會在北 30 m 越界。
"""
import time

from pymavlink import mavutil

CONN = "tcp:127.0.0.1:5762"
ALT = 10  # 起飛與飛行高度，公尺（相對起飛點）
SPEED = 3  # 往北飛的速度，m/s
SEND_SECONDS = 40  # 速度指令最多送幾秒（飛機越界後飛控接管，模式不再是 GUIDED 就停送）
GUIDED = 4  # ArduCopter 的 GUIDED 模式編號
TIMEOUT = 120  # 每個階段最多等幾秒
FENCE_TYPE_ALT_MAX_CIRCLE = 3  # FENCE_TYPE 是 bitmask：1 = 高度上限、2 = 以 Home 為圓心的圓；3 = 兩個都開
FENCE_ACTION_RTL_OR_LAND = 1  # FENCE_ACTION：1 = RTL（不行就 LAND）
FENCE_RADIUS = 30  # 圍欄半徑，公尺（FENCE_RADIUS 最小值就是 30）
FENCE_ALT_MAX = 20  # 圍欄高度上限，公尺（FENCE_ALT_MAX 範圍 10–1000）
MODES = {3: "AUTO", 4: "GUIDED", 5: "LOITER", 6: "RTL", 9: "LAND"}  # ArduCopter 模式編號 → 名稱，只用來印 log
PARAMS = {"FENCE_ENABLE": 1, "FENCE_TYPE": FENCE_TYPE_ALT_MAX_CIRCLE, "FENCE_ACTION": FENCE_ACTION_RTL_OR_LAND,
          "FENCE_RADIUS": FENCE_RADIUS, "FENCE_ALT_MAX": FENCE_ALT_MAX,
          "AVOID_ENABLE": 0}  # 要設定的參數；AVOID_ENABLE 預設 3（含 UseFence），會在圍欄內 2 m 把速度指令擋下來，要關掉才會越界

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


def get_param(name):
    m.mav.param_request_read_send(m.target_system, m.target_component, name.encode(), -1)
    msg = m.recv_match(type="PARAM_VALUE", condition=f"PARAM_VALUE.param_id=='{name}'", blocking=True, timeout=5)
    if msg is None:
        raise SystemExit(f"讀不到參數 {name}")
    return msg.param_value


def set_param(name, value):
    m.mav.param_set_send(m.target_system, m.target_component, name.encode(), value,
                         T.MAV_PARAM_TYPE_REAL32)
    msg = m.recv_match(type="PARAM_VALUE", condition=f"PARAM_VALUE.param_id=='{name}'", blocking=True, timeout=5)
    if msg is None:
        raise SystemExit(f"設定參數 {name} 沒有回應")
    log(f"{name} = {msg.param_value:g}")


originals = {n: get_param(n) for n in PARAMS}  # 結束時還原
log(f"原始參數：{originals}")
try:
    for name, value in PARAMS.items():
        set_param(name, value)

    # 1. GUIDED → arm（EKF 還沒好會被拒絕，所以重試）→ takeoff
    m.mav.set_mode_send(m.target_system, T.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, GUIDED)
    for _ in range(60):
        if command(T.MAV_CMD_COMPONENT_ARM_DISARM, 1) == 0:
            break
        time.sleep(1)
    else:
        raise SystemExit("arm 失敗")
    log("已 arm")
    command(T.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, ALT)
    end = time.time() + TIMEOUT
    while time.time() < end:
        g = m.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=1)
        if g is not None and g.relative_alt / 1000 >= ALT * 0.95:  # relative_alt 單位 mm → m
            break
    log("takeoff 完成")

    # 2. 速度指令往北（10 Hz 持續送；速度指令不做圍欄檢查，所以飛得出去），越界後飛控會改模式
    ignore = (T.POSITION_TARGET_TYPEMASK_X_IGNORE | T.POSITION_TARGET_TYPEMASK_Y_IGNORE
              | T.POSITION_TARGET_TYPEMASK_Z_IGNORE | T.POSITION_TARGET_TYPEMASK_AX_IGNORE
              | T.POSITION_TARGET_TYPEMASK_AY_IGNORE | T.POSITION_TARGET_TYPEMASK_AZ_IGNORE
              | T.POSITION_TARGET_TYPEMASK_YAW_IGNORE | T.POSITION_TARGET_TYPEMASK_YAW_RATE_IGNORE)
    log(f"往北 {SPEED} m/s（圍欄半徑 {FENCE_RADIUS} m）")

    # 3. 印模式變化、STATUSTEXT、每 5 m 變化一次的離 Home 距離，直到 disarm
    end = time.time() + TIMEOUT
    send_until = time.time() + SEND_SECONDS  # 速度指令送到這個時刻為止
    last_send = 0  # 上次送速度指令的時刻
    mode = None  # 目前的 custom_mode
    last_north = None  # 上次印出的北向距離（取整到 5 m），公尺
    while time.time() < end:
        now = time.time()
        if mode in (None, GUIDED) and now < send_until and now - last_send >= 0.1:
            last_send = now
            m.mav.set_position_target_local_ned_send(
                0, m.target_system, m.target_component, T.MAV_FRAME_LOCAL_NED, ignore,
                0, 0, 0, SPEED, 0, 0, 0, 0, 0, 0, 0)
        msg = m.recv_match(type=["HEARTBEAT", "STATUSTEXT", "LOCAL_POSITION_NED"], blocking=True, timeout=0.1)
        if msg is None:
            continue
        kind = msg.get_type()  # kind：訊息種類
        if kind == "STATUSTEXT":
            log(f"STATUSTEXT：{msg.text}")
        elif kind == "LOCAL_POSITION_NED":
            north = round(msg.x / 5) * 5  # msg.x：往北距離，公尺
            if north != last_north:
                last_north = north
                log(f"北 {msg.x:.1f} m、高 {-msg.z:.1f} m")
        elif msg.get_srcSystem() == m.target_system:  # 連線上也有 GCS（system 255）的 HEARTBEAT，要略過
            if msg.custom_mode != mode:
                mode = msg.custom_mode
                log(f"模式：{MODES.get(mode, mode)}")
            if not msg.base_mode & T.MAV_MODE_FLAG_SAFETY_ARMED:
                log("結束：已 disarm")
                break
    else:
        raise SystemExit("逾時")
finally:
    for name, value in originals.items():
        set_param(name, value)
