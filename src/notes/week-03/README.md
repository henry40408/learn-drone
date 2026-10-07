# W03 環境建置

## 學到什麼

- **架構**：你的程式／QGC／MAVProxy 透過 MAVLink 與飛控溝通；SITL 是把 ArduPilot 編成能在電腦上跑的程式，並模擬感測器與物理。
- **連接埠**：SITL 的 TCP 5760、5762 給程式連；QGC 預設聽 UDP 14550，所以中間要用 MAVProxy 轉送（`--out udp:127.0.0.1:14550`）。
- **模式**：Stabilize 不會定高，要降落用 Land；MAVLink 切模式可用 `set_mode_send`（Land = 9）。

## 安裝（全部在專案內，`vendor/` 已 gitignore）

| 項目 | 版本 | 位置 |
|---|---|---|
| ArduPilot | Copter-4.7.1 | `vendor/ardupilot` |
| Python 套件（pymavlink、MAVProxy 等） | pymavlink 2.4.50、MAVProxy 1.8.75 | `vendor/venv` |
| QGroundControl | v5.1.4 | `vendor/QGroundControl.app` |

步驟：

1. `git clone --depth 1 --branch Copter-4.7.1 --recurse-submodules --shallow-submodules` ArduPilot 到 `vendor/`
2. `uv venv vendor/venv`，裝 `empy==3.3.4 pexpect future setuptools wheel numpy pymavlink MAVProxy gnureadline`
3. `python modules/waf/waf-light configure --board sitl`，再 `waf-light copter`
4. 從 GitHub release 下載 QGC 的 dmg，把 `.app` 複製到 `vendor/`

不使用官方 `install-prereqs-mac.sh`：它會用 `sudo` 並修改 shell 設定。

## 啟動

```sh
scripts/sitl.sh                      # SITL + 轉送到 14550
open vendor/QGroundControl.app       # 會自動連線
```

驗證：QGC 左上角顯示綠色 Ready 與 Stabilize，地圖出現在 Canberra 附近。按 Takeoff 後可升空；用 pymavlink 切 Land 後平穩降落。

## 卡關與解法

- **連結失敗** `ld: pointer not aligned in AP_FWVersion::fwver`：新版 Xcode linker 不接受 `PACKED` 類別內的指標。`-ld_classic` 已被移除，無效。解法：在 `libraries/AP_Common/AP_FWVersion.h` 讓 `__APPLE__` 不套用 `PACKED`（只改 vendor，SITL 不需要該結構的封裝）。
- **MAVProxy 啟動失敗** `No module named 'gnureadline'`：在 venv 補裝。
- **QGC 顯示 Disconnected**：用 `--no-mavproxy` 時只有 TCP，沒有 UDP 14550，需另外啟動 MAVProxy 轉送。
- **macOS 沒有 `timeout` 指令**（需 coreutils）：用背景執行加 `pkill` 取代。
- **我一度誤判**：從 `GLOBAL_POSITION_INT` 的高度 3 公尺判斷它在地面，實際上 `landed_state` 是 IN_AIR。判斷是否在空中，應看 `EXTENDED_SYS_STATE.landed_state` 與馬達輸出，不要只看單一訊息。

## 下週問題

- W4：怎麼用 pymavlink 持續接收 ATTITUDE、GLOBAL_POSITION_INT？`request_data_stream_send` 與 `SET_MESSAGE_INTERVAL` 差在哪？
- 5760 只允許一個連線時，多個程式怎麼同時連？
