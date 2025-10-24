# Product Requirements Document

**Tool:** CEO's Scenes Media Processing Pipeline  
**Version:** 2.0 - Integrated Download, Transform & Map System

---

## Why

- Content creators need consistent, mobile-friendly media (3:4 portrait format) with a clean, branded look for social media platforms
- Media files come from multiple sources (Azure blob storage, CDNs) in various formats, sizes, and aspect ratios
- Manual downloading, tracking, resizing, and mapping hundreds of files to spreadsheet records is time-consuming and error-prone
- Platforms enforce strict file-size limits (≤10 MB) requiring automated optimization
- Need automated pipeline to download → transform → upload → map files to business records in Google Sheets

---

## What

### 1. **Automated Media Download System** (`download.py`)
   - Download images and videos from multiple cloud sources
   - **StepZero Azure Blob Storage Integration**
     - Extract UUID from StepZero URLs (`/image_editing/{UUID}/`)
     - Save files with UUID-based naming: `{UUID}.jpeg`
     - Handle SAS token authentication and query parameters
     - Support URLs with `|||` delimiters
   - **Swiggy CDN Integration**
     - Extract Event IDs from media-assets URLs
     - Save files with Event ID naming: `{eventId}.{extension}`
     - Preserve original file extensions
   - **Intelligent Download Strategy**
     - Use `wget` for StepZero URLs (better blob storage compatibility)
     - Use `curl` for Swiggy CDN URLs
     - Skip already downloaded files
     - Detailed logging with success/failure tracking

### 2. **Aspect-Ratio Transformation Pipeline**
   - **Images** (`image.py`): Auto-crop to 3:4 portrait ratio
   - **Videos** (`video.py`): Hardware-accelerated video cropping and encoding

### 3. **Rounded Border & Canvas Design**
   - Proportional rounded-corner white border overlay
   - Black canvas background for visual padding and brand consistency
   - Optimized for mobile viewing experience

### 4. **Google Drive Integration** (`code.gs`)
   - **Intelligent File Mapping System**
     - Priority 1: StepZero UUID mapping (Column T → Column V)
       - Extract UUID from StepZero URL in spreadsheet
       - Match with `{UUID}.jpeg` files in Google Drive
     - Priority 2: Event ID mapping (Column N → Column V) 
       - Fallback to Event ID if no StepZero file found
       - Support multiple extensions (.jpeg, .jpg, .png, etc.)
   - **Video Mapping** (Column N → Column W)
     - Map video files by Event ID to `.mp4` format
   - **Smart Processing**
     - Skip rows already mapped (avoid overwrites)
     - Detailed logging with breakdown statistics
     - Real-time progress notifications

### 5. **Batch & Interactive Processing Modes**
   - CLI menu to pick individual videos
   - `--bulk` flag for multi-CPU parallel processing
   - Separate modes for images vs videos

### 6. **Quality & Size Enforcement**
   - Hardware acceleration (VideoToolbox on macOS) when available
   - Software fallback (libx264/libx265) for compatibility
   - **Enforced 10 MB max file-size limit**
     - Two-pass re-encode at calculated bitrate if oversize
     - Automatic quality adjustment to meet size constraints
   - Optimized JPEG encoding (quality 95, no chroma subsampling)

### 7. **Progress & Feedback**
   - Real-time progress bars for FFmpeg operations
   - Download status tracking (✓ Success, ✗ Failed, → Already exists)
   - Processing summaries with timing and speed metrics
   - Google Sheets toast notifications with mapping statistics

### 8. **Supported Formats**
   - **Images:** PNG, JPEG, JPG, WEBP, GIF (input) → JPEG (output)
   - **Videos:** MP4, MOV, AVI, MKV, WEBM, FLV, TS, MPG → MP4 (output)

---

## How

### 1. **Download Pipeline** (`download.py`)

**Input:**
- `links_images.txt`: Image URLs (StepZero and Swiggy)
- `links_videos.txt`: Video URLs

**Process:**
- Parse URLs line by line
- **StepZero URLs:**
  ```
  https://stepzero.blob.core.windows.net/filesnew/default/events_qc/image_editing/{UUID}/uploadForm|||Listing_0_LISTING.jpg?se=...
  ```
  - Extract UUID using regex: `/image_editing/([a-f0-9-]{36})/`
  - Download with `wget -O {UUID}.jpeg {FULL_URL}`
  - Save to `downloaded_images/`

- **Swiggy URLs:**
  ```
  https://media-assets.swiggy.com/swiggy/..._MEDIA.jpeg
  ```
  - Extract Event ID from pattern: `{UUID}_(\d+)MEDIA`
  - Download with `curl` and preserve extension
  - Save to `downloaded_images/`

- **Video Downloads:**
  - Extract Event ID and download to `downloaded_videos/`

**Output:**
- `downloaded_images/{UUID}.jpeg` or `{eventId}.{ext}`
- `downloaded_videos/{eventId}.mp4`

