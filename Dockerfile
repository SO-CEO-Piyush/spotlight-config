# Single-stage build - simpler and more reliable for Railway
FROM python:3.11-slim

# Install Node.js, npm, FFmpeg, and system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy Python scripts
COPY download.py image.py video.py ./

# Copy and build frontend
COPY frontend/package*.json ./frontend/
WORKDIR /app/frontend
RUN npm install
COPY frontend/ ./
RUN npm run build

# Copy and setup backend
WORKDIR /app
COPY backend/package*.json ./backend/
WORKDIR /app/backend
RUN npm install
COPY backend/ ./

# Create necessary directories
WORKDIR /app
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
