# W05 Guided 模式

## 本週要知道

學完能回答：**怎麼用程式讓無人機自己起飛、飛到指定位置、降落？**

1. **GUIDED 是「由程式指揮」的模式**：飛控自己穩住姿態，程式只給目標（位置或速度），不用管馬達。
2. **固定流程**：切 GUIDED → arm → takeoff → 給目標 → 降落。每一步都要確認條件成立（`COMMAND_ACK`、高度、距離）再做下一步，不能靠 `sleep`。
3. **arm 會被拒絕**：EKF 或 GPS 還沒準備好時 pre-arm 檢查不過，要重試或看 `STATUSTEXT`。
4. **takeoff 是指令、goto 是目標訊息**：
   - 起飛：`COMMAND_LONG`（`MAV_CMD_NAV_TAKEOFF`）
   - 位置／速度：`SET_POSITION_TARGET_LOCAL_NED`（或 `GLOBAL_INT`），用 `type_mask` 選要控制哪些欄位
5. **座標系**：local NED 是 x 北、y 東、z **向下**（高度要給負數）；全域用緯度、經度、相對高度。
6. **速度控制要持續發送**：速度指令約 3 秒（`GUID_TIMEOUT`）沒更新就失效，飛機才會停下來（類似 W1 的 RC override）。
7. **降落**：切 LAND 模式，落地後飛控自動 disarm。

### 可以跳過

- 姿態目標（`SET_ATTITUDE_TARGET`）：下層控制，之後再說
- 各種 `MAV_FRAME` 的細節，先用 `LOCAL_NED` 與 `GLOBAL_RELATIVE_ALT_INT` 兩種

## 閱讀清單

**必讀**

1. Guided 模式（Copter）：<https://ardupilot.org/copter/docs/ac2_guidedmode.html>
2. 以 MAVLink 控制 Copter：<https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html>：takeoff、位置、速度指令與 `type_mask`

**選讀**

- MAVSDK-Python：<https://mavsdk.mavlink.io/main/en/python/quickstart.html>：實作 3 用
- `SET_POSITION_TARGET_LOCAL_NED`：<https://mavlink.io/en/messages/common.html#SET_POSITION_TARGET_LOCAL_NED>

## 實作

1. pymavlink 完成「GUIDED → arm → takeoff 10 m → goto 北 20 m、東 20 m → 降落」（腳本：[`scripts/w5_guided_basic.py`](../../appendix/scripts/w5_guided_basic.md)）
2. 用速度控制飛一個正方形，並觀察停止發送速度指令後飛機的反應（腳本：[`scripts/w5_velocity_square.py`](../../appendix/scripts/w5_velocity_square.md)；加參數 `timeout` 做後者）
3. 用 MAVSDK-Python 重做實作 1，比較兩者的寫法（PLAN 要求兩種各做一次）（腳本：[`scripts/w5_mavsdk_basic.py`](../../appendix/scripts/w5_mavsdk_basic.md)；要先關掉 QGC）
4. （額外）故意在 arm 前不等 EKF，觀察被拒絕的原因

## 學到什麼

### 實作 1：pymavlink 基本流程

流程是「切 GUIDED → arm → takeoff → goto → LAND」，每步都等條件成立：

| 步驟 | 送什麼 | 怎麼確認完成 |
|---|---|---|
| 切模式 | `SET_MODE`（custom_mode 4） | `HEARTBEAT` 的 `custom_mode` 變成 4 |
| arm | `COMMAND_LONG` `COMPONENT_ARM_DISARM` | `COMMAND_ACK` result 0；被拒絕是 4（`FAILED`） |
| takeoff | `COMMAND_LONG` `NAV_TAKEOFF`（param7 = 高度） | ACK 只代表「接受」，要看 `GLOBAL_POSITION_INT.relative_alt` 到 95% |
| goto | `SET_POSITION_TARGET_LOCAL_NED`（沒有 ACK） | 自己算 `LOCAL_POSITION_NED` 到目標的水平距離 < 1 m |
| 降落 | `SET_MODE` LAND（編號 9） | `relative_alt` < 0.2 m，落地後飛控自動 disarm |

- **指令的 ACK 只代表「收到」，不代表「做完」**：回答 W4 留下的問題，完成與否要看遙測（高度、距離）。
- **goto 沒有 ACK**：`SET_POSITION_TARGET_*` 是目標訊息不是指令，送出去就沒下文，到沒到要自己看位置。
- **arm 會被拒絕**：SITL 剛開機 EKF 還沒好時，約 20 秒內都 `result=4`，要重試。拒絕原因在 `STATUSTEXT`（實測在 `sitl.sh` 的輸出裡看到 `Arm: Throttle (RC3) is not neutral`；腳本本身沒有印 `STATUSTEXT`），ACK 本身只說 `FAILED`。
- **QGC 會干擾**：QGC 的虛擬搖桿開著時，油門不在中位，arm 一直被拒絕；關掉虛擬搖桿後 1 秒就 arm 成功。

### 實作 2：速度控制

