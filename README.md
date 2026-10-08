# learn-drone

自學無人機（自動飛行／程式）的筆記，純模擬、零硬體預算。內容是一本用 [mdBook](https://rust-lang.github.io/mdBook/) 編寫的 12 週學習筆記，語言為繁體中文（台灣用語）。

## 內容

- `src/PLAN.md`：12 週路線圖與工具選擇
- `src/notes/week-NN/README.md`：每週筆記（學到什麼／卡在哪／下週問題）
- `src/projects/`：三個階段性專案（W6、W9、W12）
- `src/appendix/`：附錄，每支腳本一頁，直接在書裡看程式碼
- `scripts/`：模擬環境啟動腳本與實驗程式（pymavlink）

目前進度：W1–W4 已完成（飛行原理、飛控架構、環境建置、MAVLink 協定），W5 起為規劃中。

## 閱讀

```sh
mdbook serve --open   # 本機預覽並自動重新整理
mdbook build          # 建置到 book/
```

## 模擬環境

- 開發機為 arm64 macOS，使用 ArduPilot SITL（可原生執行）與 QGroundControl。
- 所有軟體安裝在 `vendor/`（已 gitignore，不在此 repo 中）；安裝步驟、版本與疑難排解見 [W03 筆記](src/notes/week-03/README.md)。
- `scripts/sitl.sh` 啟動 ArduCopter SITL，並轉送 MAVLink 到 UDP 14550（QGroundControl）。
- 其餘腳本用 `vendor/venv/bin/python` 執行，需先啟動 SITL。

## 授權

- 程式碼（`scripts/`）：[MIT](LICENSE.txt)
- 筆記與圖片（`src/`）：[CC BY 4.0](src/LICENSE.txt)

本 repo 不包含 ArduPilot（GPLv3）與 QGroundControl 的原始碼或執行檔，這些由讀者自行下載，各自適用其授權。
