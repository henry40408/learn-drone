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

1. 用 pymavlink 持續接收 `ATTITUDE` 與 `GLOBAL_POSITION_INT`，印出頻率與值
2. 比較 `REQUEST_DATA_STREAM` 與 `SET_MESSAGE_INTERVAL` 實際得到的速率
3. 同時開兩個程式，分別連 5762 與 5763（W3 留下的問題：5760 只允許一個連線時，多個程式怎麼同時連？）
4. 停掉 SITL，觀察 `HEARTBEAT` 斷線時程式怎麼偵測（逾時）

## 學到什麼

## 卡在哪

## 下週問題
