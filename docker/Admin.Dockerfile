FROM node:20-alpine AS admin-build
RUN mkdir -p /home/node/app/node_modules && chown -R node:node /home/node/app
WORKDIR /home/node/app
COPY ./src/admin/package*.json ./
USER node
RUN npm ci
COPY --chown=node:node ./src/admin ./admin
WORKDIR /home/node/app/admin
RUN npm run build

FROM nginx:alpine
COPY --from=admin-build /home/node/app/dist/admin /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
