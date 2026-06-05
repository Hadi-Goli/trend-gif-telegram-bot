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
    font_file = 'Roboto-Bold.ttf'
    if not os.path.exists(font_file):
        logger.warning(f"Font file {font_file} not found. Watermark might fallback to default font.")

    # FFmpeg command to overlay watermark at bottom right
    # -vf "drawtext=fontfile='Roboto-Bold.ttf':text='@trend_gif':fontcolor=white:fontsize=18:x=w-tw-10:y=h-th-10:shadowcolor=black@0.8:shadowx=2:shadowy=2"
    # -c:v libx264 -pix_fmt yuv420p -an -y {output_path}
    
    vf_arg = f"drawtext=fontfile='{font_file}':text='{channel_username}':fontcolor=white:fontsize=18:x=w-tw-10:y=h-th-10:shadowcolor=black@0.8:shadowx=2:shadowy=2"
    
    cmd = [
        'ffmpeg',
        '-i', input_path,
        '-vf', vf_arg,
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
