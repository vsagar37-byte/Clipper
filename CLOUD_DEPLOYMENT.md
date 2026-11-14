# ClipForge AI cloud backend — Render
This repository contains a Render Blueprint (render.yaml) and a Dockerfile.
**Not deployed yet.** A Render account and approval of the plan are required.

## Deploy
1. Sign into https://dashboard.render.com and connect your GitHub account.
2. Choose New > Blueprint and select vsagar37-byte/Clipper.
3. Review Render's displayed monthly charges before approving the Starter service and 10 GB persistent disk. Pricing and plan availability may change.
4. Once deployed, visit https://YOUR-SERVICE.onrender.com/api/health and confirm ffmpeg is true.
5. In the ClipForge Android app, set the backend URL to the HTTPS service URL.

## Important security limitations
The current MVP has no authentication, per-user isolation, request quotas, malware screening, or scheduled video deletion. Do not make this service publicly accessible or upload sensitive videos until access control and retention policies are implemented. Render's public URL is reachable by others, even when not advertised.
The frontend controller also requires end-to-end testing and API contract fixes before video processing can be relied upon.
The included persistent disk is needed because videos are stored on the local filesystem. Jobs are in-memory and lost on restarts.
Automatic captions use faster-whisper and may require more memory than the selected instance. Larger Whisper models may require a more powerful plan.
