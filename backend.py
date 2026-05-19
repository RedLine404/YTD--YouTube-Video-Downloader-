import os
import time
import requests
from pytubefix import YouTube

class DownloaderBackend:
    @staticmethod
    def is_valid_url(url: str) -> bool:
        try:
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    @staticmethod
    def get_video_info(url: str) -> dict:
        yt = YouTube(url)
        streams = yt.streams.filter(type="video")
        
        resolutions = list(set(s.resolution for s in streams if s.resolution))
        resolutions.sort(key=lambda x: int(x.replace("p", "")), reverse=True)
        
        return {
            "title": yt.title,
            "thumbnail": yt.thumbnail_url,
            "resolutions": resolutions
        }

    @staticmethod
    def download_video(url: str, resolution: str, progress_callback, cancel_event, output_path: str = "Downloaded videos YTD") -> str:
        # Create the target directory if it does not exist
        if not os.path.exists(output_path):
            os.makedirs(output_path)

        state = {"start_time": time.time()}

        def on_progress(stream, chunk, bytes_remaining):
            if cancel_event.is_set():
                raise Exception("DOWNLOAD_CANCELLED")
            
            total_size = stream.filesize
            bytes_downloaded = total_size - bytes_remaining
            
            elapsed_time = time.time() - state["start_time"]
            speed_bps = bytes_downloaded / elapsed_time if elapsed_time > 0 else 0
            eta_seconds = bytes_remaining / speed_bps if speed_bps > 0 else 0
            
            progress_callback(bytes_downloaded, total_size, speed_bps, eta_seconds)

        yt = YouTube(url, on_progress_callback=on_progress)
        
        stream = yt.streams.filter(res=resolution, type="video").first()
        if not stream:
            stream = yt.streams.get_highest_resolution()
            
        try:
            # Download and return the absolute path for the UI
            file_path = stream.download(output_path=output_path)
            return os.path.abspath(file_path)
        except Exception as e:
            if str(e) == "DOWNLOAD_CANCELLED":
                partial_file = os.path.join(output_path, stream.default_filename)
                if os.path.exists(partial_file):
                    os.remove(partial_file)
            raise e