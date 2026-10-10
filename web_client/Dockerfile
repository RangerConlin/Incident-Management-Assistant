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
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Served at /app to match vite.config.ts's base: "/app/" — the same build
# output this image serves is also what create_app() mounts directly at
# /app for LAN/offline/direct-cloud access, so both serving paths agree on
# one asset-path convention.
COPY --from=build /build/dist /usr/share/nginx/html/app

EXPOSE 80
