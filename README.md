# ClipForge MVP — Web + Android

A runnable local-first video clipper with a responsive browser UI, manual trimming, automatic scene/audio highlight suggestions, optional speech-aware analysis, aspect-ratio exports, optional subtitle burn-in, and an Android Capacitor wrapper.

## Requirements

- Python 3.10+; FFmpeg and FFprobe installed and available on PATH.
- Node.js 18+ and Android Studio for Android packaging.

## Run web app

From the project root. Use Python 3.10 or newer. macOS system `python3` is often 3.9, which cannot run this app.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\\Scripts\\activate
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. The API docs are at **http://127.0.0.1:8000/docs**.

Optional speech-aware analysis and subtitle transcripts:

```bash
pip install faster-whisper
```

Check **http://127.0.0.1:8000/api/health** to see whether transcription is available. First model use may download weights and can be slow. Check your FFmpeg build includes the `subtitles` filter (`ffmpeg -filters | grep subtitles`).

## Android development

The Android app is a Capacitor shell. **The video processing server is required** and runs separately. For Android devices, deploy FastAPI behind HTTPS on a server reachable by the phone; the phone cannot access `127.0.0.1` on your computer. Create `frontend/config.js` containing:

```js
window.CLIPFORGE_API_URL = 'https://YOUR-BACKEND-DOMAIN';
```

Then insert `<script src="/config.js"></script>` before the existing `app.js` script in `frontend/index.html`. The default frontend calls the same origin as its backend, so this is only needed when the Android shell serves local bundled files. **HTTPS is required for production.**

```bash
cd android
npm install
npx cap add android
npm run sync
npm run open
```

In Android Studio, connect a device/emulator and run or build an APK. Android SDK, Java, and Gradle must be installed via Android Studio. `npx cap sync` copies the frontend files into the Android project. On some Android configurations, file upload from a WebView may require additional native file-chooser configuration.

## Architecture

- `frontend/`: plain HTML/CSS/JS, responsive web UI and PWA shell
- `backend/main.py`: FastAPI endpoints, uploads, highlight scoring, FFmpeg exports
- `android/`: Capacitor wrapper configuration
- `data/`: local uploads and rendered exports (auto-created)

## API

- `GET /api/health`
- `POST /api/upload` (multipart `file`)
- `GET /api/videos/{id}/source`
- `POST /api/videos/{id}/analyze` (`clip_length`, `count`, `transcribe`)
- `POST /api/videos/{id}/export` (`start`, `end`, `aspect`, `subtitles`, `transcript`)
- `GET /api/jobs/{job_id}`
- `GET /api/exports/{id}/{job_id}`

## Important MVP limitations

1. Automatic scoring is **heuristic** (scene cuts, silence, optional speech keywords). It is not a learned virality model or a guaranteed viral score.
2. The app accepts **local video uploads**, not YouTube URL downloads. For third-party videos, upload only content you have permission to process.
3. 9:16 reframing uses center crop, **not** speaker/object tracking. It can crop out an off-center subject.
4. Subtitle generation requires optional Whisper transcription and an FFmpeg build with libass. Transcript language support depends on the installed Whisper model.
5. Jobs are in memory and exports are stored on local disk; there is no login, persistent job queue, automatic cleanup, cloud storage, or multi-user isolation.
6. Do **not** expose this MVP directly to the public internet without authentication, upload security, rate limits, sandboxing, job queues, CORS restrictions, and storage quotas. FFmpeg processes untrusted media; keep it patched.
7. Android project source is included as a wrapper configuration, **not** a prebuilt APK. Android SDK builds must be run locally.

## Quick test

Run the included test script after starting the server:

```bash
python tests/smoke_test.py
```

This generates a tiny synthetic video with FFmpeg, uploads it, analyzes it, exports a 9:16 clip, and checks the resulting MP4.


## v0.4 — Creator captions studio

Enable **Auto Captions** on the Export panel, then select caption style (Classic/Bold/Outline/Neon), font, text color, highlight color, position, and font size. Word-by-word highlighting uses Whisper word timestamps. The browser shows a **style preview** (not time-synced). The backend creates ASS animated subtitle events and burns them into the MP4 with FFmpeg/libass; a separate SRT is downloadable.

Install `pip install faster-whisper` to transcribe new videos. Models download on first use and may take time. The selected FFmpeg build must support the `ass` filter (`ffmpeg -filters | grep ass`). For Telugu/Hindi, install Noto Sans Telugu / Noto Sans Devanagari on the rendering server. Word highlighting works best with generated word timestamps; supplied transcripts without word timestamps render as sentence captions. Subtitles are generated server-side on export if not already available. For production, add persistent jobs, authentication, quotas, and a managed model cache.


## v0.4 Caption timeline editor

- **Auto transcribe** (requires `pip install faster-whisper`) populates editable speech cues. Alternatively, **Add caption** allows fully manual captions without Whisper.
- Click a caption block to select it, drag the body to shift its timing, or drag either edge to resize. Tap elsewhere in the timeline to seek the video.
- Edit text and exact start/end seconds in the inspector, delete selected cues, and undo edits.
- Choose **None**, **Fade in/out**, or **Pop in** caption animation in Caption Studio.
- The video preview displays current caption text in the style sample; it does **not** render frame-accurate animations before export. The exported MP4 burns ASS subtitles using FFmpeg.
- Edited text/timing overrides original transcription when exporting. Editing a cue invalidates its original word timestamps, so that cue uses whole-line captions rather than inaccurate word highlighting.
- Export MP4 and SRT reflect all timeline edits. Captions must be enabled for export; if no cues exist, Whisper transcribes automatically if installed.
- Android is still a Capacitor source wrapper, not a compiled APK. Backend must be accessible over the network.