### 2. **Image Processing Pipeline** (`image.py`)

**Input:** `input_images/` (or `downloaded_images/`)

**Process:**
- Scan for image files
- Crop to 3:4 aspect ratio (center-weighted)
- Create rounded corner mask with white border
- Composite onto black canvas with padding
- Save as optimized JPEG (quality 95, no subsampling)

**Output:** `output_images/` with same filenames

### 3. **Video Processing Pipeline** (`video.py`)

**Input:** `input_videos/` (or `downloaded_videos/`)

**Process:**
- Interactive mode: CLI menu to select videos
- Bulk mode: Process all videos in parallel
- For each video:
  1. Probe dimensions and duration via FFmpeg
  2. Calculate 3:4 crop region (center-weighted)
  3. Generate rounded corner mask and border using PIL
  4. Build FFmpeg filter chain:
     - `crop` → center-crop to 3:4
     - `alphamerge` → apply rounded mask
     - `overlay` → composite onto black canvas
     - `format=yuv420p` → ensure compatibility
  5. Encode with optimal codec settings
  6. Check file size, re-encode at lower bitrate if > 10 MB
  7. Show real-time progress bar

**Output:** `output_videos/` with same filenames (≤ 10 MB)

### 4. **Google Drive Mapping** (`code.gs`)

**Prerequisites:**
- Processed files uploaded to Google Drive folder
- Google Sheets with data starting at row 3

**Process:**
1. Scan Google Drive folder and build filename → file ID map
2. Read spreadsheet data:
   - Column N: Backend Event ID
   - Column T: Event Hero Enhanced Image (StepZero URLs)
   - Column V: Output Spotlight Image (target for mapping)
   - Column W: Output Spotlight Video (target for video mapping)

3. For each row (images):
   - **Try StepZero mapping first:**
     - Extract UUID from Column T URL
     - Look for `{UUID}.jpeg` in Drive
     - If found, write Drive link to Column V
   - **Fall back to Event ID mapping:**
     - Look for `{eventId}.jpeg`, `.jpg`, `.png` in Drive
     - If found, write Drive link to Column V
   - Mark as "NOT FOUND" if neither succeeds

4. For each row (videos):
   - Look for `{eventId}.mp4` in Drive
   - Write Drive link to Column W or "NOT FOUND"

5. Log statistics:
   - Total found (breakdown by StepZero vs Event ID)
   - Not found count
   - Skipped (already filled) count

**Output:** Google Drive links populated in spreadsheet

### 5. **Configuration & Extensibility**

- Constants at top of each script for easy customization
- CLI flags: `--bulk`, `--input-folder`, `--output-folder`, `--jobs`
- Configurable codec, quality, max file size, and folder paths
- Google Apps Script settings for folder ID, sheet name, column mappings

### 6. **Dependencies**

**Python:**
- Python ≥ 3.8
- Pillow (PIL) for image processing
- FFmpeg on PATH with hardware acceleration support
- Standard library: `subprocess`, `pathlib`, `re`, `concurrent.futures`

**System:**
- `curl` for Swiggy downloads
- `wget` for StepZero downloads
- Google Apps Script environment for Drive integration

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     MEDIA PROCESSING PIPELINE                │
└─────────────────────────────────────────────────────────────┘

1. DOWNLOAD STAGE
   ┌──────────────────┐
   │ links_images.txt │──┐
   │ links_videos.txt │  │
   └──────────────────┘  │
                         ▼
                   ┌─────────────┐
                   │ download.py │
                   └─────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
   StepZero URLs    Swiggy URLs     Video URLs
   (wget UUID)      (curl EventID)  (curl EventID)
        │                │                │
        └────────────────┼────────────────┘
                         ▼
              ┌─────────────────────┐
              │ downloaded_images/  │
              │ downloaded_videos/  │
              └─────────────────────┘

2. TRANSFORM STAGE
   ┌─────────────────┐         ┌─────────────────┐
   │ input_images/   │         │ input_videos/   │
   └─────────────────┘         └─────────────────┘
           │                           │
           ▼                           ▼
      ┌──────────┐              ┌──────────┐
      │ image.py │              │ video.py │
      └──────────┘              └──────────┘
           │                           │
           │ • Crop 3:4                │ • Crop 3:4
           │ • Round borders           │ • Round borders
           │ • Black canvas            │ • Black canvas
           │ • JPEG optimize           │ • ≤10MB enforce
           │                           │ • HW acceleration
           ▼                           ▼
   ┌─────────────────┐         ┌─────────────────┐
   │ output_images/  │         │ output_videos/  │
   └─────────────────┘         └─────────────────┘

