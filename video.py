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
    watermark_file = '006.png'
    if not os.path.exists(watermark_file):
        logger.error(f"Watermark file {watermark_file} not found.")
        # Fallback to simple copy if watermark is missing, or return False
        return False

    # FFmpeg command to overlay watermark at bottom right
    # [1:v][0:v]scale2ref=w='iw*0.05':h='ow/mdar'[wm][vid] scales the watermark to 5% of the video width
    # [vid][wm]overlay=W-w-10:H-h-10 overlays it 10px from the bottom right
    filter_complex = "[1:v][0:v]scale2ref=w='iw*0.13':h='ow/mdar'[wm][vid];[vid][wm]overlay=W-w-10:H-h-10"
    
    cmd = [
        'ffmpeg',
        '-i', input_path,
        '-i', watermark_file,
        '-filter_complex', filter_complex,
        '-c:v', 'libx264',
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
