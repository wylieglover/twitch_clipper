import time
import torch

torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

from pyannote.audio import Pipeline as DiarizationPipeline
import whisperx
import gc
import os
import tempfile
import soundfile as sf
import numpy as np

from app.processing.subtitles.styling import generate_dynamic_ass_style
from app.processing.subtitles.whisper import whisper_to_ass

# Environment variable for Hugging Face token
HF_TOKEN = os.getenv("HF_TOKEN", None)

def whisper_to_ass_dynamic(video_path: str, ass_path: str, target_width: int = 1080, target_height: int = 1920) -> str:
    """
    Enhanced transcription using WhisperX with dynamic ASS template.
    
    Args:
        video_path: Path to input video file
        ass_path: Path to output ASS subtitle file
        target_width: Target video width for subtitle scaling
        target_height: Target video height for subtitle scaling
    
    Returns:
        Full transcript text
    """
    try:
        # Determine device and compute type
        device       = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "default" if device == "cuda" else "int8"
        
        print(f"[whisperx] Using device: {device}")
        print(f"[whisperx] Target resolution: {target_width}x{target_height}")
        
        # Load audio
        audio = whisperx.load_audio(video_path)
        
        # Load model and transcribe - using large-v2 for good balance of speed/quality
        model = whisperx.load_model("large-v2", device, compute_type=compute_type, language="en")
        result = model.transcribe(audio, batch_size=16, language="en")
        
        # Get full transcript
        transcript = " ".join([seg["text"] for seg in result["segments"]])
        
        # Load alignment model for better timing
        try:
            model_a, metadata = whisperx.load_align_model(
                language_code=result["language"], 
                device=device
            )
            result = whisperx.align(
                result["segments"], 
                model_a, 
                metadata, 
                audio, 
                device, 
                return_char_alignments=False
            )
            print("[whisperx] Alignment completed")
        except Exception as e:
            print(f"[whisperx] Alignment failed, using original timing: {e}")
            # Continue with original segments if alignment fails
        
        # Generate dynamic ASS style
        dynamic_style = generate_dynamic_ass_style(target_width, target_height)
        
        # Write ASS file with dynamic template
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(dynamic_style.strip() + "\n")
            
            for seg in result["segments"]:
                start = seg.get("start", 0)
                end = seg.get("end", start + 2)
                text = seg["text"].strip().replace("\n", " ")
                
                if not text:  # Skip empty segments
                    continue
                
                def fmt(t):
                    h, m = divmod(int(t), 3600)
                    m, s = divmod(m, 60)
                    cs = int((t % 1) * 100)
                    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"
                
                f.write(f"Dialogue: 0,{fmt(start)},{fmt(end)},Default,,0,0,0,,{text}\n")
        
        print(f"[whisperx] Dynamic ASS file created: {ass_path}")
        
        # Cleanup GPU memory
        gc.collect()
        if device == "cuda":
            torch.cuda.empty_cache()
        
        return transcript
        
    except Exception as e:
        print(f"[whisperx] Error during transcription: {e}")
        # Fallback to original whisper if WhisperX fails
        print("[whisperx] Falling back to original Whisper...")
        return whisper_to_ass(video_path, ass_path, target_width, target_height)
    

def create_audio_for_diarization(audio_data, sample_rate=16000):
    """
    Create a proper audio file for pyannote diarization.
    Handles various audio formats and ensures compatibility.
    """
    temp_file = None
    try:
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_path = temp_file.name
        temp_file.close()
        
        # Ensure audio is in the right format
        if isinstance(audio_data, np.ndarray):
            # If it's already a numpy array, use it directly
            audio_array = audio_data
        else:
            # Convert to numpy array if needed
            audio_array = np.array(audio_data)
        
        # Ensure audio is 1D (mono)
        if len(audio_array.shape) > 1:
            audio_array = np.mean(audio_array, axis=1)
        
        # Normalize audio to prevent clipping
        if np.max(np.abs(audio_array)) > 0:
            audio_array = audio_array / np.max(np.abs(audio_array)) * 0.95
        
        # Write the audio file
        sf.write(temp_path, audio_array, sample_rate)
        
        return temp_path
        
    except Exception as e:
        print(f"[diarization] Error creating audio file: {e}")
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
            except:
                pass
        return None