3. UPLOAD & MAP STAGE
   ┌─────────────────┐
   │ Upload files to │
   │ Google Drive    │
   └─────────────────┘
           │
           ▼
   ┌──────────────────────────┐
   │  Google Apps Script      │
   │  (code.gs)               │
   │                          │
   │  • Read Column T (UUID)  │
   │  • Read Column N (ID)    │
   │  • Map to Column V/W     │
   │  • Priority: UUID first  │
   └──────────────────────────┘
           │
           ▼
   ┌──────────────────────────┐
   │  Google Sheets Updated   │
   │  with Drive links        │
   └──────────────────────────┘
```

---

## Success Metrics

### Visual Quality
- ✓ All outputs are exactly 3:4 portrait aspect ratio
- ✓ Consistent rounded borders with white overlay
- ✓ Professional black canvas padding
- ✓ High-quality encoding (JPEG quality 95, video CRF 23)

### File Management
- ✓ 100% of videos ≤ 10 MB file size
- ✓ Automatic UUID extraction accuracy > 99%
- ✓ Event ID extraction accuracy > 99%
- ✓ No duplicate downloads (skip existing files)

### Performance
- ✓ Download speed limited only by network bandwidth
- ✓ Image processing: < 1 second per image
- ✓ Video interactive mode: ≥ real-time speed per video
- ✓ Video bulk mode: Linear scaling with CPU cores
- ✓ Google Drive mapping: < 1 second per row

### Reliability
- ✓ Zero failed conversions under normal conditions
- ✓ Graceful error handling with detailed logging
- ✓ Preserves existing mappings (skip already-filled rows)
- ✓ Fallback mechanisms (UUID → Event ID, HW → SW encoding)

### Integration
- ✓ 100% automated pipeline from download to spreadsheet
- ✓ Support for multiple media sources (StepZero, Swiggy, etc.)
- ✓ Real-time progress tracking and notifications
- ✓ Detailed statistics and summaries at each stage

---

## Who

### Primary Users
- **Social Media Managers:** Need consistent 3:4 portrait content for Instagram, Facebook, TikTok
- **Marketing Teams:** Process bulk media campaigns with hundreds of assets
- **Content Operations:** Map processed media to business records in spreadsheets

### Secondary Users
- **Developers:** Integrate media pipeline into larger automation workflows
- **Data Analysts:** Track media processing metrics and file relationships
- **QA Teams:** Verify media quality and mapping accuracy

---

## File Structure

```
image-to-video/
├── download.py              # Download automation script
├── image.py                 # Image transformation pipeline
├── video.py                 # Video transformation pipeline
├── code.gs                  # Google Apps Script for Drive mapping
├── requirements.txt         # Python dependencies
├── PRD.md                   # This document
├── ARCHITECTURE.md          # Technical architecture details
├── README.md                # Setup and usage instructions
│
├── links_images.txt         # Input: Image URLs to download
├── links_videos.txt         # Input: Video URLs to download
│
├── downloaded_images/       # Downloaded raw images
├── downloaded_videos/       # Downloaded raw videos
├── input_images/            # Images ready for processing
├── input_videos/            # Videos ready for processing
├── output_images/           # Processed images (3:4 + borders)
└── output_videos/           # Processed videos (3:4 + borders, ≤10MB)
```

---

## Usage Workflow

### End-to-End Pipeline

1. **Prepare Links:**
   ```bash
   # Add StepZero and Swiggy URLs to:
   # - links_images.txt
   # - links_videos.txt
   ```

2. **Download Media:**
   ```bash
   python3 download.py
   # Downloads to: downloaded_images/, downloaded_videos/
   ```

3. **Process Images:**
   ```bash
   # Copy/move files from downloaded_images/ to input_images/
   python3 image.py
   # Output: output_images/ with 3:4 aspect ratio
   ```

4. **Process Videos:**
   ```bash
   # Interactive mode (select individual videos):
   python3 video.py
   
   # Bulk mode (process all videos):
   python3 video.py --bulk --jobs 4
   # Output: output_videos/ with 3:4 aspect ratio, ≤10MB
   ```

5. **Upload to Google Drive:**
   ```bash
   # Manually upload output_images/ and output_videos/
   # to your Google Drive folder
   ```

6. **Map Files in Spreadsheet:**
   ```javascript
   // In Google Sheets:
   // Tools → Script Editor → Paste code.gs
   // Run: mapDriveImages()
   
   // Result: Column V and W populated with Drive links
   ```

---

## Future Enhancements

- [ ] Direct Google Drive upload from Python scripts
- [ ] Web UI for monitoring and control
- [ ] Support for additional media sources (S3, Cloudinary, etc.)
- [ ] Automated spreadsheet updates via Google Sheets API
- [ ] Custom watermarking and branding overlays
- [ ] Video thumbnail generation
- [ ] Duplicate detection and deduplication
- [ ] Batch retry mechanism for failed downloads
- [ ] Email/Slack notifications on pipeline completion

---

**Last Updated:** October 1, 2025  
**Version:** 2.0.0
