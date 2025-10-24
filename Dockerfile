# Multi-stage build for CEO's Scenes Media Pipeline

# Stage 1: Build Frontend
FROM node:18-alpine as frontend-build
WORKDIR /app/frontend

# Copy frontend dependencies
COPY frontend/package*.json ./
RUN npm ci --only=production

# Copy frontend source and build
COPY frontend/ ./
RUN npm run build

# Stage 2: Setup Backend
FROM node:18-alpine as backend-build
WORKDIR /app/backend

# Copy backend dependencies
COPY backend/package*.json ./
RUN npm ci --only=production

# Copy backend source
COPY backend/ ./

# Stage 3: Production Runtime with Python and FFmpeg
FROM python:3.11-slim

# Install Node.js, FFmpeg, and system dependencies
RUN apt-get update && apt-get install -y \
    nodejs \
    npm \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python scripts and requirements
COPY requirements.txt ./
COPY download.py image.py video.py ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend from build stage
COPY --from=backend-build /app/backend ./backend

# Copy frontend build from build stage
COPY --from=frontend-build /app/frontend/build ./frontend/build

# Create necessary directories
RUN mkdir -p input_images input_videos output_images output_videos downloaded_images downloaded_videos

# Set environment variables
ENV NODE_ENV=production
ENV PORT=5000

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:5000/api/health || exit 1

# Start the backend server
CMD ["node", "backend/index.js"]
