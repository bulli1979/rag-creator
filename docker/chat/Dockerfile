# Web-Chat (qa_site) — Build-Kontext: Repository-Root (../..)
FROM nginx:1.27-alpine

ARG DEFAULT_API_URL=http://localhost:8000
ARG DEFAULT_API_KEY=

COPY qa_site /usr/share/nginx/html
RUN printf 'window.__RAG_DEFAULT_API_URL__ = "%s";\nwindow.__RAG_DEFAULT_API_KEY__ = "%s";\n' "$DEFAULT_API_URL" "$DEFAULT_API_KEY" \
    > /usr/share/nginx/html/config.js

COPY docker/chat/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
