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
7. **實務**：連線要持續讀取，否則 SITL 會被卡住（W2 踩過；本週只堆了約 4 KB，沒重現卡住）。有要求但沒讀的資料不會被丟掉，會堆在緩衝區，恢復讀取時一次收到舊資料（見「學到什麼」的實作 5）。

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
3. 同時開兩個程式，分別連 5762 與 5763（W3 留下的問題：5760 只允許一個連線時，多個程式怎麼同時連？）（腳本：[`scripts/w4_two_ports.py`](../../appendix/scripts/w4_two_ports.md)）
4. 暫停（SIGSTOP）或殺掉 SITL，觀察 `HEARTBEAT` 斷線時程式怎麼偵測（逾時）（腳本：[`scripts/w4_heartbeat.py`](../../appendix/scripts/w4_heartbeat.md)）
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
- **`ATTITUDE` 實測比設定高約 12%**（4 → 4.5、10 → 11.2、20 → 22.5，實作 3 的 5 → 5.7～6.0 也一樣）：原因未確認。已排除兩件事：不是 SITL 時鐘比真實時間快（飛控時間與牆鐘的比值是 1.000），也不是全部訊息都這樣（`SYSTEM_TIME` 要 10 Hz，實測約 10.2 Hz）。所以是 `ATTITUDE` 這類訊息的送出排程造成的，細節沒有再追。
- **`LOCAL_POSITION_NED` 在 SITL 剛開機時是 0**，放了一陣子後才出現（階段 4 的 2.0 Hz）。推測是 EKF 還沒有位置原點，但沒有直接檢查 EKF 狀態，只是佐證。實驗前先讓 SITL 開一陣子。

### 實作 3：同時連 5762 與 5763

同一個程式開兩條連線（A 連 5762、B 連 5763；對 SITL 來說就是兩個 TCP 連線，效果等同兩個程式），各自設定 `ATTITUDE` 的速率，同時讀取：

| 階段 | A（5762） | B（5763） | ACK |
|---|---|---|---|
| 0. 都沒要求 | 0 | 0 | 各 1 個（是重設指令的回應，晚到） |
| 1. A 要 20 Hz | 23.0 | 0 | 只有 A 收到 |
| 2. B 再要 5 Hz | 23.7 | 5.7 | 只有 B 收到 |
| 3. A 改成 2 Hz | 2.0 | 6.0 | 只有 A 收到 |
| 4. B 停止 | 2.3 | 0 | 只有 B 收到 |

- **每個連接埠各有一份速率設定**：A 改速率不影響 B（階段 3），B 停止也不影響 A（階段 4）。實作 2 的「後下的蓋過先前的」只在同一個連接埠內成立。這也回答了 W2 的問題：QGC 走另一個連接埠，所以我要 20 Hz，QGC 顯示 4 Hz 是它自己的設定，不是被我蓋掉（QGC 一側的實際原因沒有驗證）。
- **`COMMAND_ACK` 只回給下指令的那條連線**：另一條連線不會收到，所以前面「ACK 混在遙測裡」只需要過濾自己這條連線。
- **同一個連接埠只服務一個客戶端**：A 佔著 5762 時，第二次連 5762 沒有收到 `HEARTBEAT`（TCP 連得上，但沒有資料）；5760 被 MAVProxy 佔用，連 5760 也一樣。
- **回答 W3 的問題**：5760 被 MAVProxy 用了，你的程式各自連 5762、5763，一個埠一個程式；需要更多就要用 MAVProxy 的 `--out` 轉送出更多埠（UDP），這個沒有實測。
- **JS 類比**：每個連接埠像一個獨立的 server instance，各有自己的訂閱表，每個只接受一個 client；不是同一個 server 上的多個 session 共用一份狀態。

### 實作 4：`HEARTBEAT` 斷線偵測

偵測方法：超過 3 秒（`TIMEOUT`）沒收到飛控的 `HEARTBEAT` 就判定斷線。用兩種方式讓飛控「消失」：

| 方式 | 做法 | 觀察 |
|---|---|---|
| **凍結** | 5 秒時 `SIGSTOP` 暫停 `arducopter`，13 秒時 `SIGCONT` 恢復 | TCP 連線還在，只是沒資料；暫停後 2.5–3 秒判定斷線；恢復後約 0.3 秒就收到下一個 `HEARTBEAT`，不用重連，也沒有補送一堆 `HEARTBEAT` |
| **殺掉** | 5 秒時 `SIGKILL` | TCP 連線被關閉；同樣在暫停後約 3 秒由逾時判定斷線 |

