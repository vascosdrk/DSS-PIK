# ==============================================================================
# DSS-PIK Frontend — Multi-Stage Production Dockerfile (Node 22 -> Nginx)
# Build context: ./frontend
# ==============================================================================

FROM node:22-alpine AS builder
WORKDIR /build

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . ./
RUN npm run build

FROM nginx:1.27-alpine AS runtime

RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /build/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1:80/ > /dev/null 2>&1 || exit 1
