import subprocess

from app.processing.utils.ffprobe import calculate_target_dimensions, get_video_dimensions

def convert_to_vertical(
    input_path: str,
    output_path: str,
    blur_strength: int = 10,
    target_width: int = 1080,
    target_height: int = 1920
):
    """
    - Reads the source resolution.
    - Computes optimal fg_width/fg_height to fit into 1080×1920.
    - Creates a properly scaled blurred background + centered fg on a 1080×1920 canvas.
    - Strips any rotation metadata for a "true" portrait MP4.
    """
    # 1) Probe source
    src_w, src_h = get_video_dimensions(input_path)
    dims = calculate_target_dimensions(src_w, src_h, target_width, target_height)
    fg_w, fg_h = dims['fg_width'], dims['fg_height']

    # 2) Calculate background scaling to avoid distortion
    src_aspect = src_w / src_h
    target_aspect = target_width / target_height
    
    if src_aspect > target_aspect:
        # Source is wider - scale by height and crop width
        bg_scale_h = target_height
        bg_scale_w = int(target_height * src_aspect)
    else:
        # Source is taller - scale by width and crop height  
        bg_scale_w = target_width
        bg_scale_h = int(target_width / src_aspect)

    fc = (
        f"[0:v]scale={bg_scale_w}:{bg_scale_h},"
        f"crop={target_width}:{target_height},"
        f"boxblur={blur_strength//2}:{blur_strength//2}[bg];"
        f"[0:v]scale={fg_w}:{fg_h}[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-filter_complex", fc,
        "-c:v", "h264_nvenc",
        "-preset", "p7", 
        "-tune", "hq",
        "-rc", "vbr",     # Variable bitrate for better quality
        "-cq", "18",      # Constant quality mode
        "-b:v", "0",      # Let CQ mode handle bitrate
        "-maxrate", "10M", # Cap for extreme scenes
        "-bufsize", "20M",
        "-multipass", "fullres",
        "-spatial_aq", "1",
        "-temporal_aq", "1",
        "-c:a", "copy",
        output_path
    ]

    subprocess.run(cmd, check=True)
