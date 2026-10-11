# Repository Layout Direction

Status: approved

This project is moving toward a single monorepo that produces multiple
distribution artifacts: a Windows desktop installer, a mobile app bundle, a
web client container or static build, and separate server/router containers.

The repo should be organized by runtime ownership and shared contracts, not by
a broad frontend/backend split.

## Target Tree

```text
Incident-Management-Assistant/
  apps/
    desktop/
      sarapp_desktop/
        modules/
        ui/
        panels/
        bridge/
        models/
        notifications/
        profiles/
        assets/
        settings/
        styles/
        utils/
      main.py
      requirements.txt
      pyproject.toml

    mobile/
      android/
      ios/
      lib/
      test/
      web/
      windows/
      assets/
      pubspec.yaml

    web/
      src/
      public/
      package.json
      vite.config.* / equivalent

  services/
    lan_server/
      main.py
      console/
      networking/

    cloud_server/
      main.py
      runtime/
      dashboard/

    cloud_router/
      main.py
      router/
      master_db/
      networking/

  server/
    sarapp_api/
      app.py
      routers/
        planning/
        logistics/
        operations/
        communications/
        safety/
        medical/
        liaison/
        finance/
        admin/
        mobile/
      schemas/
      dependencies/

    sarapp_db/
      mongo/
      repositories/
      collection_names.py
      sync/
      seed_loaders/

  shared/
    api_contract/
      openapi.json

    clients/
      python/
      dart/
      typescript/

    domain/
      constants/
      enums/
      schemas/

  data/
    fixtures/
    templates/
    sample_incidents/
    seed_catalogs/
    profiles/

  infra/
    docker/
      web.Dockerfile
      lan-server.Dockerfile
      cloud-server.Dockerfile
      cloud-router.Dockerfile
    compose/
    systemd/
    nginx/
    deploy/

  tools/
    scripts/
    dev/
    audits/

  docs/
    architecture/
    deployment/
    api/
```

## Ownership Rules

- `apps/desktop` owns the PySide desktop client, including desktop modules,
  UI, panels, bridge code, desktop models, notifications, styles, settings,
  assets, and desktop packaging.
- `apps/mobile` owns the Flutter mobile client and platform-specific mobile
  build files.
- `apps/web` owns the browser client.
- `server` owns FastAPI routers, backend schemas, backend validation, database
  access, sync, and server-side data behavior.
- `services` owns runtime wrappers and process entrypoints for LAN server,
  cloud server, and cloud router roles.
- `shared` owns API contracts, generated clients, and stable cross-runtime
  constants, enums, and schemas.
- `data` owns content files such as templates, fixtures, sample incidents,
  profiles, and seed catalog source files.
- `infra` owns Dockerfiles, compose files, systemd units, nginx config, and
  deployment scripts.
- `tools` owns development scripts, audits, one-off utilities, and local
  maintenance helpers.

## Dependency Rules

```text
apps/*       -> shared/* -> HTTP API -> server/*
services/*   -> server/* + shared/*
server/*     -> shared/*
shared/*     -> imports nothing project-specific
```

Client apps should not import server implementation code directly. They should
use generated or thin clients from `shared` and communicate with the backend
over the API boundary.

Server code should not import app code. Runtime-specific service wrappers may
import server packages and shared packages.

## Distribution Mapping

```text
apps/desktop   -> Windows desktop installer
apps/mobile    -> mobile app bundle
apps/web       -> web container or static web build
services/*     -> server/router Docker containers
server/*       -> included by service containers
shared/*       -> included or generated into each artifact as needed
```

Build artifacts should be produced intentionally from the relevant source
subtree instead of using sparse checkouts as the main deployment boundary.

## Migration Notes

The migration should be staged. Move runtime entrypoints and obvious client
trees first, then move backend API/database implementation code after the app
boundaries are stable.

The desktop module code should move under `apps/desktop` because it is
primarily desktop/client code. The mobile app should be merged under
`apps/mobile`, and the web client should live under `apps/web`.

Avoid turning `shared` into a junk drawer. Code belongs in `shared` only when
multiple runtimes need it and it is stable enough to act as a contract.
