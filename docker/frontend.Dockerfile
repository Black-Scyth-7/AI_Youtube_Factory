# syntax=docker/dockerfile:1
# AI YouTube Factory — frontend image (Next.js standalone). Context = repo root.

FROM node:20-bookworm-slim AS base
ENV PNPM_HOME=/pnpm PATH="/pnpm:$PATH" NEXT_TELEMETRY_DISABLED=1
RUN corepack enable
WORKDIR /repo

# ---- install workspace dependencies (cached on manifests) ----
FROM base AS deps
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml turbo.json ./
COPY apps/frontend/package.json apps/frontend/package.json
COPY apps/admin/package.json apps/admin/package.json
COPY packages/ui/package.json packages/ui/package.json
COPY packages/shared/package.json packages/shared/package.json
COPY packages/config/package.json packages/config/package.json
COPY packages/eslint-config/package.json packages/eslint-config/package.json
COPY packages/typescript-config/package.json packages/typescript-config/package.json
RUN pnpm install --frozen-lockfile

# ---- build the frontend app ----
FROM deps AS build
COPY . .
RUN pnpm --filter @ayf/frontend build

# ---- minimal runtime using Next standalone output ----
FROM node:20-bookworm-slim AS runtime
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000
WORKDIR /app
RUN groupadd --system nodejs && useradd --system --gid nodejs nextjs
COPY --from=build --chown=nextjs:nodejs /repo/apps/frontend/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /repo/apps/frontend/.next/static ./apps/frontend/.next/static
COPY --from=build --chown=nextjs:nodejs /repo/apps/frontend/public ./apps/frontend/public
USER nextjs
EXPOSE 3000
CMD ["node", "apps/frontend/server.js"]
