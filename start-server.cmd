@echo off
rem 雙擊或放進「啟動」資料夾：開機後自動啟動劃重點（手機透過 Tailscale 使用）。說明見 docs\iphone.md
chcp 65001 >nul
cd /d "%~dp0"
title 劃重點
npm run serve
pause
