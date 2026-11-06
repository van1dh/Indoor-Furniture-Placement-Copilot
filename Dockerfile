# Build the frontend, then serve it and the API from one Python image on port 8000.
FROM node:22-alpine AS frontend
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html vite.config.js ./
COPY public public
COPY src src
# Same origin as the API, so requests go to /api/...
ENV VITE_API_URL=""
RUN npm run build

FROM python:3.11-slim
WORKDIR /app/server
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server/app.py server/placement_generation.py ./
COPY server/layout layout
COPY --from=frontend /app/dist /app/dist
RUN useradd --create-home app
USER app
ENV STATIC_DIR=/app/dist PORT=8000
EXPOSE 8000
# Pass ANTHROPIC_API_KEY at run time to turn on the Claude copilot
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port $PORT"]
