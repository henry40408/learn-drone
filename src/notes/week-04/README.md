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
7. **實務**：連線要持續讀取，否則 SITL 會被卡住（W2 踩過）。有要求但沒讀的資料不會被丟掉，會堆在緩衝區，恢復讀取時一次收到舊資料（見「學到什麼」的實作 5）。

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
5. （額外）有要求但暫停讀取、或沒要求時，資料會被丟掉還是堆積？（腳本：[`scripts/w4_backlog.py`](../../appendix/scripts/w4_backlog.md)）
6. （額外）`REQUEST_MESSAGE` 只要一次，實際行為是什麼？（腳本：[`scripts/w4_request_message.py`](../../appendix/scripts/w4_request_message.md)）

## 學到什麼

### 概念：用 WebSocket 類比 MAVLink

MAVLink 像一條**雙向長連線（WebSocket）**，上面混著兩種流量：

| MAVLink | WebSocket／JS 類比 | 差別 |
|---|---|---|
| `REQUEST_DATA_STREAM`、`SET_MESSAGE_INTERVAL` | 訂閱（subscribe）：訂一次，伺服器依速率持續推事件 | 訂閱狀態存在飛控的連接埠上，斷線也不會消失；WebSocket 斷線訂閱就沒了 |
| `ATTITUDE` 等遙測訊息 | 伺服器主動推送的事件（`onmessage`） | 用 message ID 區分種類，像事件的 `type` |
| `COMMAND_LONG` → `COMMAND_ACK` | 自己定義的 request / response 訊息 | 見下 |
| `HEARTBEAT` | 心跳（ping） | 每秒 1 次，逾時就當作斷線（實作 4） |

`COMMAND_LONG` 與 HTTP request / response 不同的地方：

- **沒有 request ID**：ACK 靠 `ack.command` 欄位對應是哪個指令，不是靠順序。
- **ACK 混在遙測裡**：同一條連線上一直有 `ATTITUDE` 等資料湧來，所以要用 `recv_match(type="COMMAND_ACK")` 過濾。腳本是「發一個、等下一個 ACK」，同時有多個未回應的指令就可能對錯。
- **結果有狀態**：`ACCEPTED`、`DENIED`、`IN_PROGRESS`（起飛這種要一陣子的指令，之後還會再回最終結果）。
- **協定沒有內建逾時或重試**，要自己寫。
- **不是所有指令都有 ACK**：`REQUEST_DATA_STREAM` 沒有回應，只能看之後有沒有資料來；`PARAM_SET` 的回應是 `PARAM_VALUE`；`SET_MODE` 要看 `HEARTBEAT` 的模式有沒有變。後三項是一般知識，沒有逐一實測。

封包結構（標頭、序號、校驗碼）不用背，pymavlink 會處理；只要記得 system ID（哪台機器）、component ID（機器上的哪個零件）、message ID（哪種訊息）三個欄位，對應程式裡的 `m.target_system`、`m.target_component`、`MAVLINK_MSG_ID_*`。

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

### 實作 5：沒被讀取的資料去哪了

要 `ATTITUDE` 20 Hz，暫停讀取 5 秒再讀取；另外也測了「沒要求」5 秒後再要求。

| 情境 | 結果 |
|---|---|
| A. 有要求，暫停讀取 5 秒後恢復 | 恢復後 2 秒共收到 141 筆，**前 0.5 秒就收到 109 筆**（平常 0.5 秒約 10 筆）；第一筆的飛控時間只比暫停前最後一筆晚 0.05 秒 |
| B. 沒要求 5 秒後才要求 | 緩衝區裡 0 筆；重新要求後 2 秒收到 40 筆，前 0.5 秒 9 筆，沒有爆量 |

- **有要求但不讀：不會丟，會堆積**。141 ≈ 堆積的約 100 筆（5 秒 × 20 Hz）加上之後即時的約 40 筆。第一筆緊接著暫停前的最後一筆（只差 0.05 秒，剛好是 20 Hz 的一個間隔），中間沒有缺口，所以拿到的是**一批舊資料**，不是只剩最新的。TCP 是可靠傳輸，資料留在作業系統的緩衝區，恢復讀取時一次吐出來。
- **沒要求：什麼都沒有**。飛控不產生這些訊息，沒有東西在排隊，所以之後要求時是從那一刻開始送，不會補送。
- **JS 類比**：沒人 `subscribe` 就不 `emit`（B）；有 `subscribe` 但沒人消費 stream，資料堆在內部緩衝區，直到你開始讀才一口氣流出來（A）。
- **實務**：讀取程式如果中途停了一陣子，恢復後要預期會先收到舊資料；要拿「現在」的值，需要把緩衝區讀到空，或看 `time_boot_ms` 判斷新舊。
- **沒測到的**：5 秒 × 20 Hz 只有約 4 KB，遠小於緩衝區，所以沒有重現 W2 的「SITL 被卡住」。緩衝區塞滿後 SITL 內部怎麼反應，沒有驗證；UDP 是否直接丟包，也沒有測。

### 實作 6：`REQUEST_MESSAGE` 只要一次

先把 `ATTITUDE` 停掉（沒要求時 3 秒內 0 筆），再各送一次 `REQUEST_MESSAGE`（指令 512）：

| 動作 | 結果 |
|---|---|
| 要 `ATTITUDE` 一次 | 1 個 `COMMAND_ACK`（指令 512、result 0 = ACCEPTED），1 筆 `ATTITUDE`，約 2 毫秒內就到 |
| 再要一次 | 又 1 個 `COMMAND_ACK`、又 1 筆 `ATTITUDE` |
| 要 `AUTOPILOT_VERSION`（平常不會主動送） | 1 個 ACK，收到固件版本 4.7.1（type 位元組 255，我記得是正式版，沒有查文件確認） |

- **一次就是一次**：沒有持續推送，不需要再停掉；想要更新就再送一次，像單次的 `fetch`。
- **適合查靜態資訊**：固件版本、電池資訊這類不常變的東西，不必為了它開串流。
- **指令有 ACK，資料另外到**：ACK 只代表「飛控接受了這個請求」，要的訊息是另一個封包，要自己用 `recv_match` 收。

## 卡在哪

## 下週問題
