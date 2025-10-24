import os
import subprocess
import json
import math
import tempfile
import shutil
import time
import re
import sys
import platform
from typing import List, Tuple, Dict
import signal # Added for SIGINT
from PIL import Image, ImageDraw # Added for mask and border generation
import concurrent.futures
import argparse

def run_ffmpeg(cmd: list, log_success: bool = True):
    """
    Run an FFmpeg command and handle stderr output cleanly.
    Returns (success: bool, stderr_output: str, stdout_output: str).
    
    This function is ideal for simple FFmpeg operations like version checks,
    encoder listings, and test video creation. For complex operations that 
    require progress tracking, use run_ffmpeg_with_progress().
    """
    result = subprocess.run(cmd, capture_output=True, text=True)
    stderr = result.stderr.strip()
    stdout = result.stdout.strip()
    
    if result.returncode != 0:
        print(f"❌ FFmpeg error (code {result.returncode}):")
        print(stderr)
        return False, stderr, stdout
    
    if log_success:
        print("✅ FFmpeg completed successfully.")
        # Optionally log stderr for review (FFmpeg logs progress to stderr even on success)
        # with open("ffmpeg.log", "a") as f:
        #     f.write(f"Command: {' '.join(cmd)}\n")
        #     f.write(f"FFmpeg logs: {stderr}\n\n")
    
    return True, stderr, stdout

def run_ffmpeg_with_progress(cmd: list, filename: str, duration: float, start_time: float):
    """
    Run an FFmpeg command with real-time progress tracking.
    Returns (success: bool, stderr_lines: list).
    
    This function is designed for long-running FFmpeg operations that benefit
    from progress tracking. It properly handles returncode-based success/failure
    determination while providing real-time feedback.
    """
    # Start the process
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        bufsize=1
    )
    
    # Monitor progress from stderr (where ffmpeg outputs stats)
    last_percentage = -1
    stderr_lines = []
    completion_detected = False
    last_update_time = start_time
    
    try:
        while True:
            # Read from stderr where ffmpeg outputs progress
            line = process.stderr.readline()
            if not line:
                if process.poll() is not None:
                    break
                # Check for timeout if no updates for too long after 100%
                if completion_detected and (time.time() - last_update_time) > 30:
                    print(f"\rFinalizing {filename[:30]}... (This may take a moment)")
                    break
                continue
            
            # Store stderr for potential error messages
            stderr_lines.append(line)
            last_update_time = time.time()
            
            # Check for completion indicators
            if any(indicator in line.lower() for indicator in ['video:', 'audio:', 'subtitle:', 'global headers:']):
                # ffmpeg is showing final summary - we're done
                if completion_detected:
                    sys.stdout.write(f"\r{filename[:30]:<30} │ {'█' * 40} │ 100.0% │ Complete!     ")
                    sys.stdout.flush()
                    break
            
            # Look for time= in the output
            if 'time=' in line:
                # Extract time from stats line
                time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2}\.\d{2})', line)
                if time_match and duration > 0:
                    hours = int(time_match.group(1))
                    minutes = int(time_match.group(2))
                    seconds = float(time_match.group(3))
                    current_time = hours * 3600 + minutes * 60 + seconds
                    
                    # Calculate percentage
                    percentage = (current_time / duration) * 100
                    percentage = min(percentage, 100)
                    
                    # Check if we've reached completion
                    if percentage >= 99.5:
                        completion_detected = True
                        # Show 100% completion
                        elapsed = time.time() - start_time
                        display_progress(
                            filename,
                            100.0,
                            elapsed,
                            duration,
                            current_time
                        )
                        # Gracefully signal ffmpeg to finalize early
                        try:
                            process.send_signal(signal.SIGINT)
                        except Exception:
                            pass
                        # Exit the monitoring loop
                        break
                    elif percentage - last_percentage >= 0.1:
                        # Update display for normal progress
                        elapsed = time.time() - start_time
                        display_progress(
                            filename,
                            percentage,
                            elapsed,
                            duration,
                            current_time
                        )
                        last_percentage = percentage
        
        # Wait for process to complete with longer timeout
        try:
            # Increase timeout based on video duration
            timeout_seconds = max(300, duration * 2) if duration > 0 else 300  # Min 5 minutes
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            print(f"\rTimeout waiting for {filename} to finalize after {format_time(timeout_seconds)}. Terminating...")
            process.terminate()
            process.wait()
        
        # Clear the progress line
        sys.stdout.write('\r' + ' ' * 120 + '\r')
        sys.stdout.flush()
        
        # Check returncode for success/failure
        if process.returncode == 0:
            return True, stderr_lines
        else:
            return False, stderr_lines
            
    except KeyboardInterrupt:
        process.terminate()
        print("\n\nProcessing interrupted by user.")
        raise
    except Exception as e:
        print(f"\n❌ Error during processing: {e}")
        return False, stderr_lines

def create_output_directory(path):
    """Creates a directory if it doesn't exist."""
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"Created directory: {path}")

def get_file_size_mb(filepath):
    """Get file size in MB."""
    if not os.path.exists(filepath):
        return 0
    return os.path.getsize(filepath) / (1024 * 1024)

