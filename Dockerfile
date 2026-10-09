# Build static assets separately; the runtime image does not need Node or npm.
FROM node:24-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 STATIC_DIR=/app/frontend/dist
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/entrypoint.sh ./entrypoint.sh
COPY --from=frontend /build/dist /app/frontend/dist
RUN useradd --create-home inventory && chown -R inventory:inventory /app
USER inventory
EXPOSE 8000
CMD ["sh", "entrypoint.sh"]
