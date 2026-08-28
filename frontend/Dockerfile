FROM node:22-alpine AS frontend-build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build
# Kết quả nằm ở /app/dist, được Dockerfile của backend chép sang
