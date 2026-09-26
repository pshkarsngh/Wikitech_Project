# Release image for the SPA. Built once, then served by nginx with no Node
# runtime in the final image.
FROM node:24-alpine AS build

WORKDIR /srv/app

# Lockfile-driven install so the image is reproducible. npm ci needs both files.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Left unset on purpose. The client defaults to a relative '/api', which nginx
# reverse-proxies to the backend on the same origin, so the release build needs
# no backend URL compiled into it and no CORS allowance to work.
RUN npm run build

FROM nginx:1.27-alpine AS runtime

# Installed as a template, not as conf.d/default.conf, so the base image's
# entrypoint expands ${API_UPSTREAM} from the environment. That is what lets one
# built image serve staging and production without a rebuild.
COPY --from=build /srv/app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["nginx", "-t"]
