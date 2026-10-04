# Social Media Downloader

A small FastAPI app that lets a browser download public media links using `yt-dlp`, with a polished single-page frontend and Vercel-ready deployment setup.

## Features

- Download public videos from supported sites via `yt-dlp`
- Clean single-page UI with quality selector
- Browser-triggered file download
- Works as a FastAPI app locally and on Vercel
- Suitable for internal tools or lightweight educational/demo projects

## Important note

This project is intended for downloading media you are legally allowed to save and distribute. Respect platform terms of service, copyright law, and the rights of content creators.

## Tech stack

- Python 3.12+
- FastAPI
- yt-dlp
- Vercel Serverless Functions

## Project structure

- `main.py` – FastAPI application and download endpoint
- `api/index.py` – Vercel entrypoint that imports the app
- `index.html` – frontend UI for choosing a URL and download quality
- `vercel.json` – Vercel routing and function config
- `example.env` – sample environment variables
- `requirements.txt` – Python dependencies

## Local development

1. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Start the app:

   ```bash
   uvicorn main:app --reload
   ```

4. Open `http://localhost:8000` in your browser.

## Environment variables

Copy `example.env` to `.env` and update it if needed:

```env
ALLOWED_ORIGIN=http://localhost:8000
```

You can also set a comma-separated list when you need multiple origins:

```env
ALLOWED_ORIGIN=https://example.com,https://staging.example.com
```

If you leave it unset, the app allows all origins by default.

## Download endpoint

`GET /download?url=https://example.com/video&format=best`

Parameters:

- `url` – public video URL
- `format` – `yt-dlp` format selector; defaults to `best`

Example:

```bash
curl "http://localhost:8000/download?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&format=best[height<=720]/best"
```

## Deploying to Vercel

1. Push this project to a GitHub repository.
2. Import it into Vercel.
3. Set the Python version to `3.12` if the platform asks.
4. Add any required environment variables in the Vercel dashboard.
5. Deploy.

The app is configured to serve both the UI and the API through a Vercel Python serverless function:

- `/` -> frontend
- `/download` -> media download route

## Vercel function settings

```json
{
  "functions": {
    "api/**/*.py": {
      "maxDuration": 300
    }
  }
}
```

Python is auto-detected from the function under `api/`; do not set `runtime: "python3.12"` here. Vercel's `runtime` property expects a versioned runtime identifier, not a Python version.

## Known limitations

- Vercel serverless environments are not ideal for very large downloads or long-running jobs; this project keeps the download logic lightweight and uses a timeout budget of up to 5 minutes.
- Some platforms block or rate-limit downloads and may require a public, non-private URL.
- Unsupported or geo-restricted links may fail even if they are valid to a browser.

## License

This project is provided for educational and legitimate personal use. The author is not responsible for misuse or copyright violations.
