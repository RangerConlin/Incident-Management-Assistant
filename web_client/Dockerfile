# Self-contained image for web_client/ — same packaging pattern as
# cloud_server/ and cloud_router/ (own Dockerfile, own docker-compose.yml,
# Traefik labels), but standalone: this never touches those directories or
# their images. Build context is web_client/ itself.

FROM node:20.17-alpine AS build
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
# ca-certificates for verifying the backend's TLS cert when nginx proxies
# /api/ to it (see nginx.conf.template) — not present in the base image.
# `apk update` first: without it, apk installs whatever ca-certificates
# version was current when this Alpine base image itself was built, which
# can be stale enough to miss a newer Let's Encrypt root/intermediate
# (hit this directly: the base image's bundle was dated ~April 2025 and
# failed to verify a real cert chaining through a newer intermediate that
# the VPS host's own, independently-updated bundle verified fine).
RUN apk update && apk add --no-cache ca-certificates
# .template: substituted by the image's own built-in envsubst-on-templates
# entrypoint (reads SARAPP_BACKEND_HOST/SARAPP_BACKEND_CONNECT_CODE from
# the container environment) into /etc/nginx/conf.d/default.conf at
# startup — not a static file copy.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
# Served at /app to match vite.config.ts's base: "/app/" — the same build
# output this image serves is also what create_app() mounts directly at
# /app for LAN/offline/direct-cloud access, so both serving paths agree on
# one asset-path convention.
COPY --from=build /build/dist /usr/share/nginx/html/app

EXPOSE 80
