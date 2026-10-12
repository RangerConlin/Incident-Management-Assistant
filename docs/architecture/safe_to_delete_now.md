# Safe To Delete Now

This is a conservative cleanup list for local/generated files that do not need
to participate in the repo migration. These files are not source of truth; they
are produced by Python, Node/Vite, Flutter, IDEs, test runs, or local agent
tools.

Before deleting, close any running dev servers, test runners, Python processes,
Flutter builds, or editors that may be using these folders.

## Incident-Management-Assistant

Safe generated/cache folders:

```text
__pycache__/
.pytest_cache/
.venv/
dist/
logs/
tmp/
apps/web/node_modules/
apps/web/dist/
server/sarapp_db/sarapp_db.egg-info/
server/sarapp_db/sarapp_db/sarapp_db.egg-info/
```

Safe generated/cache file patterns:

```text
**/__pycache__/
**/*.pyc
apps/web/*.tsbuildinfo
apps/web/vite.config.d.ts
apps/web/vite.config.js
```

Local app/session state that is safe to delete if you do not need that local
state anymore:

```text
.Clairvoyance/
.claude/scheduled_tasks.lock
.claude/worktrees/
```

Do not delete all of `.claude/` blindly if you care about local Claude/Codex
settings or agent history. The `worktrees/` subfolder is the main cleanup
candidate.

## ICS-Mobile-App

Safe generated/cache folders:

```text
.dart_tool/
build/
android/.gradle/
ios/Flutter/ephemeral/
windows/flutter/ephemeral/
```

Safe generated/cache files:

```text
.flutter-plugins-dependencies
ics_mobile_app.iml
ios/Flutter/Generated.xcconfig
ios/Flutter/flutter_export_environment.sh
ios/Runner/GeneratedPluginRegistrant.h
ios/Runner/GeneratedPluginRegistrant.m
windows/flutter/generated_plugin_registrant.cc
windows/flutter/generated_plugin_registrant.h
windows/flutter/generated_plugins.cmake
```

Local IDE state that is safe to delete if you do not need local IDE settings:

```text
.idea/
```

## Do Not Delete From This List Without Review

These may contain source, docs, fixtures, seed data, or local work products:

```text
data/
forms/
modules/
profiles/
reports/
tools/scripts/
tools/
apps/web/src/
ICS-Mobile-App/lib/
ICS-Mobile-App/test/
ICS-Mobile-App/android/app/
ICS-Mobile-App/ios/Runner/
```

## Notes

- Deleting `.venv/` means you will need to recreate the Python virtual
  environment before running the desktop/server code from that environment.
- Deleting `apps/web/node_modules/` means you will need to reinstall web
  dependencies before running or building the web client.
- Deleting Flutter/Gradle build folders means the next Flutter build may take
  longer while caches regenerate.
- If a listed path is missing, there is nothing to clean for that item.
