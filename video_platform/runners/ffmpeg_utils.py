import json
import subprocess
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def get_video_info(video_path: str) -> dict:
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,duration,nb_frames",
        "-of", "json", video_path
    ]
    result = subprocess.run(cmd, capture_update=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFprobe failed: {result.stderr}")
    
    data = json.loads(result.stdout)
    if "streams" not in data or len(data["streams"]) == 0:
        raise ValueError("No video stream found")
        
    stream = data["streams"][0]
    # parse frame rate
    fps_parts = stream.get("r_frame_rate", "30/1").split("/")
    fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else float(fps_parts[0])
    
    return {
        "width": int(stream.get("width", 0)),
        "height": int(stream.get("height", 0)),
        "fps": fps,
        "duration": float(stream.get("duration", 0.0)),
        "nb_frames": int(stream.get("nb_frames", 0))
    }

def extract_frames(video_path: str, output_dir: str, fps: float = None) -> None:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-i", video_path,
        "-qscale:v", "2",
    ]
    if fps:
        cmd.extend(["-r", str(fps)])
    cmd.append(f"{output_dir}/%06d.jpg")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg extract failed: {result.stderr}")
    logger.info(f"Extracted frames from {video_path} to {output_dir}")

def merge_frames(frames_dir: str, output_path: str, fps: float) -> None:
    cmd = [
        "ffmpeg", "-y", "-framerate", str(fps),
        "-i", f"{frames_dir}/%06d.jpg",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg merge failed: {result.stderr}")
    logger.info(f"Merged frames from {frames_dir} to {output_path}")

def apply_color_lut(video_path: str, lut_path: str, output_path: str) -> None:
    # Use FFmpeg to apply 3D LUT
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"lut3d='{lut_path}'",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg color grading failed: {result.stderr}")
    logger.info(f"Applied LUT {lut_path} to {video_path}")
