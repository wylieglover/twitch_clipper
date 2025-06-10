# pipeline.py

import os
from pathlib import Path
import shutil
import subprocess
import time
import threading
from typing import Optional

import requests

from app.session_manager import SessionManager
from app.session import Session    
from app.processing.utils.sanitize import sanitize_filename
from app.processing.video.header import create_text_overlay_image
from app.processing.clips.process_vod import process_vod
from app.processing.clips.fetch import get_twitch_token, get_user_info, get_clips
from app.processing.clips.download import download_clip
from app.processing.video.vertical import convert_to_vertical
from app.processing.subtitles.whisper import whisper_to_ass
from app.processing.video.hooks import suggest_header_and_thumbnail
from app.processing.utils.ffprobe import get_video_dimensions
from config import settings

OUTPUT_DIR = os.path.abspath("output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Thread-safe cache management for trending hashtags
_trending_cache = {"hashtags": [], "timestamp": 0}
_cache_lock = threading.Lock()


def update_session_progress(session_id: str, step: str, progress: int = 0):
    """Update session with current processing step and progress"""
    if SessionManager.session_exists(session_id):
        SessionManager.update_session_progress(session_id, step, progress)
        print(f"[session {session_id}] {step} - {progress}%")

def get_tiktok_hashtags() -> list[str]:
    """Thread-safe fetch of trending TikTok hashtags with caching"""
    global _trending_cache
    
    with _cache_lock:
        # Use cache if less than 1 hour old
        if time.time() - _trending_cache["timestamp"] < 3600 and _trending_cache["hashtags"]:
            return _trending_cache["hashtags"].copy()
    
    try:
        url = "https://tiktok-scraper2.p.rapidapi.com/trending/hashtags"
        headers = {
            "X-RapidAPI-Key": settings.rapid_api_key,
            "X-RapidAPI-Host": "tiktok-scraper2.p.rapidapi.com"
        }
        
        if not headers["X-RapidAPI-Key"]:
            print("[hashtags] No RAPIDAPI_KEY found, using fallback hashtags")
            return ["#fyp", "#viral", "#trending", "#foryou"]
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            hashtags = []
            
            # Handle different response formats
            if isinstance(data, list):
                for item in data[:8]:
                    if isinstance(item, dict) and 'name' in item:
                        hashtags.append(f"#{item['name']}")
                    elif isinstance(item, str):
                        hashtags.append(f"#{item}")
            elif isinstance(data, dict) and 'hashtags' in data:
                for item in data['hashtags'][:8]:
                    if isinstance(item, dict) and 'name' in item:
                        hashtags.append(f"#{item['name']}")
                    elif isinstance(item, str):
                        hashtags.append(f"#{item}")
            
            if hashtags:
                with _cache_lock:
                    _trending_cache = {"hashtags": hashtags, "timestamp": time.time()}
                print(f"[hashtags] Fetched {len(hashtags)} trending hashtags")
                return hashtags
                
    except Exception as e:
        print(f"[hashtags] API error: {e}")
    
    # Fallback hashtags if API fails
    print(f"[hashtags] Using fallback hashtags due to API error or empty response")
    fallback = ["#fyp", "#viral", "#trending", "#foryou", "#gaming", "#funny"]
    with _cache_lock:
        _trending_cache = {"hashtags": fallback, "timestamp": time.time()}
    return fallback

def annotate_header_only(
    video_in: str,
    header_text: str,    
    output_path: str
) -> str:
    """
    Create a temporary PNG containing `header_text` at video dimensions,
    then overlay it onto `video_in`. No subtitles are burned in.
    """
    # 1) figure out input video’s dimensions
    width, height = get_video_dimensions(video_in)

    # 2) render header_text → PNG file
    overlay_image = create_text_overlay_image(header_text, width, height)

    try:
        # 3) overlay that PNG on top of the video
        filter_complex = "[0:v][1:v]overlay=0:0"
        subprocess.run([
            "ffmpeg", "-y",
            "-i", video_in,
            "-i", overlay_image,
            "-filter_complex", filter_complex,
            "-c:v", "h264_nvenc",
            "-preset", "p7",
            "-tune", "hq",
            "-rc", "vbr",
            "-cq", "20",
            "-b:v", "0",
            "-maxrate", "10M",
            "-bufsize", "20M",
            "-multipass", "fullres",
            "-spatial_aq", "1",
            "-temporal_aq", "1",
            "-c:a", "copy",
            output_path
        ], check=True)
    finally:
        # 4) clean up the temp PNG
        if os.path.exists(overlay_image):
            os.unlink(overlay_image)

    return output_path

def annotate_with_subtitles_and_header(
    video_in: str,
    ass_file: str,
    header_text: str,
    output_path: str
) -> str:
    """Single FFmpeg pass with PIL overlay - fastest approach"""
    
    width, height = get_video_dimensions(video_in)
    overlay_image = create_text_overlay_image(header_text, width, height)
    
    try:
        # Escape ASS file path for ffmpeg
        posix = Path(ass_file).as_posix()
        escaped_ass = (
            posix
            .replace(":", r"\:")
            .replace(" ", r"\ ")
            .replace("'", r"\'")
        )
        
        # Single pass: subtitles + image overlay
        filter_complex = f"[0:v]subtitles='{escaped_ass}'[subbed];[subbed][1:v]overlay=0:0"
        
        subprocess.run([
            "ffmpeg", "-y",
            "-i", video_in,
            "-i", overlay_image,
            "-filter_complex", filter_complex,
            "-c:v", "h264_nvenc",
            "-preset", "p7",           
            "-tune", "hq", 
            "-rc", "vbr",
            "-cq", "20",              
            "-b:v", "0",              
            "-maxrate", "10M",        
            "-bufsize", "20M",
            "-multipass", "fullres",
            "-spatial_aq", "1",        # Spatial adaptive quantization
            "-temporal_aq", "1",       # Temporal adaptive quantization
            "-rc-lookahead", "32",     # Look-ahead for better encoding decisions
            "-c:a", "copy",
            str(output_path)
        ], check=True)
    finally:
        # Clean up overlay image
        if os.path.exists(overlay_image):
            os.unlink(overlay_image)
    
    return str(output_path)


def process_from_vod(
    source: str, 
    max_clips: int = 5, 
    segment_duration: int = 30, 
    session: Optional[Session] = None,
    include_subtitles: bool = True
) -> list[dict]:
    """
    Process clips from a VOD URL, writing each intermediate file into the session’s output directory.
    As soon as a single clip’s final video + thumbnail + metadata are ready, we call
    SessionManager.add_result_to_session(session.session_id, clip_dict)
    so that FastAPI’s `partial_results` list grows immediately.
    """
    if session is None:
        session = Session()
    
    print(f"[pipeline] Starting VOD processing for session: {session.session_id}")
    
    try:
        vod_clips = process_vod(source, max_clips=max_clips, segment_duration=segment_duration)
        results = []

        for i, clip_path in enumerate(vod_clips[:max_clips]):
            try:
                base = os.path.splitext(os.path.basename(clip_path))[0]
                base = sanitize_filename(base) or f"vod_clip_{i+1}"
                print(f"[pipeline] Processing VOD clip {i+1}: {base} (session: {session.session_id})")

                raw      = clip_path
                # Build filenames under this session’s output directory
                ass_file = session.get_file_path(f"{base}.ass")
                vertical = session.get_file_path(f"{base}_vertical.mp4")
                final    = session.get_file_path(f"{base}_final.mp4")
                thumb    = session.get_file_path(f"{base}_thumbnail.jpg")

                # 1) Transcribe audio → .ass
                transcript = whisper_to_ass(raw, ass_file)

                # 2) Convert to vertical
                convert_to_vertical(raw, vertical)

                # 3) Generate header and thumbnail (TikTok‐style)
                header = suggest_header_and_thumbnail(
                    video_path=vertical,
                    thumbnail_path=thumb,
                    clip_title=f"VOD Clip {i+1}",
                    channel_name="Stream",
                    transcript=transcript
                )
                    

                # 4) Burn in subtitles + header
                if include_subtitles:
                    final_clip = annotate_with_subtitles_and_header(
                        vertical, ass_file, header, final
                    )
                else:
                    final_clip = annotate_header_only(
                        vertical, header, final
                    )

                # At this point, final_clip and thumb both exist under session.output_dir
                tags = get_tiktok_hashtags()
                clip_dict = {
                    "video": Path(final_clip).name,
                    "thumbnail": Path(thumb).name,
                    "transcript": transcript,
                    "tags": tags,
                    "description": header,
                    "hashtags": tags,
                    "session_id": session.session_id,
                }

                # ▶️  **STREAM THIS CLIP IMMEDIATELY** into FastAPI’s partial_results
                SessionManager.add_result_to_session(session.session_id, clip_dict)

                # Also append to local list, so that at the very end we return the full array
                results.append(clip_dict)

            except Exception as e:
                print(f"[pipeline] Error in VOD clip {i+1}: {e}")
                continue

        print(f"[pipeline] VOD processing completed for session: {session.session_id}")
        return results
        
    except Exception as e:
        print(f"[pipeline] VOD processing failed for session {session.session_id}: {e}")
        raise

def process_from_twitch_clips(
    channel_name: str, 
    time_window: str = "week", 
    max_clips: int = 5, 
    session: Optional[Session] = None,
    include_subtitles: bool = True,
    min_views: int = 100
) -> list[dict]:
    """Process clips with progress updates"""
    if session is None:
        session = Session()
        
    session_id = session.session_id
    print(f"[pipeline] Starting Twitch clips processing for session: {session_id}")
    
    try:
        update_session_progress(session_id, "Fetching Twitch token", 5)
        token = get_twitch_token()
        
        update_session_progress(session_id, "Getting user info", 10)
        user_info = get_user_info(token, channel_name)
        user_id = user_info["id"]
        channel_display_name = user_info["display_name"]
        
        update_session_progress(session_id, "Fetching clips", 15)
        clips = get_clips(user_id, token, time_window, desired_count=max_clips, min_views=min_views)
        results = []

        total_clips = len(clips[:max_clips])
        for i, clip in enumerate(clips[:max_clips]):
            clip_progress_base = 20 + (i * 70 // total_clips)  # 20-90% range
            
            clip_title = clip.get("title", f"Clip {i+1}")
            broadcaster_name = clip.get("broadcaster_name", channel_display_name)
            base = sanitize_filename(clip_title) or f"twitch_clip_{i+1}"
            
            update_session_progress(session_id, f"Processing clip {i+1}/{total_clips}: {clip_title}", clip_progress_base)

            try:
                workdir = session.create_temp_dir(prefix=f"{base}_")
                
                update_session_progress(session_id, f"Downloading clip {i+1}", clip_progress_base + 5)
                raw_path = download_clip(clip, workdir, base)
                
                update_session_progress(session_id, f"Transcribing clip {i+1}", clip_progress_base + 15)
                ass_file = os.path.join(workdir, f"{base}.ass")
                transcript = whisper_to_ass(raw_path, ass_file)
                
                update_session_progress(session_id, f"Converting clip {i+1} to vertical", clip_progress_base + 35)
                vertical = os.path.join(workdir, f"{base}_vertical.mp4")
                convert_to_vertical(raw_path, vertical)
                
                update_session_progress(session_id, f"Generating thumbnail for clip {i+1}", clip_progress_base + 50)
                final_tmp  = os.path.join(workdir, f"{base}_final.mp4")
                thumb_tmp  = os.path.join(workdir, f"{base}_thumbnail.jpg")
                
                header = suggest_header_and_thumbnail(
                    video_path=vertical,
                    thumbnail_path=thumb_tmp,
                    clip_title=clip_title,
                    channel_name=broadcaster_name,
                    transcript=transcript
                )
                
                update_session_progress(session_id, f"Adding subtitles to clip {i+1}", clip_progress_base + 60)
                if include_subtitles:
                    final_clip = annotate_with_subtitles_and_header(
                        vertical, ass_file, header, final_tmp
                    )
                else:
                    final_clip = annotate_header_only(
                        vertical, header, final_tmp
                    )
                
                # Move files and create result
                final_dest = session.get_file_path(os.path.basename(final_clip))
                thumb_dest = session.get_file_path(os.path.basename(thumb_tmp))
                shutil.move(final_clip, final_dest)
                shutil.move(thumb_tmp, thumb_dest)
                
                session.remove_temp_dir(workdir)
                
                tags = get_tiktok_hashtags()
                clip_dict = {
                    "video": os.path.basename(final_dest),
                    "thumbnail": os.path.basename(thumb_dest),
                    "transcript": transcript,
                    "tags": tags,
                    "description": header,
                    "hashtags": tags,
                    "session_id": session.session_id,
                    "view_count": clip.get("view_count", 0),
                }
                
                # Stream result immediately
                SessionManager.add_result_to_session(session.session_id, clip_dict)
                results.append(clip_dict)
                
                update_session_progress(session_id, f"Completed clip {i+1}/{total_clips}", clip_progress_base + 70)
                
            except Exception as e:
                print(f"[pipeline] Error in Twitch clip {i+1}: {e}")
                continue

        update_session_progress(session_id, "Processing completed", 100)
        print(f"[pipeline] Twitch clips processing completed for session: {session_id}")
        return results
        
    except Exception as e:
        update_session_progress(session_id, f"Error: {str(e)}", -1)
        print(f"[pipeline] Twitch clips processing failed for session {session_id}: {e}")
        raise
