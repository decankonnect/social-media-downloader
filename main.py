import os
import shutil
import tempfile
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.background import BackgroundTask
import yt_dlp
from dotenv import load_dotenv

app = FastAPI()
INDEX_FILE = os.path.join(os.path.dirname(__file__), "index.html")

# Load environment variables from .env file
load_dotenv()

# CORS configuration
app.add_middleware(CORSMiddleware,
    allow_origins=[os.getenv("ALLOWED_ORIGIN")],  # Adjust this to your needs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/download")
def download_video(
    url: str = Query(..., min_length=1),
    format: str = Query("best", min_length=1, max_length=200),
):
    parsed_url = urlparse(url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise HTTPException(status_code=400, detail="Enter a valid http or https video URL.")

    download_dir = tempfile.mkdtemp(prefix="social-video-")
    try:
        ydl_opts = {
            'format': format,
            'outtmpl': os.path.join(download_dir, '%(title).200B.%(ext)s'),
            'quiet': True,
            'noplaylist': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        actual_file_path = info.get("filepath") if info else None
        if not actual_file_path or not os.path.isfile(actual_file_path):
            downloaded_files = [
                os.path.join(download_dir, name)
                for name in os.listdir(download_dir)
                if os.path.isfile(os.path.join(download_dir, name))
                and not name.endswith((".part", ".ytdl", ".description", ".json"))
            ]
            actual_file_path = downloaded_files[0] if downloaded_files else None

        if not actual_file_path:
            raise HTTPException(
                status_code=502,
                detail="The platform did not provide a downloadable video file.",
            )

        return FileResponse(
            actual_file_path,
            filename=os.path.basename(actual_file_path),
            media_type="application/octet-stream",
            background=BackgroundTask(shutil.rmtree, download_dir),
        )
    except HTTPException:
        shutil.rmtree(download_dir)
        raise
    except Exception as e:
        shutil.rmtree(download_dir)
        raise HTTPException(
            status_code=502,
            detail=f"yt-dlp could not download this video: {e}",
        ) from e

@app.get("/")
async def root():
    return FileResponse(INDEX_FILE)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)