# ===== Сборка приложения =====
FROM node:18-alpine AS builder
WORKDIR /app

COPY package*.json ./
RUN npm install --legacy-peer-deps

COPY . .
RUN npm run build

# ===== Запуск через Next.js server =====
FROM node:18-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production

# копируем только готовый билд
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/node_modules ./node_modules

EXPOSE 3000
CMD ["npm", "start"]
