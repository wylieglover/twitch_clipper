import json
import subprocess

def get_video_duration(video_path: str) -> float:
    """
    Get video length in seconds using ffprobe.
    Returns the duration as a float.
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        video_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    
    return float(data['format']['duration'])

def get_video_dimensions(video_path: str) -> tuple[int, int]:
    """
    Get video dimensions using ffprobe.
    Returns (width, height) tuple.
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        video_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    
    # Find the video stream
    for stream in data['streams']:
        if stream['codec_type'] == 'video':
            return int(stream['width']), int(stream['height'])
    
    raise ValueError(f"No video stream found in {video_path}")

def calculate_target_dimensions(source_width: int, source_height: int, target_width: int = 1080, target_height: int = 1920) -> dict:
    """
    Calculate optimal scaling for vertical video conversion.
    Returns scaling info for background and foreground.
    """
    source_aspect = source_width / source_height
    target_aspect = target_width / target_height
    
    # For foreground (main video), scale to fit width while maintaining aspect ratio
    fg_width = target_width
    fg_height = int(target_width / source_aspect)
    
    # If the scaled height exceeds target, scale by height instead
    if fg_height > target_height:
        fg_height = target_height
        fg_width = int(target_height * source_aspect)
    
    return {
        'target_width': target_width,
        'target_height': target_height,
        'fg_width': fg_width,
        'fg_height': fg_height,
        'source_aspect': source_aspect
    }