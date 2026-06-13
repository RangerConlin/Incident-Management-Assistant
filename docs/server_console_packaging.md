# SARApp Server Console Packaging

This document describes how to build and test the standalone Windows executable for the SARApp Server Console. The Server Console package is separate from the main SARApp desktop client package and uses `sarapp_server_console.py` as its entry point.

## What gets built

The dedicated PyInstaller spec at `packaging/SARAppServerConsole.spec` builds a windowed executable named `SARAppServerConsole.exe`.

Expected output:

```text
dist/SARAppServerConsole/SARAppServerConsole.exe
```

The build is intentionally scoped to the Server Console, `server/`, and `core/networking/` support modules. It does not package the main desktop client build and does not include demo data.

## Prerequisites

From a Windows command prompt or PowerShell session in the repository root:

```bat
python -m pip install -r requirements.txt
python -m pip install pyinstaller
```

PySide6 must be importable in the same Python environment used for the build.

## Build the executable

Run the dedicated batch file from the repository root:

```bat
build_server_console.bat
```

The script will:

1. Check that the Server Console spec file exists.
2. Check that PyInstaller is installed.
3. Remove previous `build\SARAppServerConsole` and `dist\SARAppServerConsole` artifacts.
4. Run PyInstaller with `packaging\SARAppServerConsole.spec`.
5. Confirm that `dist\SARAppServerConsole\SARAppServerConsole.exe` exists.

For non-interactive automation, set `SARAPP_NO_PAUSE=1` before running the script so it exits without pausing:

```bat
set SARAPP_NO_PAUSE=1
build_server_console.bat
```

## Run the Server Console

After a successful build, launch:

```bat
dist\SARAppServerConsole\SARAppServerConsole.exe
```

The executable opens the SARApp Server Console window without requiring users to run Python manually. The app stores editable console settings in a writable settings folder next to the packaged executable:

```text
dist/SARAppServerConsole/settings/server_console.json
```

If the settings file does not exist, the console starts with defaults and creates the file when settings are saved or the server is restarted.

## Server Console validation

Manual validation on Windows:

1. Start `dist\SARAppServerConsole\SARAppServerConsole.exe`.
2. Confirm the Server Console window opens and does not immediately crash.
3. Click **Start Server**.
4. Confirm **Server status** changes to **Running**.
5. Confirm **Discovery status** changes to **Broadcasting** when discovery is enabled.
6. Open `http://127.0.0.1:8765/health` or click **Open Health Check**.
7. Confirm the health response includes `"ok": true` and a `server` object.
8. Click **Stop Server**.
9. Confirm **Server status** returns to **Stopped**.
10. Close the console and confirm only the server instance owned by this console is stopped.

A simple post-build artifact check is also available:

```bat
python tools\smoke_test_server_console.py
```

This smoke test only verifies that the expected executable path exists; it does not require external network access.

## Test with the main SARApp desktop app

Use this procedure to confirm the desktop client can discover and connect to the standalone Server Console server:

1. Start `dist\SARAppServerConsole\SARAppServerConsole.exe`.
2. In the Server Console, leave discovery enabled and click **Start Server**.
3. Verify `http://127.0.0.1:8765/health` responds successfully.
4. Launch the main SARApp desktop app separately, either from source with `python main.py` or from its own existing desktop executable.
5. Confirm the desktop app discovers the Server Console server on the LAN.
6. Confirm the desktop app connects to the discovered server and does not fall back to offline mode while the server is running.
7. Stop the server from the Server Console after testing.

## Troubleshooting

### PyInstaller is not installed

Symptom: `build_server_console.bat` prints that PyInstaller is not installed.

Fix:

```bat
python -m pip install pyinstaller
```

Then rerun `build_server_console.bat`.

### PySide6 is missing

Symptom: PyInstaller or the built executable reports that `PySide6` cannot be imported.

Fix:

```bat
python -m pip install -r requirements.txt
```

Make sure the same Python environment is used for both dependency installation and the build.

### Port already in use

Symptom: The Server Console reports that the configured port is unavailable.

Fix: Stop the other process using the port or change the Server Console port in the Settings section. The default server port is `8765`.

### Windows firewall blocks discovery

Symptom: The health endpoint works locally, but other machines or the desktop client cannot discover the server.

Fix: Allow `SARAppServerConsole.exe` through Windows Defender Firewall for the appropriate network profile. Discovery uses UDP broadcast on the configured discovery port; the default discovery port is `45454`.

### Server starts but the client does not discover it

Checklist:

- Confirm **Discovery** is enabled in the Server Console settings.
- Confirm **Discovery status** says **Broadcasting** after the server starts.
- Confirm the desktop client and Server Console are on the same LAN or broadcast domain.
- Confirm Windows firewall or endpoint security is not blocking UDP broadcast traffic.
- Try manually connecting the desktop client to the Server Console host and port if broadcast discovery is blocked.

### Health endpoint is not responding

Checklist:

- Confirm the Server Console status is **Running**.
- Confirm the configured host and port are correct.
- For a default local check, open `http://127.0.0.1:8765/health`.
- If the port was changed, use the configured port in the URL.
- If another service is using the port, stop it or choose a different Server Console port.
