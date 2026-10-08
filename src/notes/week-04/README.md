# W04 MAVLink 協定

## 本週要知道

學完能回答：**程式怎麼跟無人機講話？要資料、下指令各用什麼訊息？**

1. **MAVLink 是序列協定**：不管底層是 TCP、UDP 或序列埠，封包都是「起始標記、長度、序號、系統 ID、元件 ID、訊息 ID、資料、校驗碼」。MAVLink 2 最長 280 位元組，可簽章。
2. **HEARTBEAT 每秒 1 次**：用來發現對方存在，也用來判斷對方是否斷線。
3. **要資料有兩種方式**：
   - `REQUEST_DATA_STREAM`：舊式，一次要一整群訊息
   - `SET_MESSAGE_INTERVAL`（`COMMAND_LONG` 指令 511）：ArduPilot 4.0 以上，單一訊息、指定間隔（微秒）
   - 另有 `REQUEST_MESSAGE`（指令 512）：只要一次
4. **下指令用 `COMMAND_LONG`，結果看 `COMMAND_ACK`**：W1 的強制解鎖、W2 的起飛都是這條路。
5. **常見訊息**：`ATTITUDE`、`GLOBAL_POSITION_INT`、`LOCAL_POSITION_NED`、`GPS_RAW_INT`、`SYS_STATUS`、`EXTENDED_SYS_STATE`。W1、W2 已經碰過其中幾個。
6. **連線埠**：SITL 的 5760／5762／5763 各自獨立；QGC 走 MAVProxy 轉送的 UDP 14550。
7. **實務**：連線要持續讀取，否則 SITL 會被卡住（W2 踩過）。

### 可以跳過

- 校驗碼與序列化細節（`serialization` 那頁）
- 訊息簽章
- 自訂訊息與 XML 定義

## 閱讀清單

**必讀**

1. MAVLink 基礎：<https://ardupilot.org/dev/docs/mavlink-basics.html>：封包結構與訊息流程
2. 向 ArduPilot 要資料：<https://ardupilot.org/dev/docs/mavlink-requesting-data.html>：`REQUEST_DATA_STREAM` 與 `SET_MESSAGE_INTERVAL` 的差別，W3 留下的問題在這頁

**選讀**

- HEARTBEAT 協定：<https://mavlink.io/en/services/heartbeat.html>
- 標準訊息一覽：<https://mavlink.io/en/messages/index.html>：查欄位與單位
- 序列化（對照用，看不懂正常）：<https://mavlink.io/en/guide/serialization.html>

## 實作

1. 用 pymavlink 持續接收 `ATTITUDE` 與 `GLOBAL_POSITION_INT`，印出頻率與值（腳本：[`scripts/w4_telemetry.py`](../../appendix/scripts/w4_telemetry.md)）
2. 比較 `REQUEST_DATA_STREAM` 與 `SET_MESSAGE_INTERVAL` 實際得到的速率（腳本：[`scripts/w4_rates.py`](../../appendix/scripts/w4_rates.md)）
3. 同時開兩個程式，分別連 5762 與 5763（W3 留下的問題：5760 只允許一個連線時，多個程式怎麼同時連？）
4. 停掉 SITL，觀察 `HEARTBEAT` 斷線時程式怎麼偵測（逾時）

## 學到什麼

### 實作 1：不要就不送

連上 5762 後，SITL 重啟後的 4 秒內只收到 5 個 `HEARTBEAT` 和 1 個 `TIMESYNC`，**沒有 `ATTITUDE`、也沒有 `GLOBAL_POSITION_INT`**。要資料必須先「要」。用 `SET_MESSAGE_INTERVAL` 要 `ATTITUDE` 10 Hz、`GLOBAL_POSITION_INT` 5 Hz 後，實測是 10.0 Hz 與 4.0–5.5 Hz。

### 實作 2：兩種要法的行為

同一條連線依序下指令，每階段量 4 秒（每種訊息的 Hz）：

| 階段 | ATTITUDE | GLOBAL_POSITION_INT | LOCAL_POSITION_NED |
|---|---|---|---|
| 0. 什麼都不要（先重設） | 0 | 0 | 0 |
| 1. `DATA_STREAM` EXTRA1 → 4 Hz | 4.5 | 0 | 0 |
| 2. `DATA_STREAM` EXTRA1 → 20 Hz | 22.5 | 0 | 0 |
| 3. 再加 `INTERVAL` ATTITUDE → 10 Hz | 11.2 | 0 | 0 |
| 4. `DATA_STREAM` POSITION → 2 Hz | 11.2 | 2.2 | 2.0 |
| 5. 再加 `INTERVAL` GLOBAL_POSITION_INT → 10 Hz | 11.5 | 11.2 | 2.5 |

- **`REQUEST_DATA_STREAM` 以群組為單位**：POSITION 一個指令同時帶出 `GLOBAL_POSITION_INT` 和 `LOCAL_POSITION_NED`；`SET_MESSAGE_INTERVAL` 只動單一訊息（階段 5 後 `LOCAL_POSITION_NED` 沒被影響）。
- **後下的指令蓋過先前的**（階段 3：ATTITUDE 從 22.5 掉到 11.2），沒有取較大值或合併。要精準控制單一訊息，用 `SET_MESSAGE_INTERVAL`。
- **設定留在 SITL 的連接埠上，斷線重連也不會消失**：沒重設就重跑，階段 0 會殘留上次的速率。重設方法：`REQUEST_DATA_STREAM` 的 `MAV_DATA_STREAM_ALL` 速率設 0，並把各訊息的 `SET_MESSAGE_INTERVAL` 設 0（還原預設）。階段 0 仍有約 0.2 Hz（4 秒 1 筆），推測是重設瞬間漏出的訊息，沒有進一步確認。
- **JS 類比**：飛控內部有一張「訊息 → 送出間隔」的 `Map`，每個連接埠一份；`SET_MESSAGE_INTERVAL` 是 `map.set(key, v)`，`REQUEST_DATA_STREAM` 是對整組 key 迴圈 `set`；後寫的贏，而且狀態存在 server 端，不是 socket 上。
- **實測略高於設定**（4 → 4.5、20 → 22.5）：原因未確認，可能是 4 秒視窗的邊界誤差，也可能是排程取整。
- **`LOCAL_POSITION_NED` 在 SITL 剛開機時是 0**，放了一陣子後才出現（階段 4 的 2.0 Hz）。推測是 EKF 還沒有位置原點，但沒有直接檢查 EKF 狀態，只是佐證。實驗前先讓 SITL 開一陣子。

## 卡在哪

## 下週問題
