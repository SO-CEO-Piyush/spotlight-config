#!/usr/bin/env python3

import re
import subprocess
from pathlib import Path
import argparse

IMAGE_INPUT_FILE = "links_images.txt"
VIDEO_INPUT_FILE = "links_videos.txt"
INPUT_IMAGE_FOLDER = "input_images"
INPUT_VIDEO_FOLDER = "input_videos"
Path(INPUT_IMAGE_FOLDER).mkdir(exist_ok=True)
Path(INPUT_VIDEO_FOLDER).mkdir(exist_ok=True)

def extract_event_id(line):
    """Extract event ID from URL"""
    match = re.search(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}_(\d+)MEDIA', line)
    return match.group(1) if match else None

def extract_extension(line):
    """Extract file extension"""
    match = re.search(r'\.(jpg|jpeg|png|gif|webp)', line, re.IGNORECASE)
    return match.group(0) if match else '.jpeg'

def extract_uuid(line):
    """Extract UUID from StepZero URL path (specifically from image_editing path)"""
    # Try specific image_editing path first (more precise)
    match = re.search(r'/image_editing/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/', line, re.IGNORECASE)
    if match:
        return match.group(1)
    # Fallback to generic UUID extraction
    match = re.search(r'/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})/', line)
    return match.group(1) if match else None

def extract_video_extension(line):
    """Extract video file extension from URL or filename"""
    match = re.search(r'\.(mp4|mov|avi|mkv|webm|flv|ts|mpg)', line, re.IGNORECASE)
    return match.group(0) if match else ''

def download_file(url, output_path, validate=False):
    """
    Try to download file, return True if successful
    validate=True will use -f flag to fail on HTTP errors (for blob validation)
    """
    try:
        cmd = ['curl', '-s', '-L', '-o', output_path, url]
        if validate:
            cmd.insert(2, '-f')  # Add -f flag for validation
        
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        
        if result.returncode == 0 and Path(output_path).stat().st_size > 0:
            return True
        else:
            # Log curl error output for debugging
            err = result.stderr.decode('utf-8', errors='replace').strip()
            print(f"  DEBUG: curl failed for {url}\n    stderr: {err}")
            Path(output_path).unlink(missing_ok=True)
            return False
    except Exception as e:
        Path(output_path).unlink(missing_ok=True)
        return False

def process_image_line(line):
    """Process a single line from the file"""
    line = line.strip()
    if not line:
        return
    
    # Check for StepZero URL and download by UUID using wget
    if line.startswith('https://stepzero.blob.core.windows.net'):
        # Use the entire line as the URL (don't split on |||)
        full_url = line.strip()
        
        # Extract UUID from URL path
        uuid = extract_uuid(full_url)
        if not uuid:
            print(f"⊘ Skipping StepZero (no UUID found in URL)")
            print(f"   URL: {full_url}")
            return
        
        # Always use .jpeg extension for StepZero files
        output_file = Path(INPUT_IMAGE_FOLDER) / f"{uuid}.jpeg"
        
        # Check if already downloaded
        if output_file.exists():
            print(f"→ Already exists: {uuid}.jpeg")
            return
        
        # Enhanced logging
        print(f"\n{'='*60}")
        print(f"Downloading StepZero Image:")
        print(f"  Extracted UUID: {uuid}")
        print(f"  Saved filename: {uuid}.jpeg")
        print(f"{'='*60}")
        
        # Use wget to download with custom filename
        try:
            result = subprocess.run(
                ['wget', '-O', str(output_file), full_url],
                capture_output=True,
                timeout=60
            )
            
            if result.returncode == 0 and output_file.exists() and output_file.stat().st_size > 0:
                print(f"  ✓ Success: {uuid}.jpeg downloaded successfully")
            else:
                print(f"  ⊘ Failed: Could not download {uuid}.jpeg")
                if output_file.exists():
                    output_file.unlink()
        except Exception as e:
            print(f"  ⊘ Failed: Error during download - {str(e)}")
            if output_file.exists():
                output_file.unlink()
        return
    
    # Determine output file
    # Extract event ID (for Swiggy and other media-assets URLs)
    event_id = extract_event_id(line)
    if not event_id:
        print(f"⊘ Skipping (no event ID)")
        return
    extension = extract_extension(line)
    output_file = Path(INPUT_IMAGE_FOLDER) / f"{event_id}{extension}"
    
    # Skip if already exists
    if output_file.exists():
        print(f"→ Already exists: {event_id}")
        return
    
    # Check for Swiggy URL (download ALL)
    swiggy_match = re.search(r'https://media-assets\.swiggy\.com/[^\s]+', line)
    if swiggy_match:
        swiggy_url = swiggy_match.group(0)
        print(f"Downloading from Swiggy: {event_id}")
        
        if download_file(swiggy_url, str(output_file), validate=False):
            print(f"  ✓ Success: {event_id}")
        else:
            print(f"  ✗ Failed: {event_id}")
        return

# Define video processing function at module level
def process_video_line(line):
    line = line.strip()
    if not line:
        return
    # Support display delimiter
    parts = line.split('|||', 1)
    url = parts[0]
    # Determine event ID for naming (same logic as images)
    event_id = extract_event_id(url)
    if not event_id:
        print(f"⊘ Skipping video (no event ID): {url}")
        return
    # Extract extension from URL
    extension = extract_video_extension(url)
    output_file = Path(INPUT_VIDEO_FOLDER) / f"{event_id}{extension}"
    # Skip if already exists
    if output_file.exists():
        print(f"→ Already exists: {event_id}")
        return
    print(f"Downloading Video: {event_id}")
    if download_file(url, str(output_file), validate=False):
        print(f"  ✓ Success: {event_id}")
    else:
        print(f"  ⊘ Failed: {event_id}")

def main():
    parser = argparse.ArgumentParser(description="Download images and videos using predefined logic.")
    parser.add_argument('--image-url', dest='image_urls', action='append', help='Image URL to download (can be provided multiple times)')
    parser.add_argument('--video-url', dest='video_urls', action='append', help='Video URL to download (can be provided multiple times)')
    args = parser.parse_args()

    processed_via_cli = False

    if args.image_urls:
        print("Starting image downloads...")
        for url in args.image_urls:
            process_image_line(url)
        print("Image downloads complete.")
        processed_via_cli = True

    if args.video_urls:
        print("Starting video downloads...")
        for url in args.video_urls:
            process_video_line(url)
        print("Video downloads complete.")
        processed_via_cli = True

    if processed_via_cli:
        print(f"\nDownload complete! Check '{INPUT_IMAGE_FOLDER}' and '{INPUT_VIDEO_FOLDER}' folders.")
        return

    # Load image links from file when no CLI URLs provided
    with open(IMAGE_INPUT_FILE, 'r', encoding='utf-8') as f:
        image_lines = [line for line in f if line.strip()]
    if image_lines:
        print("Starting image downloads...")
        for line in image_lines:
            process_image_line(line)
        print("Image downloads complete.")
    else:
        print("No image links found; skipping to video downloads.")

    # Download videos from file when no CLI URLs provided
    with open(VIDEO_INPUT_FILE, 'r', encoding='utf-8') as f:
        video_lines = [line for line in f if line.strip()]
    if video_lines:
        print("Starting video downloads...")
        for line in video_lines:
            process_video_line(line)
        print("Video downloads complete.")
    else:
        print("No video links found.")

    print(f"\nDownload complete! Check '{INPUT_IMAGE_FOLDER}' and '{INPUT_VIDEO_FOLDER}' folders.")


if __name__ == '__main__':
    main()