"""W6 實驗 4：觸發低電量 failsafe（pymavlink），觀察飛控自己切到 RTL 並降落。

用法：vendor/venv/bin/python -u -I scripts/w6_failsafe_battery.py
先執行 scripts/sitl.sh；本腳本連 tcp:127.0.0.1:5762。
做法：起飛飛到北 30 m 後，把 BATT_LOW_VOLT 調到比目前電壓高 1 V，等 BATT_LOW_TIMER 秒後飛控判定低電量，
依 BATT_FS_LOW_ACT 動作。結束時還原三個參數。
"""
import time

from pymavlink import mavutil

CONN = "tcp:127.0.0.1:5762"
ALT = 10  # 起飛高度，公尺（相對起飛點）
FAR = 30  # 觸發前先飛到北幾公尺，這樣才看得出 RTL 飛回來
GUIDED = 4  # ArduCopter 的 GUIDED 模式編號
TIMEOUT = 120  # 每個階段最多等幾秒
FS_LOW_ACT_RTL = 2  # BATT_FS_LOW_ACT：2 = RTL
LOW_TIMER = 2  # BATT_LOW_TIMER：電壓持續低於門檻幾秒才觸發，秒
MODES = {3: "AUTO", 4: "GUIDED", 5: "LOITER", 6: "RTL", 9: "LAND"}  # ArduCopter 模式編號 → 名稱，只用來印 log

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


def watch(until):
    """印出模式變化與飛控的 STATUSTEXT，直到 until() 為真；逾時就結束腳本。"""
    end = time.time() + TIMEOUT
    mode = None  # 目前的 custom_mode
    while time.time() < end:
        msg = m.recv_match(type=["HEARTBEAT", "STATUSTEXT"], blocking=True, timeout=1)
        if msg is None:
            continue
        if msg.get_type() == "STATUSTEXT":
            log(f"STATUSTEXT：{msg.text}")
        elif msg.get_srcSystem() == m.target_system:  # 連線上也有 GCS（system 255）的 HEARTBEAT，要略過
            if msg.custom_mode != mode:
                mode = msg.custom_mode
                log(f"模式：{MODES.get(mode, mode)}")
            if until(msg):
                return
    raise SystemExit("逾時")


def disarmed(hb):
    return not hb.base_mode & T.MAV_MODE_FLAG_SAFETY_ARMED


originals = {n: get_param(n) for n in ("BATT_LOW_VOLT", "BATT_LOW_TIMER", "BATT_FS_LOW_ACT")}  # 結束時還原
log(f"原始參數：{originals}")
try:
    set_param("BATT_FS_LOW_ACT", FS_LOW_ACT_RTL)
    set_param("BATT_LOW_TIMER", LOW_TIMER)

    # 1. GUIDED → arm（EKF 還沒好會被拒絕，所以重試）→ takeoff → 飛到北 FAR 公尺
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
    m.mav.set_position_target_local_ned_send(
        0, m.target_system, m.target_component, T.MAV_FRAME_LOCAL_NED,
        T.POSITION_TARGET_TYPEMASK_VX_IGNORE | T.POSITION_TARGET_TYPEMASK_VY_IGNORE
        | T.POSITION_TARGET_TYPEMASK_VZ_IGNORE | T.POSITION_TARGET_TYPEMASK_AX_IGNORE
        | T.POSITION_TARGET_TYPEMASK_AY_IGNORE | T.POSITION_TARGET_TYPEMASK_AZ_IGNORE
        | T.POSITION_TARGET_TYPEMASK_YAW_IGNORE | T.POSITION_TARGET_TYPEMASK_YAW_RATE_IGNORE,
        FAR, 0, -ALT, 0, 0, 0, 0, 0, 0, 0, 0)
    end = time.time() + TIMEOUT
    while time.time() < end:
        pos = m.recv_match(type="LOCAL_POSITION_NED", blocking=True, timeout=1)  # pos.x：往北距離，公尺
        if pos is not None and abs(pos.x - FAR) < 1.0:
            break
    log(f"已飛到北 {FAR} m")

    # 2. 把低電量門檻調到比目前電壓高 1 V
    volt = m.recv_match(type="SYS_STATUS", blocking=True, timeout=5).voltage_battery / 1000  # mV → V
    log(f"目前電壓 {volt:.2f} V，把 BATT_LOW_VOLT 調到 {volt + 1:.2f} V")
    set_param("BATT_LOW_VOLT", volt + 1)

    # 3. 不再送任何指令，只觀察飛控自己做什麼，直到 disarm
    watch(disarmed)
    log("結束：已 disarm")
finally:
    for name, value in originals.items():
        set_param(name, value)
