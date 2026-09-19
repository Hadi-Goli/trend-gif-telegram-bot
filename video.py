import subprocess
import os
import asyncio
import logging

logger = logging.getLogger(__name__)

async def _execute_ffmpeg(cmd: list) -> tuple[int, str]:
    """Helper to execute an FFmpeg command asynchronously and return (returncode, stderr)."""
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return process.returncode, stderr.decode(errors='ignore')

async def watermark_video(input_path: str, output_path: str, channel_username: str) -> bool:
    """
    Downloads and watermarks a video using FFmpeg.
    Runs asynchronously using asyncio.create_subprocess_exec.
    Includes automatic H.264 bitstream sanitization for videos with invalid/reserved color spaces.
    """
    watermark_file = '001.png'
    if not os.path.exists(watermark_file):
        logger.error(f"Watermark file {watermark_file} not found.")
        # Fallback to simple copy if watermark is missing, or return False
        return False

    # 1. Upscale low-res videos to min width of 640px (bicubic) so watermark has high pixel density
    # 2. Rotate watermark 90 degrees clockwise (transpose=clock) for vertical top-to-bottom reading
    # 3. Scale watermark proportionally (35% of video height, bounded by 45% of width) with lanczos filter
    # 3. Scale watermark proportionally (26% of video height, bounded by 35% of width) with lanczos filter
    # 4. Position watermark at middle right: W-w-10 horizontally, (H-h)/2 vertically
    filter_complex = (
        "[0:v]scale='ceil(if(lt(iw,640),640,iw)/2)*2':-2:flags=bicubic[scaled_vid];"
        "[1:v]transpose=clock[wm_rot];"
        "[wm_rot][scaled_vid]scale2ref=h='min(ih*0.35,iw*0.45)':w='oh*mdar':flags=lanczos[wm][vref];"
        "[wm_rot][scaled_vid]scale2ref=h='min(ih*0.26,iw*0.35)':w='oh*mdar':flags=lanczos[wm][vref];"
        "[vref][wm]overlay=W-w-10:(H-h)/2"
    )
    
    cmd = [
        'ffmpeg',
        '-i', input_path,
        '-i', watermark_file,
        '-filter_complex', filter_complex,
        '-c:v', 'libx264',
        '-crf', '26',
        '-preset', 'fast',
        '-pix_fmt', 'yuv420p',
        '-an', # Remove audio
        '-y',  # Overwrite output
        output_path
    ]
    def build_cmd(src_path: str) -> list[str]:
        return [
            'ffmpeg',
            '-i', src_path,
            '-i', watermark_file,
            '-filter_complex', filter_complex,
            '-c:v', 'libx264',
            '-crf', '26',
            '-preset', 'fast',
            '-pix_fmt', 'yuv420p',
            '-an', # Remove audio
            '-y',  # Overwrite output
            output_path
        ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
        # First attempt with original input
        returncode, stderr = await _execute_ffmpeg(build_cmd(input_path))
        if returncode == 0:
            logger.info("Watermarking successful.")
            return True
        else:
            logger.error(f"FFmpeg failed with return code {process.returncode}")
            logger.error(f"FFmpeg stderr: {stderr.decode()}")
            return False
            

        # If it failed due to "Invalid color space" (FFmpeg 7+ strictness on reserved metadata),
        # sanitize the H.264 bitstream metadata to standard BT.709 and retry.
        if "Invalid color space" in stderr:
            logger.warning("Invalid color space detected in input video. Sanitizing H.264 bitstream...")
            sanitized_path = f"sanitized_{os.path.basename(input_path)}"
            sanitize_cmd = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-bsf:v', 'h264_metadata=colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1',
                '-c', 'copy',
                sanitized_path
            ]
            s_rc, s_err = await _execute_ffmpeg(sanitize_cmd)
            if s_rc == 0 and os.path.exists(sanitized_path):
                try:
                    returncode, stderr = await _execute_ffmpeg(build_cmd(sanitized_path))
                    if returncode == 0:
                        logger.info("Watermarking successful after bitstream sanitization.")
                        return True
                finally:
                    if os.path.exists(sanitized_path):
                        os.remove(sanitized_path)

        logger.error(f"FFmpeg failed with return code {returncode}")
        logger.error(f"FFmpeg stderr: {stderr}")
        return False
        
    except Exception as e:
        logger.error(f"Error executing FFmpeg: {e}")
        return False
