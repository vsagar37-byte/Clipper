# ClipForge AI cloud backend — Render
This repository contains a Render Blueprint (render.yaml) and a Dockerfile.
Deployment requires a Render account with access to the repository.

## Deploy
1. Sign into https://dashboard.render.com and connect your GitHub account.
2. Choose New > Blueprint and select vsagar37-byte/Clipper.
3. Confirm the Blueprint shows Free compute and no persistent disk. Check the workspace billing settings and included build and bandwidth limits before deploying. If a payment method is on file, Render can bill for overages.
4. Once deployed, visit https://YOUR-SERVICE.onrender.com/api/health and confirm ffmpeg is true.
5. In Render's Environment settings, copy the generated `CLIPFORGE_ACCESS_KEY`.
   For an existing service, set a unique random key of at least 32 characters
   and set `CLIPFORGE_REQUIRE_ACCESS_KEY=1` before making it available.
6. In ClipForge, enter the HTTPS backend URL and access key, then select
   **Save & reconnect**. The app keeps the key in memory for the current session.
   Rotate the key in Render if access needs to be revoked.

## Important security limitations
The access key protects processing and media endpoints. Render's health check
and the app shell remain public. Treat the key as single-owner access: everyone
with it can access video or job IDs they have. The app has no per-user
isolation, request quotas, malware screening, or scheduled video deletion.
Keep the key private and use a single operator per deployment. Local development
can run without a key when the backend binds to loopback.
Free instances can idle and lose uploads and exports on spin-down, restart, or redeploy. Download finished clips promptly. Jobs are in-memory and are also lost when the service stops.
Automatic captions use faster-whisper and may exceed the Free instance's memory. Caption performance needs to be verified on Render.

## Direct YouTube import (v0.5)

Deploy the matching frontend and backend together and rebuild the Android APK.
Paste a public YouTube link and choose **Import & find highlights**. The Docker
image includes yt-dlp, its JavaScript support package, Node.js, and FFmpeg.

Set MAX_DURATION_SECONDS=3600 for videos up to one hour; older services may still
have the previous 1800-second value. MAX_UPLOAD_MB defaults to 200 on Render.
Only one import runs at once. Downloads time out after 15 minutes and return a
clear error if YouTube rejects the server. No login credentials, cookies, or
proxy rotation are used. File upload remains the fallback. Free hosting may not
have enough memory for speech analysis; direct import does not change that.
