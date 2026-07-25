# syntax=docker/dockerfile:1

# ---------- deps: install node_modules from a clean lockfile ----------
FROM node:22-alpine AS deps
# libc6-compat: some Next/SWC native binaries expect glibc symbols on Alpine.
RUN apk add --no-cache libc6-compat
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ---------- builder: produce the standalone server bundle ----------
FROM node:22-alpine AS builder
RUN apk add --no-cache libc6-compat
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Guarantee a public/ dir exists — Next's public/ is optional and git doesn't
# track empty dirs, so it may be absent on a clean checkout (the runner COPYs it).
RUN mkdir -p public
ENV NEXT_TELEMETRY_DISABLED=1
# NEXT_PUBLIC_* is inlined at build time (it's browser-facing), so the public API
# URL must be supplied here: docker build --build-arg NEXT_PUBLIC_API_BASE_URL=...
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
RUN npm run build

# ---------- runner: minimal, non-root ----------
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN addgroup -g 10001 nodejs && adduser -u 10001 -G nodejs -S nextjs
# Standalone output + static assets + public dir are all that's needed at runtime.
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
