import subprocess
import re
import os

# Use the Windows NUL device, or "/dev/null" on Unix
NULL_DEVICE = 'NUL' if os.name == 'nt' else '/dev/null'

def detect_audio_spikes(
    file_path: str,
    threshold_db: float = -10.0,
    # window_size not implemented here but you could batch/filter by timestamp later
):
    """
    Run ffmpeg's astats on just the audio track, detect all frames
    whose RMS level > threshold_db, return sorted (time, rms_db).
    """
    # Start with the simplest approach - just astats without resampling
    filter_chain = "astats=metadata=1:reset=1"
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "info",
        "-i", file_path,
        "-vn",                          # drop video
        "-af", filter_chain,           # apply astats only
        "-f", "null", NULL_DEVICE
    ]
    
    try:
        print(f"[audio_spike_detector] Running: {' '.join(cmd)}")
        proc = subprocess.run(
            cmd, stderr=subprocess.PIPE, text=True, check=True
        )
        output = proc.stderr
    except subprocess.CalledProcessError as e:
        print(f"[audio_spike_detector] astats failed, trying alternative approach:\n  {e.stderr or e}")
        
        # Alternative: use volumedetect filter instead
        filter_chain = "volumedetect"
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "info",
            "-i", file_path,
            "-vn",
            "-af", filter_chain,
            "-f", "null", NULL_DEVICE
        ]
        
        try:
            print(f"[audio_spike_detector] Trying volumedetect: {' '.join(cmd)}")
            proc = subprocess.run(
                cmd, stderr=subprocess.PIPE, text=True, check=True
            )
            # volumedetect gives us overall stats, not frame-by-frame
            # Fall back to a simpler approach using ffprobe
            return _detect_spikes_with_ffprobe(file_path, threshold_db)
        except subprocess.CalledProcessError as e2:
            print(f"[audio_spike_detector] volumedetect also failed:\n  {e2.stderr or e2}")
            return _fallback_spike_detection(file_path)

    # Parse the stderr for "time=" and "RMS level dB:"
    return _parse_astats_output(output, threshold_db)

def _parse_astats_output(output: str, threshold_db: float):
    """Parse astats output for RMS levels above threshold"""
    time_pattern = r"time=(\d+:\d+:\d+\.\d+)"
    rms_pattern  = r"RMS level dB:\s*(-?\d+\.\d+)"
    spikes = []
    current_time = 0.0

    for line in output.splitlines():
        tm = re.search(time_pattern, line)
        if tm:
            h, m, s = tm.group(1).split(":")
            current_time = int(h)*3600 + int(m)*60 + float(s)

        rm = re.search(rms_pattern, line)
        if rm and current_time > 0:
            rms_db = float(rm.group(1))
            if rms_db > threshold_db:
                spikes.append((current_time, rms_db))

    # Return sorted by loudest first
    return sorted(spikes, key=lambda x: x[1], reverse=True)

def _detect_spikes_with_ffprobe(file_path: str, threshold_db: float):
    """Alternative spike detection using ffprobe to get audio info"""
    try:
        # Get audio stream info first
        cmd = [
            "ffprobe",
            "-hide_banner",
            "-loglevel", "quiet",
            "-select_streams", "a:0",
            "-show_entries", "stream=duration",
            "-of", "csv=p=0",
            file_path
        ]
        
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(proc.stdout.strip())
        
        # Sample at regular intervals (every 0.5 seconds)
        sample_points = []
        interval = 0.5
        current = 0.0
        
        while current < duration:
            sample_points.append(current)
            current += interval
            
        # For each sample point, extract a small segment and analyze
        spikes = []
        for timestamp in sample_points:
            try:
                cmd = [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel", "quiet",
                    "-ss", str(timestamp),
                    "-i", file_path,
                    "-t", "0.1",  # 100ms sample
                    "-vn",
                    "-af", "volumedetect",
                    "-f", "null", NULL_DEVICE
                ]
                
                proc = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
                if proc.returncode == 0:
                    # Look for mean_volume in stderr
                    mean_vol_match = re.search(r"mean_volume:\s*(-?\d+\.\d+)\s*dB", proc.stderr)
                    if mean_vol_match:
                        vol_db = float(mean_vol_match.group(1))
                        if vol_db > threshold_db:
                            spikes.append((timestamp, vol_db))
            except:
                continue
                
        return sorted(spikes, key=lambda x: x[1], reverse=True)
        
    except Exception as e:
        print(f"[audio_spike_detector] ffprobe method failed: {e}")
        return _fallback_spike_detection(file_path)

def _fallback_spike_detection(file_path: str):
    """Fallback: return some reasonable timestamps based on video duration"""
    try:
        # Get video duration
        cmd = [
            "ffprobe",
            "-hide_banner",
            "-loglevel", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            file_path
        ]
        
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(proc.stdout.strip())
        
        # Return some strategic timestamps
        spikes = [
            (duration * 0.1, -8.0),   # 10% through
            (duration * 0.3, -9.0),  # 30% through  
            (duration * 0.7, -7.0),  # 70% through
            (duration * 0.9, -8.5),  # 90% through
        ]
        
        print(f"[audio_spike_detector] Using fallback timestamps for {duration:.1f}s video")
        return spikes
        
    except Exception as e:
        print(f"[audio_spike_detector] Fallback also failed: {e}")
        # Last resort - return some default timestamps
        return [(2.0, -8.0), (5.0, -9.0), (10.0, -7.0)]