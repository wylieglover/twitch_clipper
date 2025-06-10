import os
import subprocess

def download_clip(clip_meta, output_dir: str, filename: str) -> str:
    """
    Downloads the Twitch clip into output_dir under filename.mp4,
    and returns the full path to the downloaded file.
    """
    
    os.makedirs(output_dir, exist_ok=True)
    clip_url   = clip_meta["url"]
    local_path = os.path.join(output_dir, f"{filename}.mp4")
    print(f"Downloading clip {clip_meta['id']} → {local_path}")
    subprocess.run([
        "streamlink",
        "--force",  
        clip_url,
        "best",
        "-o", local_path
    ], check=True)
    print("Downloaded", local_path)
    return local_path
