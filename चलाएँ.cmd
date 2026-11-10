@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 -m bhash_studio %*
) else (
  python -m bhash_studio %*
)
if errorlevel 1 (
  echo कार्यक्रम शुरू नहीं हो सका। पाइथन और उसकी चित्रमय खिड़कियों की स्थापना जाँचें।
  pause >nul
)
