FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY tsconfig.json tsconfig.build.json nest-cli.json ./
COPY src ./src
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY package.json package-lock.json* ./
RUN npm install --omit=dev
COPY --from=builder /app/dist ./dist
RUN addgroup -S app && adduser -S app -G app \
  && chown -R app:app /app
EXPOSE 3001
HEALTHCHECK --interval=10s --timeout=5s --retries=6 --start-period=15s \
  CMD wget -qO- http://127.0.0.1:3001/api/health || exit 1
USER app
CMD ["node", "dist/main.js"]
