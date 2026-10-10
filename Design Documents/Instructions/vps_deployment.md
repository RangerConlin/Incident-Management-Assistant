# VPS Deployment & Traefik

How hosted services in this repo (`cloud_server/`, `cloud_router/`,
`web_client/`) get packaged and reach Traefik on a VPS. Written after
`web_client/`'s own packaging got this wrong on the first pass — the
mistake and the fix are below so it isn't repeated.

## Pattern: each service packages itself, standalone

Every hosted service owns its own `Dockerfile` + `docker-compose.yml` (and
anything else it needs — `nginx.conf`, `.dockerignore`) inside its own
directory. No service's packaging reaches into another service's
directory, copies its files, or shares a Docker image/build context with
it. `cloud_server/`'s Dockerfile does copy `data/db/sarapp_db/` (the
shared API package every server runs), which is fine — that's the shared
backend package, not another *service's* packaging — but it never touches
`cloud_router/` or `web_client/`, and neither of those touches it back.

Treat each service's packaging files as being as off-limits to the others
as the hard rules already treat router/schema code: changing one
service's deployment is in scope; reaching into a different service's
directory to do it is not, even to fix something that looks related.

## Don't assume a shared Traefik network — check first

A common Compose+Traefik pattern is an `external: true` shared network
that every service joins so Traefik can route to it. **This repo's actual
VPS does not use that pattern.** Confirmed by running, not assumed:

```
docker network ls
docker ps --filter "name=traefik" --format '{{.Names}}'
docker inspect <that container name> \
  --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{"\n"}}{{end}}'
```

On the deployed VPS this prints `host` — Traefik runs with
`--network host`, not attached to any bridge network at all. It
discovers and reaches backend containers via the Docker socket (label
discovery) plus direct routing to each container's own bridge-network IP,
which a host-networked process can already reach without being a member
of that bridge network. `cloud_server`/`cloud_router` each confirm this:
`docker network ls` shows `cloud_server_sarapp-net` and
`cloud_router_sarapp-net` — each service's own private per-project
network, not a shared one either.

**Consequence**: a service's `docker-compose.yml` should not declare an
`external: true` shared network and should not require one to be created
first. Only the Traefik labels matter for discovery — no `networks:`
block needed beyond Compose's own default. `web_client/docker-compose.yml`
had this wrong on its first pass (required a nonexistent external
`traefik` network, which would have failed `docker compose up` outright)
until checked against the real box with the commands above and fixed.

**Do not assume this generalizes to every deployment.** If this app is
ever packaged for a *different* VPS, run the same three commands there
first — don't carry over "host networking, no shared network" as a fact
about Traefik in general. It is a fact about this one box, learned by
checking, not a property of Traefik as software.

## Routing convention

- `cloud_server`/`cloud_router`: `PathPrefix(`/r/<SARAPP_CONNECT_CODE>`)` —
  the connect-code path every client already uses (see
  `Design Documents/Instructions/cloud_router_architecture.md`).
  `cloud_server/prefix.py`'s `ConnectCodePrefixMiddleware` strips that
  prefix server-side before the shared FastAPI app sees the request.
- A static/standalone service with no connect code of its own (e.g.
  `web_client/`'s standalone container) uses a fixed rule instead — a
  `PathPrefix` on a path it owns outright (`/app`), or a dedicated
  `Host(...)` rule for its own subdomain. Either way, always
  `entrypoints=websecure` + `tls=true` to match how the existing services
  are fronted — don't add a plaintext HTTP router.

## Env var conventions

Follow the existing style (`cloud_server/docker-compose.yml`): required
values with no sensible default use Compose's `${VAR:?set VAR}` so
`docker compose up` fails loudly instead of silently deploying
misconfigured; everything else gets a `${VAR:-default}` so the service
runs out of the box with zero `.env` file. Never hardcode a secret or a
deployment-specific value (connect codes, passwords, URLs) directly in a
`docker-compose.yml` — env var only, same as `SARAPP_MONGO_URI` already
must never be hardcoded in application code.

## Verifying without a VPS

A sandbox/dev environment usually has no Docker daemon at all. What's
still checkable without one:
- `docker compose config` — resolves the compose file, env var defaults,
  and label interpolation without needing a running daemon. Catches YAML
  / variable-substitution mistakes (this is what caught nothing being
  wrong syntactically, even though the external-network *requirement*
  was still wrong until checked against the real box).
- The built static output's file layout actually matches what the
  Dockerfile `COPY`s and the web server roots (e.g. `npm run build` then
  compare `dist/`'s contents against the `COPY --from=build` line).

Say plainly when an actual `docker build`/`docker compose up` was not run
— "the config resolves cleanly" is not the same claim as "it builds and
runs," and this doc exists because a config that resolved cleanly still
had a requirement that would have failed on the real box.
