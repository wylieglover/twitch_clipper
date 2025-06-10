import torch
import whisper
from app.processing.subtitles.styling import generate_dynamic_ass_style

import warnings

warnings.filterwarnings(
    "ignore",
    message="Failed to launch Triton kernels.*",
    module="whisper.timing",
)

def whisper_to_ass(video_path: str, ass_path: str, target_width: int = 1080, target_height: int = 1920, 
                   max_words_per_line: int = 3, max_chars_per_line: int = 30) -> str:
    """
    Generate ASS subtitles with word-by-word or small phrase timing for better readability.
    """
   
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[whisper] using device={device}")
    
    model = whisper.load_model("turbo", device=device)
    result = model.transcribe(
        video_path,
        language="en",
        word_timestamps=True,
        condition_on_previous_text=False,
        temperature=0.0,
        initial_prompt="Include proper punctuation and capitalization."
    )
    
    segments = result["segments"]
    transcript = result["text"]
    
    # Generate dynamic style template
    dynamic_style = generate_dynamic_ass_style(target_width, target_height)
    
    def fmt_time(t):
        """Format time for ASS format"""
        h, m = divmod(int(t), 3600)
        m, s = divmod(m, 60)
        cs = int((t % 1) * 100)
        return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"
    
    def create_word_chunks(segments, max_words_per_line, max_chars_per_line):
        """Create smaller subtitle chunks from word-level timestamps"""
        chunks = []
        
        for seg in segments:
            if "words" not in seg or not seg["words"]:
                # Fallback to segment-level timing if word timestamps unavailable
                chunks.append({
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": seg["text"].strip()
                })
                continue
            
            words = seg["words"]
            current_chunk = []
            chunk_start = None
            
            for i, word in enumerate(words):
                word_text = word.get("word", "").strip()
                if not word_text:
                    continue
                    
                if chunk_start is None:
                    chunk_start = word.get("start", seg["start"])
                
                current_chunk.append(word_text)
                
                # Check if we should end this chunk
                should_end_chunk = False
                
                # End on punctuation (period, question mark, exclamation)
                if word_text.endswith(('.', '?', '!')):
                    should_end_chunk = True
                # End if we hit word limit
                elif len(current_chunk) >= max_words_per_line:
                    should_end_chunk = True
                # End if we hit character limit
                elif len(' '.join(current_chunk)) >= max_chars_per_line:
                    should_end_chunk = True
                # End if this is the last word in the segment
                elif i == len(words) - 1:
                    should_end_chunk = True
                
                if should_end_chunk:
                    chunk_end = word.get("end", seg["end"])
                    chunk_text = ' '.join(current_chunk)
                    
                    chunks.append({
                        "start": chunk_start,
                        "end": chunk_end,
                        "text": chunk_text
                    })
                    
                    # Reset for next chunk
                    current_chunk = []
                    chunk_start = None
        
        return chunks
    
    # Create word-level chunks
    subtitle_chunks = create_word_chunks(segments, max_words_per_line, max_chars_per_line)
    
    # Write ASS file
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(dynamic_style.strip() + "\n")
        
        for chunk in subtitle_chunks:
            start_time = fmt_time(chunk["start"])
            end_time = fmt_time(chunk["end"])
            text = chunk["text"].replace("\n", " ")
            
            f.write(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}\n")
    
    return transcript