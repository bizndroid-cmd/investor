# =============================================================================
# Production Dockerfile for React Frontend (Multi-stage, Static Build)
# =============================================================================

FROM node:18-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --production=false

COPY . .

ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# Stage 2: Minimal static file output (copied to Caddy volume)
FROM alpine:3.19 AS output
COPY --from=builder /app/dist /static
