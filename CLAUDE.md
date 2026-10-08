# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案性質

自學無人機（自動飛行／程式，純模擬、零硬體預算）的 workspace，內容是一本用 mdBook 編寫的 12 週學習筆記，不是應用程式；目前沒有測試或 lint。

## 指令

- `mdbook build`：建置到 `book/`（已 gitignore）
- `mdbook serve --open`：本機預覽並自動重新整理

## 結構

- mdBook 只讀 `src/`（`book.toml` 的 `src = "src"`），所有內容都必須放在 `src/` 底下，不能放在專案根目錄
- `src/SUMMARY.md` 是目錄，新增章節或頁面時必須同步登記，否則不會出現在書中
- `src/PLAN.md`：12 週路線圖與工具選擇，是整個專案的依據
- `src/notes/week-NN/README.md`：每週筆記，固定三節（學到什麼／卡在哪／下週問題）；週次主題與 `PLAN.md` 的 W1–W12 一一對應
- `src/appendix/`：附錄，每個 `scripts/*` 一頁（`appendix/scripts/<name>.md`，用 `{{#include}}` 引入原始檔）；新增腳本時要補一頁、登記到 `SUMMARY.md`，並在筆記裡連過去
- `src/projects/`：三個階段性專案（`waypoint-mission` W6、`aruco-landing` W9、`final` W12），總覽在 `README.md`

## 環境注意

- 開發機是 arm64 macOS：ArduPilot SITL 可原生執行；Gazebo 與 PX4 較不穩，需用 Docker 或 Linux VM
- 內容語言為繁體中文（台灣用語）

## 模擬環境

- `scripts/sitl.sh`：啟動 ArduCopter SITL 並轉送 MAVLink 到 UDP 14550（QGC）；程式可直接連 `tcp:127.0.0.1:5762`
- 所有軟體都在 `vendor/`（gitignore），不得裝到家目錄或系統目錄；用 `vendor/venv/bin/python` 執行 pymavlink
- `vendor/ardupilot` 有一處本地修改（`AP_FWVersion.h` 在 Apple 平台不用 `PACKED`），重新 clone 後需重做，細節見 `src/notes/week-03/README.md`

## 腳本慣例

- 變數可以簡寫，但要在定義處加註解說明意思與單位