def calculate_target_bitrate(duration, target_size_mb=10, audio_bitrate_kbps=192):
    """
    Calculate the optimal video bitrate to achieve target file size.
    
    Args:
        duration: Video duration in seconds
        target_size_mb: Target file size in MB
        audio_bitrate_kbps: Audio bitrate in kbps
    
    Returns:
        Target video bitrate in kbps
    """
    if duration <= 0:
        return 2000  # Default fallback
    
    # Convert target size to bits
    target_bits = target_size_mb * 8 * 1024 * 1024
    
    # Calculate audio size in bits
    audio_bits = audio_bitrate_kbps * 1000 * duration
    
    # Calculate available bits for video
    video_bits = target_bits - audio_bits
    
    # Apply safety margin to ensure we stay under limit
    safety_margin = 0.90  # Use 90% of calculated bitrate for safety
    target_video_bitrate_kbps = (video_bits / duration / 1000) * safety_margin
    
    # Ensure minimum quality threshold
    min_bitrate = 500  # 500 kbps minimum
    max_bitrate = 5000  # 5 Mbps maximum for reasonable quality
    
    return max(min_bitrate, min(max_bitrate, target_video_bitrate_kbps))

def reencode_to_target_size(input_path, output_path, target_size_mb, duration, system_info, output_codec='h264'):
    """
    Re-encode video to meet target file size using two-pass encoding for optimal quality.
    
    Args:
        input_path: Path to input video (oversized)
        output_path: Path for output video
        target_size_mb: Target file size in MB
        duration: Video duration in seconds
        system_info: System capabilities info
        output_codec: Output codec to use
    
    Returns:
        True if successful, False otherwise
    """
    print(f"   📦 Re-encoding to meet {target_size_mb} MB size limit...")
    
    # Calculate target bitrate
    audio_bitrate = 128  # Reduce audio bitrate for size-constrained encoding
    target_video_bitrate = calculate_target_bitrate(duration, target_size_mb, audio_bitrate)
    
    print(f"   🎯 Target video bitrate: {target_video_bitrate:.0f} kbps")
    
    # Use software encoding for size-constrained re-encoding (more predictable)
    # Two-pass encoding provides better quality distribution
    temp_dir = tempfile.mkdtemp()
    log_file = os.path.join(temp_dir, 'ffmpeg2pass')
    
    try:
        # Pass 1: Analysis pass
        cmd_pass1 = [
            'ffmpeg',
            '-i', input_path,
            '-c:v', 'libx264',
            '-b:v', f'{int(target_video_bitrate)}k',
            '-maxrate', f'{int(target_video_bitrate * 1.2)}k',
            '-bufsize', f'{int(target_video_bitrate * 2)}k',
            '-preset', 'slow',  # Slower preset for better quality
            '-pass', '1',
            '-passlogfile', log_file,
            '-an',  # No audio in pass 1
            '-f', 'null',
            '-y',
            '/dev/null' if platform.system() != 'Windows' else 'NUL'
        ]
        
        print(f"   🔄 Pass 1/2: Analyzing video...")
        success, _, _ = run_ffmpeg(cmd_pass1, log_success=False)
        
        if not success:
            print("   ❌ Pass 1 failed")
            return False
        
        # Pass 2: Encoding pass
        cmd_pass2 = [
            'ffmpeg',
            '-i', input_path,
            '-c:v', 'libx264',
            '-b:v', f'{int(target_video_bitrate)}k',
            '-maxrate', f'{int(target_video_bitrate * 1.2)}k',
            '-bufsize', f'{int(target_video_bitrate * 2)}k',
            '-preset', 'slow',
            '-pass', '2',
            '-passlogfile', log_file,
            '-c:a', 'aac',
            '-b:a', f'{audio_bitrate}k',
            '-movflags', '+faststart',
            '-y',
            output_path
        ]
        
        print(f"   🔄 Pass 2/2: Encoding with optimal settings...")
        start_time = time.time()
        success, stderr_lines = run_ffmpeg_with_progress(cmd_pass2, os.path.basename(output_path), duration, start_time)
        
        if not success:
            print("   ❌ Pass 2 failed")
            return False
        
        # Verify final size
        final_size = get_file_size_mb(output_path)
        print(f"   ✅ Re-encoded successfully: {final_size:.2f} MB")
        
        return True
        
    finally:
        # Clean up pass log files
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass

def enforce_size_limit(output_path, target_size_mb, duration, system_info, output_codec='h264'):
    """
    Check output file size and re-encode if it exceeds the limit.
    
    Args:
        output_path: Path to the output video
        target_size_mb: Maximum allowed file size in MB
        duration: Video duration in seconds
        system_info: System capabilities info
        output_codec: Output codec used
    
    Returns:
        True if file is within limit (or successfully re-encoded), False otherwise
    """
    if not os.path.exists(output_path):
        print(f"   ❌ Output file not found: {output_path}")
        return False
    
    file_size = get_file_size_mb(output_path)
    print(f"   📊 Output file size: {file_size:.2f} MB")
    
    if file_size <= target_size_mb:
        print(f"   ✅ File size within {target_size_mb} MB limit")
        return True
    
    print(f"   ⚠️  File exceeds {target_size_mb} MB limit by {file_size - target_size_mb:.2f} MB")
    
    # Create temporary copy of oversized file
    temp_input = output_path + '.oversized.tmp'
    shutil.copy2(output_path, temp_input)
    
    try:
        # Re-encode to target size
        success = reencode_to_target_size(
            temp_input, 
            output_path, 
            target_size_mb, 
            duration, 
            system_info, 
            output_codec
        )
        
        if success:
            # Verify final size
            final_size = get_file_size_mb(output_path)
            if final_size <= target_size_mb:
                print(f"   ✅ Successfully reduced from {file_size:.2f} MB to {final_size:.2f} MB")
                return True
            else:
                print(f"   ⚠️  Size still exceeds limit: {final_size:.2f} MB")
                # Try one more time with even lower bitrate
                target_video_bitrate = calculate_target_bitrate(duration, target_size_mb * 0.95, 128)
                print(f"   🔄 Attempting aggressive re-encode with {target_video_bitrate:.0f} kbps...")
                success = reencode_to_target_size(
                    temp_input, 
                    output_path, 
                    target_size_mb * 0.95,  # Target 95% of limit for safety
                    duration, 
                    system_info, 
                    output_codec
                )
                final_size = get_file_size_mb(output_path)
                print(f"   📊 Final size after aggressive re-encode: {final_size:.2f} MB")
                return final_size <= target_size_mb
        
        return False
        
    finally:
        # Clean up temporary file
        try:
            if os.path.exists(temp_input):
                os.remove(temp_input)
        except Exception:
            pass