`SET_POSITION_TARGET_LOCAL_NED` 的 `type_mask` 決定哪些欄位有效：用速度就忽略位置、加速度、yaw、yaw 速率。座標系 local NED：x 北、y 東、z 向下（往上要給負的）。

- **要持續發送**：腳本以 10 Hz 送。`timeout` 模式停止發送後，飛機**繼續以 2 m/s 飛了約 3.5 秒**才停（多滑行約 7 m），符合 `GUID_TIMEOUT` 預設 3 秒。
- **轉角會減速**：每換一邊地速掉到約 0.5 m/s 再回到 2 m/s，因為指令從 (2, 0) 直接跳到 (0, 2)，飛控受加速度上限限制。正方形終點與起點偏差約 1 m。
- **想不減速**：把速度向量的方向逐步旋轉，或放寬加速度參數（任務模式的是 `WP_ACCEL`、轉角加速度是 `WP_ACC_CNR`，見 ArduPilot 文件；Guided 速度模式用哪個沒有驗證）；更合適的是 W6 的任務與 spline 航點。
- **`type_mask` 的位元值不要手算**：一開始寫的 `0b0000_1111_1111_1000` 多設了 bit 9（`FORCE_SET`），改成用 `POSITION_TARGET_TYPEMASK_*_IGNORE` 常數組合才精確。

### 實作 3：MAVSDK-Python 4.0

同一流程用 MAVSDK 重做，約 34 秒跑完：

| | pymavlink | MAVSDK 4.0 |
|---|---|---|
| 風格 | 同步，自己組訊息、等 ACK | `async/await`，一個動作一個呼叫 |
| 失敗 | 檢查 `ack.result` | 丟 `ActionError` |
| 切模式 | 自己 `SET_MODE` | `takeoff()` 內部處理 |
| goto | local NED（公尺） | 經緯度＋海拔 AMSL，要自己換算 |
| 連線 | `tcp:127.0.0.1:5762`（獨立埠，可與 QGC 並存） | `udpin://0.0.0.0:14550`（與 QGC 搶同一埠） |

- **基本動作 MAVSDK 好寫很多**，但把細節包起來了：看不到 `result=4` 或 `STATUSTEXT`，低階控制（`type_mask`、任意訊息、`SET_MESSAGE_INTERVAL`）也較弱。
- **4.0 與 3.x 不同**：內嵌原生函式庫、不再需要 `mavsdk_server` 與 `grpcio`，import 路徑是 `mavsdk.asyncio`；`udp://` 已棄用，要用 `udpin://`。
- **JS 類比**：pymavlink 像直接寫 `fetch` 加手動處理回應，MAVSDK 像一層有型別的 SDK client。

## 卡在哪

- **arm 一直被拒絕**：先是 EKF 還沒好（等約 20 秒），後來是 QGC 虛擬搖桿讓 RC3 不在中位；`COMMAND_ACK` 只說 `FAILED`，原因要看 `STATUSTEXT`。
- **MAVSDK 連不上**：QGC 還開著會搶 14550，要先關掉；用 `udp://` 會有棄用警告。
- **用高度判斷落地不可靠**：飛機已落地並 disarm，`relative_alt` 仍讀到 1.17 m（相對 home 的值會漂移），`< 0.2 m` 的條件逾時；改成等飛控 disarm。
- **等 disarm 被 GCS 的 `HEARTBEAT` 誤觸**：連線上也有 system 255 的 `HEARTBEAT`（沒有 ARMED 旗標），第一版沒過濾，腳本在降落開始 0.6 秒就誤判完成；要只看 `get_srcSystem() == m.target_system`。同樣的問題 W4 實作 4 就提過。
- **goto 馬上「完成」**：目標是相對 EKF 原點的 (20, 20)，連續多次不重啟 SITL 時，飛機降落點已經在 (20, 20)，所以一開始就在目標上。要重現飛行過程需重啟 SITL。
- **`type_mask` 的位元寫錯**：手算的值多了 `FORCE_SET`，實測雖然能飛，但不精確。
- **沒解開的疑問**：
  - Guided 速度模式的加速度上限到底是哪個參數（任務模式是 `WP_ACCEL`，這個沒驗證；原本猜的 `WPNAV_ACCEL` 是舊版名稱）。
  - MAVSDK 的 `offboard` 速度控制在 ArduPilot 上能不能用（沒測）。
  - 實作 4（arm 被拒絕的 `PreArm` 原因）沒做，只在實作 1 碰到兩種。

## 下週問題

- W6 上傳航點任務：MAVLink 的任務協定（`MISSION_COUNT`、`MISSION_REQUEST_INT`、`MISSION_ACK`）流程是什麼？跟 MAVSDK 的 `mission` 外掛差多少？
- 任務模式能不能不減速過彎（spline 航點、`WP_RADIUS`）？
- geofence 與 failsafe（RTL、電池、斷線）各自怎麼設定、怎麼觸發？
- 同時開 pymavlink 與 MAVSDK 時，埠要怎麼分（MAVSDK 搶 14550，QGC 也要用）？
