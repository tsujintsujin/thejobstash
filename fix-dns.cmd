@echo off
REM ---------------------------------------------------------------------------
REM  Point this machine's DNS at resolvers that work.
REM
REM  WHY: the router at 192.168.254.254 currently answers REFUSED to every
REM  lookup - not just some names, all of them. Chrome still works because it
REM  uses DNS-over-HTTPS and never asks the router. Everything else on the
REM  machine does ask, so npm, git, pip and cloudflared all fail with
REM  "ENOTFOUND" or "no such host".
REM
REM  This is what currently stops the tunnel connecting: cloudflared has to
REM  resolve Cloudflare's edge before it can dial out, and it cannot.
REM
REM  WHAT IT DOES: sets the DNS servers on the active adapter to Cloudflare
REM  (1.1.1.1) and Google (8.8.8.8). It changes nothing else - not the router,
REM  not the firewall, not any other setting. Needs Administrator, so Windows
REM  will ask you to confirm; that prompt is this script asking for itself.
REM
REM  TO UNDO: run this with the word "revert" after it, or in Settings ->
REM  Network -> Wi-Fi -> DNS server assignment, set it back to Automatic.
REM ---------------------------------------------------------------------------
setlocal

REM Self-elevate. "Run with PowerShell" from the context menu does not elevate,
REM so without this the script would simply be refused.
net session >nul 2>&1
if %errorlevel% neq 0 (
  echo Asking Windows for Administrator...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '%1' -Verb RunAs"
  exit /b
)

if /i "%1"=="revert" goto revert

echo.
echo  Before:
powershell -NoProfile -Command "Get-DnsClientServerAddress -AddressFamily IPv4 | Where-Object {$_.ServerAddresses} | Format-Table -AutoSize InterfaceAlias,ServerAddresses"

powershell -NoProfile -Command ^
  "$a = Get-NetAdapter | Where-Object {$_.Status -eq 'Up' -and -not $_.Virtual} | Select-Object -First 1;" ^
  "if (-not $a) { Write-Host 'No active adapter found.'; exit 1 }" ^
  "Set-DnsClientServerAddress -InterfaceIndex $a.ifIndex -ServerAddresses ('1.1.1.1','8.8.8.8');" ^
  "Write-Host ('Set DNS on ' + $a.Name + ' to 1.1.1.1, 8.8.8.8')"

ipconfig /flushdns >nul

echo.
echo  After:
powershell -NoProfile -Command "Get-DnsClientServerAddress -AddressFamily IPv4 | Where-Object {$_.ServerAddresses} | Format-Table -AutoSize InterfaceAlias,ServerAddresses"

echo  Testing...
powershell -NoProfile -Command ^
  "try { $r = Resolve-DnsName registry.npmjs.org -Type A -ErrorAction Stop | Select-Object -First 1;" ^
  "Write-Host ('  OK  registry.npmjs.org -> ' + $r.IPAddress) }" ^
  "catch { Write-Host '  STILL FAILING - tell Claude what this said' }"

echo.
echo  Done. Now run scorer.cmd to bring the scorer and tunnel up.
pause
exit /b

:revert
echo Reverting the active adapter to automatic (DHCP) DNS...
powershell -NoProfile -Command ^
  "$a = Get-NetAdapter | Where-Object {$_.Status -eq 'Up' -and -not $_.Virtual} | Select-Object -First 1;" ^
  "Set-DnsClientServerAddress -InterfaceIndex $a.ifIndex -ResetServerAddresses;" ^
  "Write-Host ('Reset DNS on ' + $a.Name)"
ipconfig /flushdns >nul
pause
exit /b
