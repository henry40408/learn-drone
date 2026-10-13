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
6. **速度控制要持續發送**：速度指令約 1 秒沒更新就失效，飛機會停下來（類似 W1 的 RC override）。
7. **降落**：切 LAND 模式，落地後飛控自動 disarm。

### 可以跳過

- 姿態目標（`SET_ATTITUDE_TARGET`）：下層控制，之後再說
- 各種 `MAV_FRAME` 的細節，先用 `LOCAL_NED` 與 `GLOBAL_RELATIVE_ALT_INT` 兩種

## 閱讀清單

**必讀**

1. Guided 模式（Copter）：<https://ardupilot.org/copter/docs/ardupilot-copter-guided-mode.html>
2. 以 MAVLink 控制 Copter：<https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html>：takeoff、位置、速度指令與 `type_mask`

**選讀**

- MAVSDK-Python：<https://mavsdk.mavlink.io/main/en/python/quickstart.html>：實作 3 用
- `SET_POSITION_TARGET_LOCAL_NED`：<https://mavlink.io/en/messages/common.html#SET_POSITION_TARGET_LOCAL_NED>

## 實作

1. pymavlink 完成「GUIDED → arm → takeoff 10 m → goto 北 20 m、東 20 m → 降落」（腳本：[`scripts/w5_guided_basic.py`](../../appendix/scripts/w5_guided_basic.md)）
2. 用速度控制飛一個正方形（改發速度、持續發送；觀察停止發送後飛機的反應）
3. 用 MAVSDK-Python 重做實作 1，比較兩者的寫法（PLAN 要求兩種各做一次）
4. （額外）故意在 arm 前不等 EKF，觀察被拒絕的原因

## 學到什麼

## 卡在哪

## 下週問題