def whisper_to_ass_with_speakers_dynamic(video_path: str, ass_path: str, target_width: int = 1080, target_height: int = 1920) -> str:
    """
    Enhanced version with speaker diarization and dynamic resolution support.
    Use this if your clips have multiple speakers.
    """
    temp_audio_path = None
    
    try:
        device       = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "default" if device == "cuda" else "int8"
        
        print(f"[whisperx] Using device: {device} (with speaker diarization)")
        print(f"[whisperx] Target resolution: {target_width}x{target_height}")
        
        # Check for HF token
        if not HF_TOKEN:
            print("[whisperx] Warning: No HF_TOKEN found. Speaker diarization requires Hugging Face authentication.")
            print("[whisperx] Falling back to transcription without speakers...")
            return whisper_to_ass_dynamic(video_path, ass_path, target_width, target_height)
        
        # Load audio and transcribe
        audio = whisperx.load_audio(video_path)
        model = whisperx.load_model("large-v2", device, compute_type=compute_type, language="en")
        print(f"[debug] Loaded model at {time.time()}")
        result = model.transcribe(audio, batch_size=16, language="en")
        print(f"[debug] Transcribed model at {time.time()}")
        # Align
        print(f"[debug] About to load_align_model at {time.time()}")
        try:
            model_a, metadata = whisperx.load_align_model(
                language_code=result["language"], 
                device=device
            )
            print(f"[debug] Loaded align model at {time.time()}")
            result = whisperx.align(
                result["segments"], 
                model_a, 
                metadata, 
                audio, 
                device, 
                return_char_alignments=False
            )
            print("[whisperx] Alignment completed")
        except Exception as e:
            print(f"[whisperx] Alignment failed: {e}")
        
        # Speaker diarization with improved error handling
        try:
            print("[whisperx] Initializing speaker diarization...")
            
            # Initialize diarization pipeline with explicit device setting
            diarize_model = DiarizationPipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=HF_TOKEN,
                device=device
            )
        
            print("[whisperx] Creating audio file for diarization...")
            
            # Create temporary audio file with better error handling
            temp_audio_path = create_audio_for_diarization(audio, sample_rate=16000)
            
            if temp_audio_path and os.path.exists(temp_audio_path):
                print(f"[whisperx] Running diarization on: {temp_audio_path}")
                # Run diarization with error handling
                try:
                    diarize_segments = diarize_model(temp_audio_path)
                    print("[whisperx] Diarization completed, assigning speakers...")
                    
                    # Assign speakers to words
                    result = whisperx.assign_word_speakers(diarize_segments, result)
                    print("[whisperx] Speaker assignment completed")
                    
                except Exception as diarize_error:
                    print(f"[whisperx] Diarization pipeline failed: {diarize_error}")
                    print("[whisperx] Continuing without speaker labels...")
            else:
                print("[whisperx] Failed to create audio file for diarization")
                
        except Exception as e:
            print(f"[whisperx] Speaker diarization setup failed: {e}")
            print("[whisperx] Continuing without speaker labels...")
        
        finally:
            # Clean up temporary file
            if temp_audio_path and os.path.exists(temp_audio_path):
                try:
                    os.unlink(temp_audio_path)
                    print("[whisperx] Cleaned up temporary audio file")
                except Exception as cleanup_error:
                    print(f"[whisperx] Warning: Could not clean up temp file: {cleanup_error}")
        
        # Get transcript
        transcript = " ".join([seg["text"] for seg in result["segments"]])
        
        # Generate dynamic ASS style
        dynamic_style = generate_dynamic_ass_style(target_width, target_height)
        
        # Write ASS with speaker labels and dynamic resolution
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(dynamic_style.strip() + "\n")
            
            for seg in result["segments"]:
                start = seg.get("start", 0)
                end = seg.get("end", start + 2)
                text = seg["text"].strip().replace("\n", " ")
                
                if not text:
                    continue
                
                # Add speaker label if available
                if "speaker" in seg and seg["speaker"]:
                    speaker = seg["speaker"]
                    text = f"[{speaker}] {text}"
                
                def fmt(t):
                    h, m = divmod(int(t), 3600)
                    m, s = divmod(m, 60)
                    cs = int((t % 1) * 100)
                    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"
                
                f.write(f"Dialogue: 0,{fmt(start)},{fmt(end)},Default,,0,0,0,,{text}\n")
        
        print(f"[whisperx] ASS file with speaker diarization created: {ass_path}")
        
        # Cleanup
        gc.collect()
        if device == "cuda":
            torch.cuda.empty_cache()
        
        return transcript
        
    except Exception as e:
        print(f"[whisperx] Error during speaker-aware transcription: {e}")
        print("[whisperx] Falling back to transcription without speakers...")
        
        # Clean up temp file in case of error
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.unlink(temp_audio_path)
            except:
                pass
                
        return whisper_to_ass_dynamic(video_path, ass_path, target_width, target_height)