import os
import yt_dlp
import sys

def download_audio(url, output_dir="temp"):
    """
    Download audio from YouTube URL and convert to WAV.
    Returns the absolute path to the downloaded .wav file.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Downloading: {url}")
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            # yt-dlp changes extension after post-processing
            base, _ = os.path.splitext(filename)
            wav_path = base + ".wav"
            
            if os.path.exists(wav_path):
                return os.path.abspath(wav_path)
            else:
                # Sometimes filename is different?
                # Re-scan dir for newest wav?
                # Or trust yt-dlp naming convention.
                # yt-dlp replaces spaces with underscores? No, default is title.
                # Let's check if file exists.
                return os.path.abspath(wav_path)
                
    except Exception as e:
        print(f"Error downloading: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) > 1:
        url = sys.argv[1]
        path = download_audio(url)
        print(f"Downloaded to: {path}")
    else:
        print("Usage: python youtube_downloader.py <URL>")
