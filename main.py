import os
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
import yt_dlp
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent
INDEX_FILE = PROJECT_ROOT / "index.html"


def get_allowed_origins() -> list[str]:
    configured = os.getenv("ALLOWED_ORIGIN", "*")
    origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    if not origins or origins == ["*"]:
        return ["*"]
    return origins


app = FastAPI(title="Social Media Downloader", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.api_route("/download", methods=["GET", "HEAD"])
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

@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return FileResponse(INDEX_FILE)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)