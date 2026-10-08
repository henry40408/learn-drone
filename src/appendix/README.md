# 附錄：程式碼

筆記裡用到的所有腳本，原始檔在 repo 的 `scripts/`，這裡直接顯示內容。`w*.py` 都連到 `tcp:127.0.0.1:5762`，使用前先執行 `scripts/sitl.sh`；`pid_*.py` 是純模擬，不需要 SITL。

- [`pid_climb.py`](scripts/pid_climb.md)：PID 完整升空：0 m → 9.5 m → 10 m，同時畫出高度與 P、I、D 三項的數字。
- [`pid_demo.py`](scripts/pid_demo.md)：PID 示範：一維高度控制，從 0 m 升到 10 m，比較 P、PI、PID。
- [`pid_terms.py`](scripts/pid_terms.md)：PID 三項各自的「量」：懸停在 10 m，t=2 秒時突然多了載重，看 P、I、D 如何貢獻推力。
- [`sitl.sh`](scripts/sitl.md)：啟動 ArduCopter SITL，並用 MAVProxy 轉送到 UDP 14550（QGC 預設埠）。Ctrl-C 結束。
- [`w1_modes.py`](scripts/w1_modes.md)：W1 實驗：有風時比較 AltHold、Loiter、Stabilize。
- [`w2_noise.py`](scripts/w2_noise.md)：W2 實驗：開啟模擬的 IMU 震動雜訊，比較原始值與 EKF 估算。
- [`w2_sensors.py`](scripts/w2_sensors.md)：W2 實作：讀 SITL 靜止時的原始感測器值，與 EKF 估算的姿態比較。
- [`w4_backlog.py`](scripts/w4_backlog.md)：W4 實驗：沒被讀取的資料會被丟掉，還是下次讀取時一次收到？
- [`w4_heartbeat.py`](scripts/w4_heartbeat.md)：W4 實驗 4：HEARTBEAT 斷線偵測。
- [`w4_rates.py`](scripts/w4_rates.md)：W4 實驗 2：比較 REQUEST_DATA_STREAM 與 SET_MESSAGE_INTERVAL 實際得到的速率。
- [`w4_request_message.py`](scripts/w4_request_message.md)：W4 實驗：REQUEST_MESSAGE（指令 512）只要一次，不會持續推送。
- [`w4_two_ports.py`](scripts/w4_two_ports.md)：W4 實驗 3：同時連 5762 與 5763，看速率設定是各自一份還是共用，以及同一個埠能不能連兩次。
- [`w4_telemetry.py`](scripts/w4_telemetry.md)：W4 實驗 1：持續接收 ATTITUDE 與 GLOBAL_POSITION_INT，每秒印出實際頻率與最新值。
