import os
import re
import shutil
import tempfile
import zipfile
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


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]", "_", value or "download")
    cleaned = cleaned.strip().strip(".") or "download"
    return cleaned[:180]


def find_downloaded_files(directory: str) -> list[str]:
    files: list[str] = []
    for root, _, names in os.walk(directory):
        for name in names:
            file_path = os.path.join(root, name)
            if os.path.isfile(file_path) and not name.endswith((".part", ".ytdl", ".description", ".json")):
                files.append(file_path)
    return sorted(files)


def build_download_options(download_dir: str, media_type: str, quality: str, include_playlist: bool) -> dict:
    chosen_quality = quality.strip() if quality and quality.strip() else "best"

    if media_type == "audio":
        chosen_format = "bestaudio/best"
        if chosen_quality and chosen_quality.lower() not in {"best", "bestaudio", "bestaudio/best"}:
            chosen_format = chosen_quality
    else:
        normalized = chosen_quality.lower()
        if normalized == "best":
            chosen_format = "bestvideo"
        elif normalized.startswith("bestvideo"):
            chosen_format = chosen_quality
        elif normalized.startswith("best["):
            chosen_format = chosen_quality.replace("best[", "bestvideo[", 1)
            if "/best" in chosen_format:
                chosen_format = chosen_format.split("/best", 1)[0]
        else:
            chosen_format = f"bestvideo[{chosen_quality}]" if not chosen_quality.startswith("bestvideo") else chosen_quality

    options = {
        "format": chosen_format,
        "outtmpl": os.path.join(download_dir, "%(title).200B.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": not include_playlist,
        "extract_flat": False,
    }
    return options


def create_playlist_archive(download_dir: str, files: list[str], title: str) -> str:
    archive_name = f"{sanitize_filename(title) or 'playlist'}-archive.zip"
    archive_path = os.path.join(download_dir, archive_name)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in files:
            archive.write(file_path, arcname=os.path.basename(file_path))
    return archive_path


def fetch_downloaded_file(url: str, media_type: str, quality: str, include_playlist: bool) -> tuple[str, str, str]:
    parsed_url = urlparse(url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise HTTPException(status_code=400, detail="Enter a valid http or https video URL.")

    download_dir = tempfile.mkdtemp(prefix=f"decan-{media_type}-")
    last_error: Exception | None = None

    try:
        attempted_formats = [quality.strip() if quality and quality.strip() else "best"]
        if attempted_formats[0] != "best":
            attempted_formats.append("best")

        for chosen_format in attempted_formats:
            try:
                ydl_opts = build_download_options(download_dir, media_type, chosen_format, include_playlist)
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)

                downloaded_files = find_downloaded_files(download_dir)
                if not downloaded_files:
                    raise HTTPException(
                        status_code=502,
                        detail="The platform did not provide a downloadable file.",
                    )

                if include_playlist and len(downloaded_files) > 1:
                    archive_path = create_playlist_archive(download_dir, downloaded_files, info.get("title") if isinstance(info, dict) else "playlist")
                    return archive_path, os.path.basename(archive_path), "application/zip"

                file_path = downloaded_files[0]
                return file_path, os.path.basename(file_path), "application/octet-stream"
            except Exception as exc:  # broad catch so we can retry with the generic best format on invalid quality filters
                last_error = exc
                if "Requested format is not available" in str(exc) and chosen_format != "best":
                    continue
                raise

        raise HTTPException(
            status_code=502,
            detail=f"yt-dlp could not download this file: {last_error or 'requested format is not available'}",
        )
    except HTTPException:
        shutil.rmtree(download_dir, ignore_errors=True)
        raise
    except Exception as exc:  # pragma: no cover - surfaced to API caller
        shutil.rmtree(download_dir, ignore_errors=True)
        raise HTTPException(
            status_code=502,
            detail=f"yt-dlp could not download this file: {exc}",
        ) from exc


app = FastAPI(title="Decan Video Downloader", version="1.0.0")

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
    type: str = Query("video", min_length=1, max_length=20),
    playlist: bool = Query(False),
):
    media_type = type.lower() if type else "video"
    if media_type not in {"video", "audio"}:
        raise HTTPException(status_code=400, detail="Media type must be 'video' or 'audio'.")

    file_path, filename, media_type_header = fetch_downloaded_file(url, media_type, format, playlist)
    # The file response owns the cleanup of the temp directory after it streams.
    return FileResponse(
        file_path,
        filename=filename,
        media_type=media_type_header,
        background=BackgroundTask(shutil.rmtree, str(Path(file_path).parent), ignore_errors=True),
    )


@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return FileResponse(INDEX_FILE)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)