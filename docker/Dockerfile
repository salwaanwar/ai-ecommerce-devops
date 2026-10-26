# Static e-commerce frontend served by non-root Nginx
FROM nginxinc/nginx-unprivileged:1.27-alpine

LABEL org.opencontainers.image.title="nexvion-ecommerce" \
      org.opencontainers.image.description="Nexvion e-commerce frontend served by Nginx"

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY application/ /usr/share/nginx/html/

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://localhost:8080/health || exit 1
