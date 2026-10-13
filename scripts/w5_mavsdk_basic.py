"""W5 實驗 3：Guided 基本流程（MAVSDK-Python 4.0）：arm、takeoff、goto、降落。

用法：vendor/venv/bin/python -u -I scripts/w5_mavsdk_basic.py
與 scripts/w5_guided_basic.py 做同一件事，用來比較兩種寫法。
先執行 scripts/sitl.sh；本腳本聽 udpin://0.0.0.0:14550（MAVProxy 轉送的埠），所以要先關掉 QGC，
否則兩個程式搶同一個埠。MAVSDK 的 goto 吃經緯度與海拔（AMSL），不是 local NED。
"""
import asyncio
import math
import time

from mavsdk.asyncio import ComponentType, Configuration, Mavsdk
from mavsdk.asyncio.plugins.action import ActionAsync, ActionError
from mavsdk.asyncio.plugins.telemetry import TelemetryAsync

CONN = "udpin://0.0.0.0:14550"  # udpin：本機監聽（udp:// 已被 MAVSDK 標為棄用）
TAKEOFF_ALT = 10  # 起飛高度，公尺（相對起飛點）
GOTO_NORTH = 20  # goto 目標：往北幾公尺（相對起飛點）
GOTO_EAST = 20  # goto 目標：往東幾公尺（相對起飛點）
M_PER_DEG_LAT = 111_320  # 每度緯度約幾公尺（近似值）
TIMEOUT = 60  # 每個階段最多等幾秒
t0 = time.time()  # 腳本開始時刻


def log(msg):
    print(f"[{time.time() - t0:5.1f}s] {msg}")


async def wait_for(label, check):
    """每個位置更新就呼叫 check(position)；成立就回傳，逾時就結束腳本。"""
    async def loop():
        async for pos in telemetry.subscribe_position():
            if check(pos):
                return pos

    try:
        pos = await asyncio.wait_for(loop(), TIMEOUT)
    except asyncio.TimeoutError:
        raise SystemExit(f"逾時：{label}")
    log(f"{label}：完成")
    return pos


async def main():
    global telemetry
    config = Configuration.create_with_component_type(ComponentType.GROUND_STATION)
    async with Mavsdk(config) as mavsdk:
        await mavsdk.add_any_connection(CONN)
        system = await mavsdk.first_autopilot(timeout_s=10.0)
        if system is None:
            raise SystemExit("找不到飛控（QGC 是否還開著？）")
        log("已連線")
        action = ActionAsync(system)  # action：arm、takeoff、goto、land 等動作
        telemetry = TelemetryAsync(system)  # telemetry：位置、狀態等遙測

        # 1. arm（EKF 還沒準備好會被拒絕，所以重試；MAVSDK 以例外表示失敗）
        for _ in range(30):
            try:
                await action.arm()
                break
            except ActionError as e:
                log(f"arm 被拒絕（{e}），1 秒後重試")
                await asyncio.sleep(1)
        else:
            raise SystemExit("arm 失敗")
        log("已 arm")

        # 2. takeoff：高度達到目標的 95% 就算完成
        await action.set_takeoff_altitude(TAKEOFF_ALT)
        await action.takeoff()
        pos = await wait_for("takeoff", lambda p: p.relative_altitude_m >= TAKEOFF_ALT * 0.95)

        # 3. goto：把「北 20 m、東 20 m」換成經緯度；高度維持（absolute_altitude_m 是 AMSL）
        lat0, lon0 = pos.latitude_deg, pos.longitude_deg  # 起點（起飛點上空）
        lat = lat0 + GOTO_NORTH / M_PER_DEG_LAT
        lon = lon0 + GOTO_EAST / (M_PER_DEG_LAT * math.cos(math.radians(lat0)))
        await action.goto_location(lat, lon, pos.absolute_altitude_m, 0)
        log(f"goto：北 {GOTO_NORTH} m、東 {GOTO_EAST} m")

        def reached(p):
            dn = (p.latitude_deg - lat) * M_PER_DEG_LAT  # 距目標：北向，公尺
            de = (p.longitude_deg - lon) * M_PER_DEG_LAT * math.cos(math.radians(lat0))  # 距目標：東向，公尺
            return math.hypot(dn, de) < 1.0

        await wait_for("goto", reached)

        # 4. 降落：落地後飛控自動 disarm
        await action.land()
        log("land 指令已送出")
        await wait_for("降落", lambda p: p.relative_altitude_m < 0.2)


asyncio.run(main())