- **斷線偵測只能靠逾時**。`recv_match` 沒資料時回傳 `None`，跟「連線已經關閉」回傳的結果一樣，單看回傳值分不出來。偵測延遲介於 `TIMEOUT − 1` 到 `TIMEOUT` 秒之間（取決於斷線時離上次 `HEARTBEAT` 多久）。
- **凍結比殺掉難偵測**：凍結時 TCP 看起來一切正常（沒有 EOF、沒有錯誤），只有逾時能發現；殺掉至少連線層會知道。
- **連線關閉後 pymavlink 會空轉**：`recv_match(blocking=True, timeout=0.5)` 不再阻塞，10 秒內狂印了約 290 萬行 `EOF on TCP socket`、吃滿一顆 CPU。實務上偵測到斷線後要立刻關掉連線或停止迴圈，不能繼續呼叫 `recv_match`。
- **連線上有兩個 `HEARTBEAT` 來源**：飛控（system 1，type 2 = 四旋翼）和一個 GCS（system 255，type 6），各約 1 Hz。GCS 那個推測是 MAVProxy 發的、由飛控轉送到這個埠（凍結期間它也跟著消失，支持這個推測，但沒有直接確認來源）。**偵測斷線要過濾掉 GCS 的**，否則只要地面站活著，就可能讓你誤判飛控還活著。
- **凍結恢復後的 `HEARTBEAT` 爆量，是 GCS 的、不是飛控的**：未過濾時，恢復後 1 秒內收到 9 個；過濾後飛控自己只有 1 個，GCS 的約 8 個。這 8 個是 MAVProxy 在凍結的 8 秒裡送給飛控、堆在緩衝區裡的，飛控恢復後一次讀完再轉送出來；飛控自己的 `HEARTBEAT` 在凍結時根本沒有產生，所以不會補送。這正好呼應實作 5：**沒產生的不會補，已經送出但沒人讀的會堆積**。
- **JS 類比**：WebSocket 的 ping / pong 逾時。網路層沒掉時（凍結），`onclose` 不會觸發，只能靠應用層心跳；掉了（殺掉）會收到 `onclose`，pymavlink 卻不會告訴你，只會空轉。
- **沒釐清的**：`w4_telemetry.py` 印出 `component=0`，可能跟 `wait_heartbeat` 先收到哪個 `HEARTBEAT` 有關，沒有確認。

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

- **第一次跑 `w4_telemetry.py` 什麼都沒印**：5762 預設只送 `HEARTBEAT`，要先用 `SET_MESSAGE_INTERVAL` 要求才有 `ATTITUDE`。
- **實驗 2 階段 0 不乾淨**：上次實驗留下的速率表還在（設定存在飛控、斷線不會清），所以每次開頭都要 `reset()`。
- **`HEARTBEAT` 計數偏高**：GCS（system 255）的 `HEARTBEAT` 也會經飛控轉送到連線上，要用 `type` 過濾。
- **kill 模式輸出 49 MB**：連線關閉後 pymavlink 空轉狂印 `EOF on TCP socket`，要用 `grep -v` 濾掉。
- **沒解開的疑問**：
  - `ATTITUDE` 實測比要求的速率高約 12%（SITL 時鐘比 1.000，原因不明）。
  - QGC 顯示 4 Hz 的原因。
  - 緩衝區滿了 SITL 會不會卡住（只堆了約 4 KB，沒測到）。
  - 剛開機的 SITL 上 `LOCAL_POSITION_NED` 為 0（推測是 EKF 還沒設定原點，未驗證）。
  - `w4_telemetry.py` 印出 `component=0` 的原因。

## 下週問題

- W5 Guided 模式：`arm`、`takeoff`、`goto` 各自要送哪個 MAVLink 指令？怎麼確認指令真的被接受、執行完了（`COMMAND_ACK` 之外還要看什麼）？
- 速度控制（`SET_POSITION_TARGET_*`）的座標系與單位是什麼？
- 同時有 pymavlink 與 MAVSDK 兩個程式連線時，埠要怎麼分？
