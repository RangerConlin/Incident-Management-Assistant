@echo off
setlocal

REM srv1707346 is the box's own local hostname, not a resolvable DNS record
REM from outside it — use the public IP as the actual SSH target.
set "VPS=root@2.25.136.185"
set "REMOTE_ROOT=/opt/sarapp-web-client"
set "PROJECT_NAME=sarapp-web-client"

echo Updating SARApp web client on %VPS%
echo.

REM No --env-file .env here, unlike cloud_server/cloud_router's update scripts:
REM web_client's docker-compose.yml has no required env vars, so this must not
REM hard-fail if .env was never created. Compose still picks one up on its own
REM if it exists.
ssh -t %VPS% "cd %REMOTE_ROOT% && git pull --ff-only && cd web_client && docker compose -p %PROJECT_NAME% up -d --build --remove-orphans && docker compose -p %PROJECT_NAME% ps && echo && echo Update complete. You are now in %REMOTE_ROOT%/web_client. && exec bash"

echo.
echo SSH session ended.
pause
