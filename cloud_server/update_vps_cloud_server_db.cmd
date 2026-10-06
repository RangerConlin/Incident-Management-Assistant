@echo off
setlocal

set "VPS=root@srv1707346"
set "REMOTE_ROOT=/opt/sarapp-cloud-server-db"
set "PROJECT_NAME=sarapp-cloud-server-db-test"

echo Updating SARApp cloud server DB on %VPS%
echo.

ssh -t %VPS% "cd %REMOTE_ROOT% && git pull --ff-only && cd cloud_server && docker compose -p %PROJECT_NAME% --env-file .env up -d --build --remove-orphans && docker compose -p %PROJECT_NAME% --env-file .env ps && echo && echo Update complete. You are now in %REMOTE_ROOT%/cloud_server. && exec bash"

echo.
echo SSH session ended.
pause
