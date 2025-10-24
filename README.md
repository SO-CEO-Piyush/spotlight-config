# CEO's Scenes Media Pipeline 🎬

[![Production Ready](https://img.shields.io/badge/production-ready-brightgreen)]()
[![Docker](https://img.shields.io/badge/docker-enabled-blue)]()
[![Dark Mode](https://img.shields.io/badge/dark%20mode-supported-yellow)]()

# Image and Video Processing Scripts

This repository contains two scripts that process media files with identical visual transformations:
- `image.py` - Processes images using PIL/Pillow
- `video.py` - Processes videos using ffmpeg

## Features

Both scripts provide the following capabilities:

1. **Aspect Ratio Conversion**: Converts media to 3:4 aspect ratio
   - Wide media: Center-cropped horizontally
   - Tall media: Top-cropped vertically

2. **Rounded Corners**: Adds rounded corners with proportional radius

3. **Semi-transparent Border**: Adds a white border with 15% opacity

4. **Black Canvas**: Places the processed media on a larger 3:4 black canvas (1.2x the original height)

## Installation

### For Image Processing

```bash
pip install -r requirements.txt
```

### For Video Processing

Install ffmpeg based on your operating system:

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt-get install ffmpeg
```

**Windows:**
Download from [ffmpeg.org](https://ffmpeg.org/download.html)

## Usage

### Image Processing

```bash
python image.py
```

By default, processes images from the same directory. You can modify the input/output folders in the script:
```python
INPUT_FOLDER = "/path/to/input/images"
OUTPUT_FOLDER = "/path/to/output/images"
```

Supported formats: PNG, JPG, JPEG, BMP, GIF, TIFF, AVIF

### Video Processing

```bash
python video.py
```

**Interactive Features:**
- **Multi-select Support**: Choose multiple videos to process at once
- **Selection Options**:
  - Enter numbers separated by spaces (e.g., `1 3 5`)
  - Type `all` to select all videos
  - Type `sample` to create and process test videos
  - Press Enter to exit without processing
- **Video Information**: Shows resolution and duration for each video
- **Confirmation**: Review your selection before processing begins

Configure input/output folders and codec settings in the script:
```python
INPUT_FOLDER = "/path/to/input/videos"
OUTPUT_FOLDER = "/path/to/output/videos"
OUTPUT_CODEC = 'h264'  # Options: h264, h265, vp9, prores
OUTPUT_FORMAT = 'mp4'  # Options: mp4, mov, mkv, webm
```

Supported formats: MP4, AVI, MOV, MKV, FLV, WMV, WEBM, M4V, MPG, MPEG

## Video Codec Options

- **h264**: Most compatible, good quality/size balance (default)
- **h265**: Better compression than h264, less compatible
- **vp9**: Good for web, supports transparency
- **prores**: High quality, large file size, good for editing

## Processing Details

### Border and Radius Calculation
- Border size: `width * (2/360)` pixels (minimum 1px for images, 2px for videos)
- Corner radius: `width * (16/360)` pixels

### Canvas Sizing
- Height: Original height × 1.2, rounded to nearest multiple of 4
- Width: Calculated from height to maintain 3:4 ratio
- Videos ensure even dimensions for codec compatibility

### Quality Settings
- Images: JPEG quality 100%
- Videos: CRF 18 (high quality), AAC audio at 192kbps

## Example Transformations

1. **Wide Content (16:9)** → Center-cropped to 3:4
2. **Tall Content (9:16)** → Top-cropped to 3:4
3. **Square Content (1:1)** → Top-cropped to 3:4

All processed media maintains the visual style of rounded corners, semi-transparent border, and black letterboxing for consistent presentation.

## Development Setup

1. Fix npm cache ownership if needed:

   ```bash
   sudo chown -R $(id -u):$(id -g) ~/.npm
   ```

2. Install dependencies and start servers:

   ```bash
   npm install
   cd frontend && npm install
   cd ../backend && npm install
   cd ..
   npm run start
   ```

3. Open http://localhost:3000 in your browser.

## 🚀 Cloud Deployment

**Your app is production-ready!** See [DEPLOYMENT.md](DEPLOYMENT.md) for complete guides.

**Quick Deploy (Railway - Recommended):**
```bash
git init && git add . && git commit -m "Deploy"
# Then go to railway.app → Deploy from GitHub
```

**Other Options:** Render, Google Cloud Run, AWS, DigitalOcean, Heroku

---

## Docker Deployment

Build and run the container:

```bash
# Build the image
docker build -t media-pipeline .

# Run the container
docker run -p 5000:5000 media-pipeline
```

In production, the React frontend is served by the Express backend at http://localhost:5000# spotlight-config
