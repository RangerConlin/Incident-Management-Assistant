@echo off
setlocal

REM srv1707346 is the box's own local hostname, not a resolvable DNS record
REM from outside it — use the public IP as the actual SSH target.
set "VPS=root@2.25.136.185"
set "REMOTE_ROOT=/opt/sarapp"
set "PROJECT_NAME=sarapp-router"

echo Updating SARApp cloud router on %VPS%
echo.

ssh -t %VPS% "cd %REMOTE_ROOT% && git pull --ff-only && cd services/cloud_router && docker compose -p %PROJECT_NAME% --env-file .env up -d --build --remove-orphans && docker compose -p %PROJECT_NAME% --env-file .env ps && echo && echo Update complete. You are now in %REMOTE_ROOT%/services/cloud_router. && exec bash"

echo.
echo SSH session ended.
pause
