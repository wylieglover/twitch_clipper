import tempfile
from pathlib import Path
import cv2
from google import genai
from google.genai import types

# Hugging Face multimodal model imports + text-generation pipeline
from app.processing.video.spike import detect_audio_spikes
from app.processing.utils.ffprobe import get_video_duration
from config import settings

client = genai.Client(
    api_key=settings.gemini_api_key,
    http_options=types.HttpOptions(api_version='v1alpha')
)

def extract_best_frame_and_thumbnail(video_path: str, thumbnail_path: str) -> str:
    """
    Extract the most visually interesting frame and save as thumbnail.
    Returns the temp frame path for title generation.
    """
    spikes = detect_audio_spikes(video_path)
    duration = get_video_duration(video_path)
    
    # Get candidate timestamps (same logic as before)
    candidates = []
    for spike_time, _ in spikes[:3]:
        candidates.append(spike_time)
    candidates.extend([duration * 0.25, duration * 0.5, duration * 0.75])
    
    # Find best frame
    best_frame = None
    best_variance = 0
    best_timestamp = duration / 2  # fallback
    
    cap = cv2.VideoCapture(video_path)
    for timestamp in candidates[:5]:
        cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        ret, frame = cap.read()
        if ret:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            variance = cv2.Laplacian(gray, cv2.CV_64F).var()
            if variance > best_variance:
                best_variance = variance
                best_frame = frame
                best_timestamp = timestamp
    
    cap.release()
    
    if best_frame is None:
        raise RuntimeError(f"Could not extract frame from {video_path}")
    
    # Save as thumbnail (high quality)
    cv2.imwrite(thumbnail_path, best_frame)
    
    # Also save temp version for AI processing
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        temp_path = tmp.name
    cv2.imwrite(temp_path, best_frame)
    
    return temp_path
def generate_header_genai(frame_path: str,
                          clip_title: str,
                          channel_name: str,
                          transcript_snippet: str = "") -> str:
    """
    Generate a short viral-style TikTok header using Gemini multimodal input.
    """
    if not settings.gemini_api_key:
        raise ValueError("GOOGLE_API_KEY not set in settings.gemini_api_key")

    with open(frame_path, "rb") as f:
        img_bytes = f.read()
    image_part = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")

    # Build prompt with minimal formatting, optimized for drama or irony
    prompt = (
        "You're a short-form video captioner for viral Twitch clips. "
        "Write a short, punchy TikTok-style hook (4-8 words). "
        "Use a Gen-Z tone—but avoid overused filler slang like “fr fr,” “no cap,” or “legit.” "
        "Keep it fresh, avoid hashtags or quotation marks.\n\n"
        f"Streamer: {channel_name}\n"
        f"Title: {clip_title}\n"
        f"Transcript snippet: {transcript_snippet[:150]}\n\n"
        "Return only the caption."
    )

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[prompt, image_part]
    )

    return response.text.strip().split("\n")[0][:60]


def suggest_header_and_thumbnail(video_path: str, thumbnail_path: str, clip_title: str, channel_name: str, transcript: str = "") -> str:
    """
    Generate both header and thumbnail from the same best frame using cloud APIs
    """
    print(f"[AI] Generating smart header and thumbnail for: {clip_title}")
    
    try:
        temp_frame_path = extract_best_frame_and_thumbnail(video_path, thumbnail_path)
        try:
            header = generate_header_genai(
                temp_frame_path, 
                clip_title, 
                channel_name, 
                transcript[:200]
            )
            print(f"[AI] Generated header: {header}")
            return header
        finally:
            Path(temp_frame_path).unlink(missing_ok=True)
    except Exception as e:
        print(f"[AI] Error generating header: {e}")
        return f"{clip_title[:30]}"