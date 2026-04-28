# ─────────────────────────────────────────────────────────────────────
# Build stage — produce the static Vue bundle.
# ─────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build


# ─────────────────────────────────────────────────────────────────────
# Runtime stage — nginx serving the bundle + proxying /api/.
# ─────────────────────────────────────────────────────────────────────
FROM nginx:alpine

# Static bundle.
COPY --from=build /app/dist /usr/share/nginx/html

# nginx config goes into /etc/nginx/templates/ rather than /etc/nginx/conf.d/.
# The nginx:alpine entrypoint runs envsubst on every *.template file in
# /etc/nginx/templates/ at container start — replacing ${DOMAIN_NAME}
# (and any other env vars) with their runtime values, then writing the
# result to /etc/nginx/conf.d/. Lets us swap dogfood domains without
# rebuilding the image.
COPY nginx.conf /etc/nginx/templates/default.conf.template

EXPOSE 80 443

# Default CMD comes from the nginx:alpine base. The frontend service
# in docker-compose.prod.yml overrides with a wrapper that reloads
# nginx every 12h to pick up renewed Let's Encrypt certs.