def get_video_info(video_path):
    """Get video information using ffprobe."""
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,codec_name,duration,r_frame_rate',
        '-of', 'json',
        video_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        stream = info['streams'][0]
        
        # Parse frame rate
        fps_parts = stream['r_frame_rate'].split('/')
        fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else float(fps_parts[0])
        
        return {
            'width': int(stream['width']),
            'height': int(stream['height']),
            'codec': stream['codec_name'],
            'duration': float(stream.get('duration', 0)),
            'fps': fps
        }
    except subprocess.CalledProcessError as e:
        print(f"Error getting video info: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None

def detect_system() -> Dict[str, any]:
    """Detect system information and capabilities."""
    system_info = {
        'platform': platform.system(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'is_macos': platform.system() == 'Darwin',
        'is_apple_silicon': False,
        'has_videotoolbox': False,
        'available_hw_encoders': []
    }
    
    # Check if running on Apple Silicon
    if system_info['is_macos'] and system_info['machine'] == 'arm64':
        system_info['is_apple_silicon'] = True
    
    return system_info

def check_hardware_encoders(system_info: Dict[str, any]) -> Dict[str, any]:
    """Check available hardware encoders."""
    if not system_info['is_macos']:
        return system_info
    
    # Check for VideoToolbox encoders using run_ffmpeg
    success, stderr_output, stdout_output = run_ffmpeg(['ffmpeg', '-encoders'], log_success=False)
    
    if success:
        hw_encoders = []
        if 'h264_videotoolbox' in stdout_output:
            hw_encoders.append('h264_videotoolbox')
        if 'hevc_videotoolbox' in stdout_output:
            hw_encoders.append('hevc_videotoolbox')
        if 'prores_videotoolbox' in stdout_output:
            hw_encoders.append('prores_videotoolbox')
        
        system_info['available_hw_encoders'] = hw_encoders
        system_info['has_videotoolbox'] = len(hw_encoders) > 0
        
        if system_info['has_videotoolbox']:
            print(f"✅ Hardware acceleration available: {', '.join(hw_encoders)}")
    
    return system_info

def check_ffmpeg_installed():
    """Check if ffmpeg and ffprobe are installed."""
    # Check ffmpeg
    success, stderr_output, stdout_output = run_ffmpeg(['ffmpeg', '-version'], log_success=False)
    if not success:
        print("Error: ffmpeg must be installed to use this script.")
        print("Install with: brew install ffmpeg (on macOS)")
        return False

    ffmpeg_version = stdout_output.split('\n')[0] if stdout_output else "Unknown version"
    print(f"Found: {ffmpeg_version}")

    # Check ffprobe
    try:
        subprocess.run(['ffprobe', '-version'], capture_output=True, text=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: ffprobe must be installed to use this script.")
        print("Install with: brew install ffmpeg (on macOS)")
        return False

def format_time(seconds):
    """Format seconds into a readable time string."""
    if seconds < 0:
        return "calculating..."
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"

def parse_progress(line, total_duration):
    """Parse ffmpeg progress output and return progress info."""
    # When using -progress pipe:1, ffmpeg outputs key=value pairs
    # We need to look for lines that start with "out_time_ms="
    if line.startswith('out_time_ms='):
        try:
            # Extract microseconds and convert to seconds
            time_ms = int(line.split('=')[1])
            current_time = time_ms / 1000000.0  # Convert microseconds to seconds
            
            if total_duration > 0:
                # Calculate percentage
                percentage = (current_time / total_duration) * 100
                percentage = min(percentage, 100)  # Cap at 100%
                
                return {
                    'current_time': current_time,
                    'percentage': percentage,
                    'total_duration': total_duration
                }
        except (ValueError, IndexError):
            pass
    
    # Also try the standard time format as fallback
    time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})', line)
    if time_match and total_duration > 0:
        hours = int(time_match.group(1))
        minutes = int(time_match.group(2))
        seconds = int(time_match.group(3))
        current_time = hours * 3600 + minutes * 60 + seconds
        
        # Calculate percentage
        percentage = (current_time / total_duration) * 100
        percentage = min(percentage, 100)  # Cap at 100%
        
        return {
            'current_time': current_time,
            'percentage': percentage,
            'total_duration': total_duration
        }
    return None

def display_progress(filename, percentage, elapsed_time, total_duration, current_time):
    """Display progress bar with time information."""
    # Calculate ETA
    if percentage > 0:
        total_estimated_time = elapsed_time / (percentage / 100)
        eta = total_estimated_time - elapsed_time
    else:
        eta = -1
    
    # Create progress bar
    bar_length = 40
    filled_length = int(bar_length * percentage // 100)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    
    # Format the progress line
    progress_line = (
        f"\r{filename[:30]:<30} │ {bar} │ "
        f"{percentage:5.1f}% │ "
        f"{format_time(current_time)}/{format_time(total_duration)} │ "
        f"ETA: {format_time(eta)}"
    )
    
    # Print without newline
    sys.stdout.write(progress_line)
    sys.stdout.flush()

def get_video_files(folder: str) -> List[Tuple[str, str]]:
    """Get all video files in a folder with their full paths."""
    allowed_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v', '.mpg', '.mpeg')
    video_files = []
    
    if os.path.exists(folder):
        for filename in sorted(os.listdir(folder)):
            if filename.lower().endswith(allowed_extensions):
                full_path = os.path.join(folder, filename)
                video_files.append((filename, full_path))
    
    return video_files

def display_video_menu(video_files: List[Tuple[str, str]]) -> List[int]:
    """Display interactive menu for video selection and return selected indices."""
    print("\n" + "="*60)
    print("VIDEO SELECTION MENU")
    print("="*60)
    
    if not video_files:
        print("\nNo video files found in the input folder.")
        print("Would you like to create sample videos for testing?")
        choice = input("\nEnter 'y' to create sample videos, or any other key to exit: ").strip().lower()
        if choice == 'y':
            return []  # Empty list signals to create sample videos
        else:
            return None  # None signals to exit
    
    print("\nAvailable videos:")
    print("-"*60)
    
    # Display videos with numbers
    for i, (filename, _) in enumerate(video_files, 1):
        # Get video info for display
        video_info = get_video_info(video_files[i-1][1])
        if video_info:
            duration = f"{video_info['duration']:.1f}s" if video_info['duration'] > 0 else "N/A"
            resolution = f"{video_info['width']}x{video_info['height']}"
            print(f"{i:3d}. {filename:<40} [{resolution}, {duration}]")
        else:
            print(f"{i:3d}. {filename}")
    
    print("\n" + "-"*60)
    print("\nOptions:")
    print("  - Enter numbers separated by spaces to select videos (e.g., '1 3 5')")
    print("  - Enter 'all' to select all videos")
    print("  - Enter 'sample' to create and process sample videos")
    print("  - Press Enter without typing to exit")
    print("-"*60)
    
    selection = input("\nYour selection: ").strip().lower()
    
    if not selection:
        return None  # Exit
    elif selection == 'sample':
        return []  # Create sample videos
    elif selection == 'all':
        return list(range(len(video_files)))
    else:
        # Parse individual selections
        selected_indices = []
        try:
            for num in selection.split():
                index = int(num) - 1
                if 0 <= index < len(video_files):
                    if index not in selected_indices:
                        selected_indices.append(index)
                else:
                    print(f"Warning: Ignoring invalid selection '{num}' (out of range)")
            
            if not selected_indices:
                print("\nNo valid videos selected.")
                return None
                
            return selected_indices
            
        except ValueError:
            print("\nError: Invalid input. Please enter numbers only.")
            return None

def confirm_selection(video_files: List[Tuple[str, str]], selected_indices: List[int]) -> bool:
    """Confirm the selected videos before processing."""
    print("\n" + "="*60)
    print("CONFIRMATION")
    print("="*60)
    print(f"\nYou have selected {len(selected_indices)} video(s) for processing:")
    print("-"*60)
    
    for i, index in enumerate(selected_indices, 1):
        filename = video_files[index][0]
        print(f"  {i}. {filename}")
    
    print("-"*60)
    confirmation = input("\nProceed with processing? (y/n): ").strip().lower()
    return confirmation == 'y'

def get_optimal_codec_settings(system_info: Dict[str, any], output_codec: str, video_info: dict = None) -> List[str]:
    """Get optimal codec settings based on system capabilities and output format."""
    codec_settings = []
    
    # Determine the actual encoder to use
    if system_info['is_apple_silicon'] and system_info['has_videotoolbox']:
        if output_codec == 'h264' and 'h264_videotoolbox' in system_info['available_hw_encoders']:
            codec_settings.extend(['-c:v', 'h264_videotoolbox'])
            # VideoToolbox specific settings
            # Use more conservative bitrate settings for stability
            codec_settings.extend([
                '-b:v', '3M',          # Target bitrate 3 Mbps (reduced for stability)
                '-profile:v', 'main',  # Main profile for better compatibility
                '-allow_sw', '1'       # Allow software fallback
            ])
            print("🚀 Using hardware acceleration: h264_videotoolbox")
        elif output_codec == 'h265' and 'hevc_videotoolbox' in system_info['available_hw_encoders']:
            codec_settings.extend(['-c:v', 'hevc_videotoolbox'])
            codec_settings.extend([
                '-b:v', '3M',          # HEVC is more efficient, lower bitrate
                '-maxrate', '4M',
                '-bufsize', '6M',
                '-profile:v', 'main',
                '-tag:v', 'hvc1',      # Better compatibility
                '-allow_sw', '1'
            ])
            print("🚀 Using hardware acceleration: hevc_videotoolbox")
        elif output_codec == 'prores' and 'prores_videotoolbox' in system_info['available_hw_encoders']:
            codec_settings.extend(['-c:v', 'prores_videotoolbox'])
            codec_settings.extend([
                '-profile:v', '2',     # ProRes 422 HQ
                '-vendor', 'apl0'      # Apple vendor ID
            ])
            print("🚀 Using hardware acceleration: prores_videotoolbox")
        else:
            # Fallback to software encoding
            codec_settings.extend(['-c:v', f'lib{output_codec}' if output_codec in ['x264', 'x265'] else output_codec])
            codec_settings.extend(['-preset', 'medium', '-crf', '18'])
            print(f"⚠️  Hardware acceleration not available for {output_codec}, using software encoding")
    else:
        # Non-Apple Silicon or VideoToolbox not available
        if output_codec == 'h264':
            codec_settings.extend(['-c:v', 'libx264'])
            codec_settings.extend([
                '-preset', 'medium',
                '-crf', '18',
                '-profile:v', 'high',
                '-level', '4.1'
            ])
        elif output_codec == 'h265':
            codec_settings.extend(['-c:v', 'libx265'])
            codec_settings.extend([
                '-preset', 'medium',
                '-crf', '20',
                '-tag:v', 'hvc1'
            ])
        else:
            codec_settings.extend(['-c:v', output_codec])
            codec_settings.extend(['-preset', 'medium', '-crf', '18'])
        print(f"ℹ️  Using software encoding: {codec_settings[1]}")
    
    # Pixel format is handled in the filter chain (format=yuv420p)
    # No need to specify it again here
    
    # Add format-specific optimizations
    codec_settings.extend(['-movflags', '+faststart'])  # Optimize for streaming
    
    return codec_settings

def process_videos_in_folder(input_folder, output_folder, video_files_to_process=None, 
                           output_codec='h264', output_format='mp4', system_info=None, max_output_size_mb=10):
    """
    Processes videos: crops them to a 3:4 aspect ratio,
    adds a rounded border, and places them on a slightly larger 3:4 black canvas.
    
    Args:
        input_folder: Input folder path
        output_folder: Output folder path
        video_files_to_process: List of (filename, filepath) tuples to process. If None, processes all videos.
        output_codec: Output video codec
        output_format: Output file format
        system_info: System capabilities information
        max_output_size_mb: Maximum output file size in MB (default: 10)
    """
    print(f"\nStarting video processing...")
    print(f"📦 Maximum output size: {max_output_size_mb} MB per video")
    
    # Check if ffmpeg is installed
    if not check_ffmpeg_installed():
        return False
    
    # Get system info if not provided
    if system_info is None:
        system_info = detect_system()
        system_info = check_hardware_encoders(system_info)
    
    # Ensure the output directory exists
    create_output_directory(output_folder)

    # If no specific videos provided, get all videos from folder
    if video_files_to_process is None:
        video_files_to_process = get_video_files(input_folder)
    
    if not video_files_to_process:
        print("No videos to process.")
        return False
    
    processed_count = 0
    failed_count = 0
    total_start_time = time.time()
    
    # Process each video
    for idx, (filename, video_path) in enumerate(video_files_to_process, 1):
        try:
            print(f"\n[{idx}/{len(video_files_to_process)}] Processing '{filename}'...")
            # Prepare output file path
            output_filename = os.path.splitext(filename)[0] + f".{output_format}"
            output_path = os.path.join(output_folder, output_filename)
            
            # Get video information
            video_info = get_video_info(video_path)
            if not video_info:
                print(f"Could not get video info for {filename}")
                failed_count += 1
                continue
            
            original_width = video_info['width']
            original_height = video_info['height']
            fps = video_info['fps']
            duration = video_info.get('duration', 0)
            
            # --- UNIFIED STEP: Calculate crop dimensions for 3:4 aspect ratio ---
            target_ratio = 3 / 4
            video_ratio = original_width / original_height
            
            if abs(video_ratio - target_ratio) < 0.01:
                # Video already has correct aspect ratio
                crop_width = original_width
                crop_height = original_height
                crop_x = 0
                crop_y = 0
                print(f"Video already has 3:4 aspect ratio.")
            elif video_ratio > target_ratio:
                # Video is WIDER than 3:4. Crop the width from the sides to center it.
                print(f"Cropping width of '{filename}' to 3:4 aspect ratio.")
                crop_width = int(original_height * target_ratio)
                crop_height = original_height
                # Center crop horizontally
                crop_x = (original_width - crop_width) // 2
                crop_y = 0
            else:
                # Video is TALLER than 3:4. Crop the height from the bottom.
                print(f"Cropping height of '{filename}' to 3:4 aspect ratio.")
                crop_width = original_width
                crop_height = int(original_width / target_ratio)
                # Top crop (keep top portion)
                crop_x = 0
                crop_y = 0
                
            # Ensure dimensions are even (required for many codecs)
            crop_width = crop_width if crop_width % 2 == 0 else crop_width - 1
            crop_height = crop_height if crop_height % 2 == 0 else crop_height - 1
            
            # --- Step 1: Calculate proportional border and radius ---
            # Calculate proportional radius and border size based on video width
            radius = int(crop_width * (16 / 360))
            border_size = max(1, round(crop_width * (2 / 360)))
                
            # --- Step 2: Calculate the final 3:4 canvas dimensions ---
            # Make the canvas 1.2x the height of the cropped video
            target_height = crop_height * 1.2
            canvas_height = int(round(target_height / 4) * 4)
            canvas_width = (canvas_height // 4) * 3
            
            # Safeguard: if the canvas is too narrow, expand it to fit the content
            content_width = crop_width + border_size * 2
            if canvas_width < content_width:
                canvas_width = content_width
                canvas_height = int(round((canvas_width * 4 / 3) / 4) * 4)
            
            # Ensure canvas dimensions are even
            canvas_width = canvas_width if canvas_width % 2 == 0 else canvas_width - 1
            canvas_height = canvas_height if canvas_height % 2 == 0 else canvas_height - 1
            
            # Calculate position to center horizontally and align to the top
            paste_x = (canvas_width - (crop_width + border_size * 2)) // 2
            paste_y = 0  # Align to the top
                
            # Pre-generate rounded-corner mask and border PNGs to speed up filtering
            # Create a temporary directory for mask/border images
            tmpdir = tempfile.mkdtemp()
            base_name = os.path.splitext(filename)[0]
            mask_path = os.path.join(tmpdir, f"{base_name}_mask.png")
            border_path = os.path.join(tmpdir, f"{base_name}_border.png")
            # Generate mask: solid white rounded rectangle on black background
            mask_img = Image.new('L', (crop_width, crop_height), 0)
            mask_draw = ImageDraw.Draw(mask_img)
            mask_draw.rounded_rectangle((0, 0, crop_width, crop_height), radius=radius, fill=255)
            mask_img.save(mask_path)
            # Generate border: semi-transparent white rounded rectangle
            br_w, br_h = crop_width + border_size*2, crop_height + border_size*2
            border_img = Image.new('RGBA', (br_w, br_h), (128, 128, 128, 255))  # Solid grey border
            border_mask = Image.new('L', (br_w, br_h), 0)
            bdraw = ImageDraw.Draw(border_mask)
            bdraw.rounded_rectangle((0, 0, br_w, br_h), radius=radius+border_size, fill=255)
            border_img.putalpha(border_mask)
            border_img.save(border_path)
            # Build filter using pre-generated mask and border as inputs 1 and 2
            # Build filter chain without explicit frame rate on color source
            filter_str = (
                f"[0:v]crop={crop_width}:{crop_height}:{crop_x}:{crop_y}[cropped];"
                f"[1:v]format=rgba[mask];"
                f"[cropped][mask]alphamerge[rounded];"
                f"[2:v]format=rgba[border];"
                # Center the rounded video inside the border image
                f"[border][rounded]overlay={border_size}:{border_size}[bordered];"
                f"color=c=black:s={canvas_width}x{canvas_height}[bg];"
                f"[bg][bordered]overlay={paste_x}:{paste_y}[final]"
            )
            
            # Check if output dimensions exceed hardware encoder limits
            max_hw_w, max_hw_h = 4096, 2304
            output_exceeds_hw_limits = (canvas_width > max_hw_w or canvas_height > max_hw_h)
            
            # Enforce yuv420p format for compatibility with h264 encoders
            # Convert from rgba (due to alphamerge/overlay) to yuv420p
            use_hw_encoder = (
                system_info.get('is_apple_silicon') and 
                'h264_videotoolbox' in system_info.get('available_hw_encoders', []) and 
                output_codec == 'h264' and
                not output_exceeds_hw_limits
            )
            
            if output_exceeds_hw_limits and system_info.get('is_apple_silicon'):
                print(f"⚠️  Output dimensions {canvas_width}x{canvas_height} exceed hardware encoder limits; using software encoding")
            
            # Always convert to yuv420p for h264 compatibility (works with both HW and SW encoders)
            filter_str = filter_str.replace('[final]', ',format=yuv420p[final]')
            
            # Build the ffmpeg command with optimized settings
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-loop', '1',  # Loop mask image
                '-i', mask_path,
                '-loop', '1',  # Loop border image
                '-i', border_path,
                '-filter_complex', filter_str,
                '-map', '[final]',
                '-map', '0:a?',  # Copy audio from original
            ]
            
            # Explicitly set output duration to match input video duration
            # This prevents over-encoding when using looped image inputs
            if duration > 0:
                cmd.extend(['-t', str(duration)])
            
            # Add optimized codec settings
            # If output exceeds hardware limits, disable hardware encoding
            effective_system_info = system_info.copy()
            if output_exceeds_hw_limits:
                effective_system_info['has_videotoolbox'] = False
            
            codec_settings = get_optimal_codec_settings(effective_system_info, output_codec, video_info)
            cmd.extend(codec_settings)
            
            # Audio settings
            cmd.extend([
                '-c:a', 'aac',         # Use AAC for audio
                '-b:a', '192k',        # Audio bitrate
                '-ar', '48000',        # Sample rate
            ])
            
            # Add stats and output
            cmd.extend([
                '-stats',              # Show progress statistics
                '-y',                  # Overwrite output file
                output_path
            ])
            
            # Execute the command with progress tracking
            print(f"\nApplying effects to '{filename}'...")
            print(f"Input: {original_width}x{original_height} → Output: {canvas_width}x{canvas_height} (3:4 with borders)")
            print(f"Duration: {format_time(duration) if duration > 0 else 'Unknown'}")
            
            # Debug: Print full FFmpeg command (uncomment to see full command)
            # print(f"\n🔍 FFmpeg command:\n{' '.join(cmd)}\n")
            
            print("-" * 120)
            
            # Show initial progress
            sys.stdout.write(f"\r{filename[:30]:<30} │ {'░' * 40} │   0.0% │ Initializing...")
            sys.stdout.flush()
            
            start_time = time.time()
            
            # Use the reusable FFmpeg wrapper with progress tracking
            try:
                success, stderr_lines = run_ffmpeg_with_progress(cmd, filename, duration, start_time)
                
                # Clean up temporary mask/border files
                try:
                    shutil.rmtree(tmpdir)
                except Exception:
                    pass
                
                if success:
                    end_time = time.time()
                    processing_time = end_time - start_time
                    print(f"✅ Successfully processed '{filename}'")
                    print(f"   Processing time: {format_time(processing_time)}")
                    if duration > 0 and processing_time > 0:
                        print(f"   Average speed: {duration/processing_time:.1f}x realtime")
                    
                    # Enforce size limit
                    size_ok = enforce_size_limit(output_path, max_output_size_mb, duration, system_info, output_codec)
                    if size_ok:
                        processed_count += 1
                    else:
                        print(f"   ❌ Failed to meet size requirements")
                        failed_count += 1
                else:
                    # Use stored stderr lines for error output
                    print(f"❌ Error processing {filename}:")
                    # Show last 10 lines of error output
                    error_lines = stderr_lines[-10:] if len(stderr_lines) > 10 else stderr_lines
                    for line in error_lines:
                        if line.strip():
                            print(f"   {line.strip()}")
                    failed_count += 1
                    
            except KeyboardInterrupt:
                print("\n\nProcessing interrupted by user.")
                raise
            except Exception as e:
                print(f"\n❌ Error during processing: {e}")
                failed_count += 1
                    
        except Exception as e:
            print(f"Could not process {filename}. Reason: {e}")
            failed_count += 1
    
    total_end_time = time.time()
    total_processing_time = total_end_time - total_start_time
    
    print("\n" + "="*60)
    print("PROCESSING COMPLETE")
    print("="*60)
    print(f"Total videos processed: {processed_count}")
    if failed_count > 0:
        print(f"Failed to process: {failed_count}")
    print(f"Total processing time: {format_time(total_processing_time)}")
    if processed_count > 0:
        avg_time = total_processing_time / processed_count
        print(f"Average time per video: {format_time(avg_time)}")
    print("="*60)
    
    return processed_count > 0

def create_test_video(output_path, width=600, height=360, duration=5):
    """Create a test video with specific dimensions."""
    cmd = [
        'ffmpeg',
        '-f', 'lavfi',
        '-i', f'color=c=0xB44682:s={width}x{height}:r=30:d={duration}',
        '-f', 'lavfi',
        '-i', f'sine=frequency=1000:duration={duration}',
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '22',
        '-c:a', 'aac',
        '-y',
        output_path
    ]
    
    # Use the reusable FFmpeg wrapper
    success, _, _ = run_ffmpeg(cmd, log_success=False)
    return success

def create_sample_videos(input_folder):
    """Create sample videos for testing."""
    print("\nCreating sample videos for testing...")
    test_videos = [
        ('wide_test_video.mp4', 800, 400),  # Wider than 3:4
        ('tall_test_video.mp4', 400, 800),  # Taller than 3:4
        ('square_test_video.mp4', 600, 600),  # Square
    ]
    
    created_videos = []
    for filename, width, height in test_videos:
        video_path = os.path.join(input_folder, filename)
        if create_test_video(video_path, width, height):
            print(f"Created test video: {filename} ({width}x{height})")
            created_videos.append((filename, video_path))
        else:
            print(f"Failed to create test video: {filename}")
    
    return created_videos

def process_single_video(filename: str, video_path: str, output_folder: str, output_codec: str, output_format: str, system_info: Dict[str, any], max_output_size_mb: int = 10) -> bool:
    """
    Process a single video file with existing logic by calling process_videos_in_folder on one video.
    Returns True if processing succeeds, False otherwise.
    """
    return process_videos_in_folder(
        os.path.dirname(video_path),
        output_folder,
        [(filename, video_path)],
        output_codec,
        output_format,
        system_info,
        max_output_size_mb
    )

def process_videos_in_bulk(input_folder: str, output_folder: str, jobs: int = None, max_output_size_mb: int = 10):
    """
    Processes all videos in input_folder in parallel and saves to output_folder.
    
    Args:
        input_folder: Input folder path
        output_folder: Output folder path
        jobs: Number of parallel jobs (defaults to CPU count)
        max_output_size_mb: Maximum output file size in MB (default: 10)
    """
    video_files = get_video_files(input_folder)
    if not video_files:
        print(f"No videos found in {input_folder}.")
        return False
    
    # Prepare output directory
    create_output_directory(output_folder)
    
    # Detect system capabilities once
    system_info = detect_system()
    system_info = check_hardware_encoders(system_info)
    
    # Determine parallelism
    max_workers = jobs or os.cpu_count() or 1
    print(f"Processing {len(video_files)} videos with {max_workers} workers...")
    print(f"Maximum output size: {max_output_size_mb} MB per video")
    
    results = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                process_single_video,
                filename,
                path,
                output_folder,
                OUTPUT_CODEC,
                OUTPUT_FORMAT,
                system_info,
                max_output_size_mb
            ): filename for filename, path in video_files
        }
        for future in concurrent.futures.as_completed(futures):
            fname = futures[future]
            try:
                success = future.result()
                status = '✅' if success else '❌'
            except Exception as e:
                status = '❌'
                print(f"Error in {fname}: {e}")
            print(f"{status} {fname}")
            results.append(status == '✅')
    
    succeeded = sum(results)
    failed = len(results) - succeeded
    print(f"Bulk processing complete: {succeeded} succeeded, {failed} failed.")
    return succeeded > 0

