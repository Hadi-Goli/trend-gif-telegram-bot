import subprocess
import os
import asyncio
import logging

logger = logging.getLogger(__name__)

async def watermark_video(input_path: str, output_path: str, channel_username: str) -> bool:
    """
    Downloads and watermarks a video using FFmpeg.
    Runs asynchronously using asyncio.create_subprocess_exec.
    """
    watermark_file = '001.png'
    if not os.path.exists(watermark_file):
        logger.error(f"Watermark file {watermark_file} not found.")
        # Fallback to simple copy if watermark is missing, or return False
        return False

    # 1. Upscale low-res videos to min width of 640px (bicubic) so watermark has high pixel density
    # 2. Rotate watermark 90 degrees clockwise (transpose=clock) for vertical top-to-bottom reading
    # 3. Scale watermark proportionally (35% of video height, bounded by 45% of width) with lanczos filter
    # 4. Position watermark at middle right: W-w-10 horizontally, (H-h)/2 vertically
    filter_complex = (
        "[0:v]scale='ceil(if(lt(iw,640),640,iw)/2)*2':-2:flags=bicubic[scaled_vid];"
        "[1:v]transpose=clock[wm_rot];"
        "[wm_rot][scaled_vid]scale2ref=h='min(ih*0.35,iw*0.45)':w='oh*mdar':flags=lanczos[wm][vref];"
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

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            logger.info("Watermarking successful.")
            return True
        else:
            logger.error(f"FFmpeg failed with return code {process.returncode}")
            logger.error(f"FFmpeg stderr: {stderr.decode()}")
            return False
            
    except Exception as e:
        logger.error(f"Error executing FFmpeg: {e}")
        return False
