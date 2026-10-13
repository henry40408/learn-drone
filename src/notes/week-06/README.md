# W06 任務與安全

## 本週要知道

學完能回答：**怎麼把一串航點交給無人機自己飛完？飛出範圍或出狀況時，飛控怎麼自保？**

1. **任務是一份「清單」存在飛控裡**：用 AUTO 模式執行，不是你一直發指令。W5 的 Guided 是「你指揮每一步」，W6 的任務是「先交代好、再放手」。
2. **上傳任務有固定協定**（MAVLink mission protocol）：
   - 你送 `MISSION_COUNT`（共幾項）
   - 飛控逐項回 `MISSION_REQUEST_INT`（要第幾項）
   - 你回 `MISSION_ITEM_INT`（該項內容）
   - 全部收完，飛控回 `MISSION_ACK`
   - 跟 W4 的 `COMMAND_LONG` 不同：這是**飛控主動來要**，你被動回應
3. **任務項目 = 指令 + 參數 + 座標**：`NAV_TAKEOFF`、`NAV_WAYPOINT`、`NAV_RETURN_TO_LAUNCH`、`NAV_LAND` 等；第 0 項在 ArduPilot 是 home，不能當航點用（需查文件確認細節）。
4. **航點之間會減速轉彎還是順過**：一般航點到達判定看 `WPNAV_RADIUS`；spline 航點（`NAV_SPLINE_WAYPOINT`）才會平滑過彎。這是 W5 速度控制轉角減速的答案。
5. **Geofence（地理圍欄）**：用一組 `FENCE_*` 參數設定圓柱範圍（半徑、高度上限）與越界動作（RTL、降落…）；越界時飛控自己處理，不靠你的程式。
6. **Failsafe（故障保護）**：遙控器斷線、地面站斷線、電池低電量、EKF 失效等情況各有參數決定動作，常見是 RTL 或 LAND。
7. **RTL（Return To Launch）**：回到起飛點上空（先爬到 `RTL_ALT`），再降落；也是多數 failsafe 的預設動作。
8. **安全機制是「最後防線」**：先在模擬器故意觸發一次，看到它真的動作，才算理解。

### 可以跳過

- 任務項目的條件與事件指令（`CONDITION_*`、`DO_*` 大全）：用到再查
- Rally point（備降點）與 ArduPilot 的 mission 重新排序細節
- 固定翼與 VTOL 的 failsafe

## 閱讀清單

**必讀**

1. MAVLink 任務協定：<https://mavlink.io/en/services/mission.html>：上傳／下載流程與狀態
2. Auto 模式：<https://ardupilot.org/copter/docs/auto-mode.html>
3. 任務指令一覽（ArduPilot 支援的）：<https://ardupilot.org/copter/docs/common-mavlink-mission-command-messages-mav_cmd.html>
4. RTL 模式：<https://ardupilot.org/copter/docs/rtl-mode.html>
5. Failsafe 總覽：<https://ardupilot.org/copter/docs/failsafe-landing-page.html>

**選讀**

- Geofence：<https://ardupilot.org/copter/docs/common-geofencing-landing-page.html>
- 簡易圍欄設定：<https://ardupilot.org/copter/docs/common-ac2_simple_geofence.html>
- 電池 failsafe：<https://ardupilot.org/copter/docs/failsafe-battery.html>
- 地面站 failsafe：<https://ardupilot.org/copter/docs/gcs-failsafe.html>
- MAVSDK 任務（C++ 指南，Python 用法對照）：<https://mavsdk.mavlink.io/main/en/cpp/guide/missions.html>

## 實作

1. pymavlink 上傳一個正方形任務（起飛 → 四個航點 → RTL），切 AUTO 執行並觀察進度（`MISSION_CURRENT`、`MISSION_ITEM_REACHED`）
2. 觀察任務協定：只送 `MISSION_COUNT` 不回應會怎樣？（逾時與重送）
3. 設圓柱 geofence，用 Guided 往外飛，觀察越界時的動作
4. 觸發一種 failsafe（例如地面站斷線或電池低電量），確認飛控自己 RTL
5. （選做）用 MAVSDK 的 `mission` 外掛重做實作 1，比較兩者
6. 專案 1：`projects/waypoint-mission`，整合以上做成「自動飛正方形並回家」

## 學到什麼

## 卡在哪

## 下週問題