if __name__ == "__main__":
    # --- Configuration ---
    # Set the folder where your original videos are located
    INPUT_FOLDER = "/Users/piyush.s_int/Documents/CEO's Scenes/image-to-video/input_videos"
    # Set the folder where the processed videos will be saved
    OUTPUT_FOLDER = "/Users/piyush.s_int/Documents/CEO's Scenes/image-to-video/output_videos"
    
    # Output codec options: h264, h265, vp9, prores
    OUTPUT_CODEC = 'h264'  # You can change this to your preferred codec
    OUTPUT_FORMAT = 'mp4'  # Output format: mp4, mov, mkv, webm
    
    # Maximum output file size in MB
    MAX_OUTPUT_SIZE_MB = 10  # All output videos will be ≤ 10 MB
    
    # Parse CLI arguments for bulk processing
    parser = argparse.ArgumentParser(description="Video processor with bulk and interactive modes.")
    parser.add_argument('--bulk', action='store_true', help='Process entire input folder in bulk')
    parser.add_argument('--input-folder', '-i', default=INPUT_FOLDER, help='Input folder path')
    parser.add_argument('--output-folder', '-o', default=OUTPUT_FOLDER, help='Output folder path')
    parser.add_argument('--jobs', '-j', type=int, help='Number of parallel jobs')
    parser.add_argument('--list-json', action='store_true', help='List available input videos with metadata as JSON')
    parser.add_argument('--files', help='Comma-separated list of filenames to process non-interactively')
    parser.add_argument('--files-json', help='JSON array of filenames to process non-interactively')
    args = parser.parse_args()

    if args.list_json:
        video_files = get_video_files(args.input_folder)
        video_metadata = []
        for filename, path in video_files:
            info = get_video_info(path)
            video_metadata.append({
                'filename': filename,
                'path': path,
                'info': info or {}
            })
        print(json.dumps(video_metadata))
        exit(0)

    if args.files or args.files_json:
        if args.files_json:
            try:
                filenames = json.loads(args.files_json)
                if not isinstance(filenames, list):
                    raise ValueError
            except ValueError:
                print("Invalid JSON provided for --files-json. Expected JSON array of filenames.")
                exit(1)
        else:
            filenames = [name.strip() for name in args.files.split(',') if name.strip()]

        if not filenames:
            print("No filenames provided to --files/--files-json")
            exit(1)

        video_files = get_video_files(args.input_folder)
        lookup = {fname: path for fname, path in video_files}
        missing = [fname for fname in filenames if fname not in lookup]
        if missing:
            print("The following files were not found in the input folder:")
            for fname in missing:
                print(f"  - {fname}")
            exit(1)

        selected_videos = [(fname, lookup[fname]) for fname in filenames]

        system_info = detect_system()
        system_info = check_hardware_encoders(system_info)

        success = process_videos_in_folder(
            args.input_folder,
            args.output_folder,
            selected_videos,
            OUTPUT_CODEC,
            OUTPUT_FORMAT,
            system_info,
            MAX_OUTPUT_SIZE_MB
        )
        exit(0 if success else 1)

    if args.bulk:
        process_videos_in_bulk(args.input_folder, args.output_folder, args.jobs, MAX_OUTPUT_SIZE_MB)
        exit(0)

    # --- Continue existing interactive logic ---
    # Detect system capabilities
    system_info = detect_system()
    
    print("="*60)
    print("VIDEO PROCESSOR WITH ROUNDED CORNERS")
    if system_info['is_apple_silicon']:
        print("🍎 Apple Silicon Optimized")
    print("="*60)
    print(f"System:        {system_info['platform']} {system_info['machine']}")
    print(f"Input folder:  {args.input_folder}")
    print(f"Output folder: {args.output_folder}")
    print(f"Output codec:  {OUTPUT_CODEC}")
    print(f"Output format: {OUTPUT_FORMAT}")
    print("="*60)
    
    # Check if ffmpeg is installed
    if not check_ffmpeg_installed():
        exit(1)
    
    # Check hardware encoders
    system_info = check_hardware_encoders(system_info)
    
    # Create input folder if it doesn't exist
    if not os.path.exists(args.input_folder):
        print(f"\nInput folder '{args.input_folder}' not found. Creating it...")
        os.makedirs(args.input_folder)
    
    # Get all video files
    video_files = get_video_files(args.input_folder)
    
    # Display interactive menu
    selected_indices = display_video_menu(video_files)
    
    if selected_indices is None:
        print("\nExiting without processing any videos.")
        exit(0)
    
    # Handle different selection cases
    if selected_indices == []:  # Create sample videos
        created_videos = create_sample_videos(args.input_folder)
        if created_videos:
            print("\nWould you like to process the created sample videos?")
            choice = input("Enter 'y' to process, or any other key to exit: ").strip().lower()
            if choice == 'y':
                process_videos_in_folder(args.input_folder, args.output_folder, created_videos, 
                                       OUTPUT_CODEC, OUTPUT_FORMAT, system_info, MAX_OUTPUT_SIZE_MB)
            else:
                print("\nSample videos created. You can run the script again to process them.")
        else:
            print("\nFailed to create sample videos.")
    else:
        # Process selected videos
        selected_videos = [(video_files[i][0], video_files[i][1]) for i in selected_indices]
        
        # Confirm selection
        if confirm_selection(video_files, selected_indices):
            process_videos_in_folder(args.input_folder, args.output_folder, selected_videos, 
                                   OUTPUT_CODEC, OUTPUT_FORMAT, system_info, MAX_OUTPUT_SIZE_MB)
        else:
            print("\nCancelled. No videos were processed.")