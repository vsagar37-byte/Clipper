"""Bounded public YouTube import. No cookies, proxy rotation or login bypass."""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def download_youtube(video_id, folder, max_bytes, max_duration, timeout=900):
    output = Path(folder)
    command = [sys.executable, '-m', 'yt_dlp', '--ignore-config', '--no-playlist',
               '--no-progress', '--no-warnings', '--socket-timeout', '20',
               '--retries', '1', '--fragment-retries', '1', '--no-cache-dir',
               '--js-runtimes', 'node', '--max-filesize', str(max_bytes),
               '--match-filters', f'duration <= {max_duration} & !is_live',
               '--write-info-json', '--no-write-playlist-metafiles',
               '-f', 'bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]',
               '--merge-output-format', 'mp4', '-o', str(output / 'source.%(ext)s'),
               '--', f'https://www.youtube.com/watch?v={video_id}']
    # Kill the entire group on timeout, including any FFmpeg merger child.
    with (output / 'download.log').open('wb') as log:
        process = subprocess.Popen(command, stdout=log, stderr=log, start_new_session=os.name != 'nt')
        deadline = time.monotonic() + timeout
        try:
            while process.poll() is None:
                if time.monotonic() > deadline:
                    raise ValueError('YouTube import timed out. Try again later or upload the video file.')
                # During merging, both inputs and the final output may coexist.
                size = sum(p.stat().st_size for p in output.iterdir() if p.is_file())
                if size > max_bytes * 2 + 10 * 1024 * 1024:
                    raise ValueError('Video exceeds the import size limit. Upload a smaller file.')
                time.sleep(0.5)
            if process.returncode:
                raise ValueError('YouTube could not provide this video. It may be unavailable, restricted, or blocking this server. Try later or upload the original file.')
        finally:
            if process.poll() is None:
                if os.name == 'nt':
                    process.kill()
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()
    path = output / 'source.mp4'
    if not path.is_file() or path.stat().st_size > max_bytes:
        raise ValueError('Video unavailable or exceeds the configured size/duration limit.')
    info_path = output / 'source.info.json'
    info = json.loads(info_path.read_text()) if info_path.is_file() else {}
    # Keep only the title and ID; discard temporary signed media URLs and logs.
    for p in output.iterdir():
        if p != path and p.is_file():
            p.unlink()
    return {'title': str(info.get('title') or 'YouTube video')[:300], 'youtube_video_id': video_id}
