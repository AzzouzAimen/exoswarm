FROM node:24-alpine AS dependencies

WORKDIR /app
RUN npm install --global pnpm@11.10.0

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/package.json
RUN pnpm install --frozen-lockfile --filter @exoswarm/web...

FROM dependencies AS builder

COPY apps/web ./apps/web
COPY assets ./assets

ARG NEXT_PUBLIC_EXOSWARM_API_URL=https://exoswarm.duckdns.org
ENV NEXT_PUBLIC_EXOSWARM_API_URL=$NEXT_PUBLIC_EXOSWARM_API_URL

RUN pnpm --dir apps/web build

FROM node:24-alpine AS runner

ENV NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000

WORKDIR /app

RUN addgroup -S -g 10001 exoswarm \
    && adduser -S -D -H -u 10001 -G exoswarm exoswarm

COPY --from=builder --chown=exoswarm:exoswarm /app/apps/web/.next/standalone ./
COPY --from=builder --chown=exoswarm:exoswarm /app/apps/web/.next/static ./apps/web/.next/static

USER exoswarm

EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:3000').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"

CMD ["node", "apps/web/server.js"]
