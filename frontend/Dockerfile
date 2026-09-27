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

# Installed as templates, not as conf.d/default.conf, so the base image's
# entrypoint expands ${API_UPSTREAM} from the environment. That is what lets one
# built image serve staging and production without a rebuild.
#
# The two .conf files are `include`d by the site config rather than pasted into it.
# nginx drops every inherited `add_header` as soon as a level defines one of its own,
# so the security headers have to be re-included at each level that sets a header;
# a single copy inside the server block would silently vanish from /assets/ and from
# index.html. See the comment at the top of nginx-security-headers.conf.
COPY --from=build /srv/app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY nginx-security-headers.conf /etc/nginx/nginx-security-headers.conf
COPY nginx-proxy-api.conf /etc/nginx/nginx-proxy-api.conf

# Fail the build on a broken config rather than shipping an image that will not start.
# The template still holds ${API_UPSTREAM} at build time - the entrypoint expands it at
# container start - so it is expanded to a placeholder here to make `nginx -t` resolve the
# includes for real. A missing or malformed snippet then fails the build instead of the
# deployment. The rendered file is removed so it cannot shadow the entrypoint's own.
RUN sed 's|\${API_UPSTREAM}|127.0.0.1:8000|' /etc/nginx/templates/default.conf.template \
      > /etc/nginx/conf.d/default.conf \
 && nginx -t \
 && rm -f /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["nginx", "-t"]
