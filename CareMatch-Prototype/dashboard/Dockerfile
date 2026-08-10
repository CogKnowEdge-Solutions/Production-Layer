# CareMatch dashboard. Multi-stage: build the TanStack Start app with Nitro's
# "node-server" preset (set in vite.config.ts), then ship only the built
# .output/ to a slim runtime image and run it with plain `node`. The Nitro
# node-server preset bundles its dependencies, so no node_modules are needed.
FROM node:22-slim AS build
WORKDIR /app/dashboard

COPY dashboard/package.json ./
RUN npm install

COPY dashboard .
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NITRO_PORT=8080
COPY --from=build /app/dashboard/.output /app/.output
EXPOSE 8080
CMD ["node", ".output/server/index.mjs"]
