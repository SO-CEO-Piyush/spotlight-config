# Multi-stage build for CEO's Scenes Media Pipeline

# Stage 1: Build Frontend
FROM node:18-alpine AS frontend-build
WORKDIR /app/frontend

# Copy package files and install dependencies
COPY frontend/package*.json ./
RUN npm install --production

# Copy frontend source and build
COPY frontend/ ./
RUN npm run build

# Stage 2: Setup Backend
FROM node:18-alpine AS backend-build
WORKDIR /app/backend

# Copy package files and install dependencies
COPY backend/package*.json ./
RUN npm install --production

# Copy backend source
COPY backend/ ./

# Stage 3: Production Runtime with Python and FFmpeg
FROM python:3.11-slim

# Install Node.js, npm, FFmpeg, and curl
RUN apt-get update && apt-get install -y \
    nodejs \
    npm \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python requirements and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy Python scripts
COPY download.py image.py video.py ./

# Copy backend with node_modules from build stage
COPY --from=backend-build /app/backend ./backend

# Copy frontend build from build stage
COPY --from=frontend-build /app/frontend/build ./frontend/build

# Create necessary directories for media files
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
