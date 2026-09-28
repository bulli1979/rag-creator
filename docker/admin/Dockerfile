# Admin-Web (`adminWeb`) — Build-Kontext: Repository-Root
FROM node:20-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
COPY adminWeb/package.json adminWeb/package.json
COPY documentHandling/apps/renderer/package.json documentHandling/apps/renderer/package.json
COPY documentHandling/apps/main/package.json documentHandling/apps/main/package.json
COPY documentHandling/packages/shared/package.json documentHandling/packages/shared/package.json
COPY chatBot/apps/renderer/package.json chatBot/apps/renderer/package.json
COPY chatBot/apps/main/package.json chatBot/apps/main/package.json
COPY chatBot/packages/shared/package.json chatBot/packages/shared/package.json

RUN npm ci --ignore-scripts || npm install

COPY documentHandling/packages/shared documentHandling/packages/shared
COPY adminWeb adminWeb
COPY tsconfig.base.json tsconfig.base.json

RUN npm run build --workspace @rag/admin-web

FROM nginx:1.27-alpine
COPY --from=build /app/adminWeb/dist /usr/share/nginx/html
COPY docker/admin/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
