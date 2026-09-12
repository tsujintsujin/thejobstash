@echo off
REM ---------------------------------------------------------------------------
REM  TheJobStash scorer - the one piece that still runs on this machine.
REM
REM  The site itself is on Cloudflare and does not need this to serve pages,
REM  sign people in, or show the dashboard. What needs it is anything that runs
REM  Python: the free trial, resume upload, digest preview and delivery. Those
REM  say "the scorer is offline" while this is not running.
REM
REM  Double-click this, or run it from a terminal. It starts two things:
REM    1. py_server.py   - api_bridge's commands over HTTP on localhost:3300
REM    2. cloudflared    - dials OUT to Cloudflare and publishes that as
REM                        https://scorer.thejobstash.com
REM
REM  Nothing listens for inbound connections and no port is forwarded.
REM  Close this window to stop both.
REM ---------------------------------------------------------------------------
setlocal

cd /d "%~dp0"

REM Secrets and ids live in .env.cloudflare, which is never committed.
if not exist ".env.cloudflare" (
  echo .env.cloudflare is missing - it holds JOBSTASH_PY_TOKEN and the D1 ids.
  pause
  exit /b 1
)
for /f "usebackq tokens=1,* delims==" %%A in (".env.cloudflare") do (
  if not "%%A"=="" if not "%%B"=="" set "%%A=%%B"
)

set "CLOUDFLARED=%APPDATA%\npm\node_modules\cloudflared\bin\cloudflared.exe"

echo.
echo  storage : Cloudflare D1 (via %JOBSTASH_SITE_ORIGIN%)
echo  scorer  : http://localhost:3300
echo  public  : https://scorer.thejobstash.com
echo.

start "jobstash scorer" cmd /c "python py_server.py & pause"
start "jobstash tunnel" cmd /c ""%CLOUDFLARED%" tunnel run jobstash-scorer & pause"

echo Both started in their own windows. Close them to stop.
timeout /t 5 >nul
endlocal
