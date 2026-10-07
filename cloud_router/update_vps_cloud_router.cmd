@echo off
setlocal

set "VPS=root@srv1707346"
set "REMOTE_ROOT=/root/incident-management-assistant"
set "PROJECT_NAME=cloud_router"

echo Updating SARApp cloud router on %VPS%
echo.

ssh -t %VPS% "cd %REMOTE_ROOT% && git pull --ff-only && cd cloud_router && docker compose -p %PROJECT_NAME% --env-file .env up -d --build --remove-orphans && docker compose -p %PROJECT_NAME% --env-file .env ps && echo && echo Update complete. You are now in %REMOTE_ROOT%/cloud_router. && exec bash"

echo.
echo SSH session ended.
pause
