# 無人機自學計畫：自動飛行 / 程式（純模擬）

## 目標

12 週內，在模擬器中用程式控制無人機完成自主任務（起飛、航點、感測器回饋、簡單視覺追蹤），並理解飛控與 MAVLink 的運作原理。

## 約束

- 預算 ≈ 0，不買硬體，全部在模擬中完成
- 環境：macOS（Apple Silicon 與否待確認）；Gazebo/PX4 在 macOS 較不穩，必要時改用 Docker 或 Linux VM
- 每週 5–8 小時；每週結束留一份筆記到 `notes/week-NN/`

## 工具選擇

| 用途 | 首選 | 備案 |
|---|---|---|
| 飛控韌體 | ArduPilot SITL（macOS 原生可跑） | PX4 SITL（Docker） |
| 地面站 | MAVProxy、QGroundControl | Mission Planner（需 Windows） |
| 程式介面 | pymavlink → MAVSDK-Python | DroneKit |
| 3D 模擬 | Gazebo（Docker / VM） | AirSim、Webots |
| 機器人框架 | ROS 2（第 9 週起，Docker） | — |

## 路線圖

### 階段 1：基礎觀念（第 1–3 週）
- **W1 飛行原理**：四軸力學、roll/pitch/yaw/throttle、飛行模式（Stabilize/Loiter/Guided/RTL）
- **W2 飛控架構**：IMU、GPS、氣壓計、EKF、PID 控制迴路；ArduPilot 與 PX4 比較
- **W3 環境建置**：安裝 ArduPilot SITL + MAVProxy + QGroundControl，手動起飛降落
  - 產出：能在 QGC 看到虛擬無人機並下指令

### 階段 2：用程式飛（第 4–6 週）
- **W4 MAVLink 協定**：訊息結構、heartbeat、常見訊息（ATTITUDE、GLOBAL_POSITION_INT）；用 pymavlink 讀遙測
- **W5 Guided 模式**：arm、takeoff、goto、速度控制、降落（pymavlink 與 MAVSDK 各做一次）
- **W6 任務與安全**：上傳航點任務、geofence、failsafe、RTL
  - 專案 1：`projects/waypoint-mission` 自動飛正方形並回家

### 階段 3：感知與進階（第 7–9 週）
- **W7 模擬器進階**：Gazebo 世界、攝影機、距離感測器；ArduPilot/PX4 與 Gazebo 串接
- **W8 電腦視覺**：OpenCV 讀模擬相機畫面、顏色/ArUco 標記偵測
- **W9 ROS 2 入門**：節點、topic、MAVROS 或 px4_msgs
  - 專案 2：`projects/aruco-landing` 偵測標記並精準降落

### 階段 4：整合與延伸（第 10–12 週）
- **W10 控制理論**：調 PID、看 log（`.bin`/ULog）分析、參數調校
- **W11 避障與路徑規劃**：簡單 A*／potential field，在模擬中繞障
- **W12 總結專案**：`projects/final` 自選主題（目標追蹤、多機、搜索覆蓋路徑）
  - 產出：README + 示範錄影 + 心得

## 每週流程

1. 讀（官方文件為主，約 2 小時）
2. 做（實作與小實驗，約 3–4 小時）
3. 寫（在 `notes/week-NN/README.md` 記錄：學到什麼、卡在哪、下週問題）

## 資源

- ArduPilot Dev 文件：<https://ardupilot.org/dev/>
- PX4 文件：<https://docs.px4.io/>
- MAVLink 指南：<https://mavlink.io/en/>
- MAVSDK-Python：<https://mavsdk.mavlink.io/>
- QGroundControl：<https://qgroundcontrol.com/>
- Gazebo：<https://gazebosim.org/>

## 日後上實機

目前不涉及。若要飛實機，先查台灣民航局無人機註冊、操作證與禁限航區規定，再從 <250g 小機與開闊場地開始。

## 進度

- [x] 階段 1（W1–3）：W1 飛行原理、W2 飛控架構（含 4 輪測驗與實作）、W3 環境建置皆完成
- [ ] 階段 2（W4–6）
- [ ] 階段 3（W7–9）
- [ ] 階段 4（W10–12）

**目前位置（2026-10-08）**：W4 MAVLink 協定實作 1–6 與筆記已完成；下一步是 W5 Guided 模式。
