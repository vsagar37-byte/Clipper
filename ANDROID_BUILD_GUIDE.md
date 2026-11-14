# ClipForge AI v0.4.1 — Android build guide

## Recommended first setup: local backend
Use a Windows/Mac/Linux computer to run Python + FFmpeg, and an Android phone on the **same Wi-Fi**. This is free to host locally. For use away from home, deploy the backend behind HTTPS (requires a server, storage and operational security).

## 1. Start the backend
Install Python 3.10+ and FFmpeg (both `ffmpeg` and `ffprobe` must be on PATH).

Windows PowerShell from the project root:
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
pip install faster-whisper
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

macOS/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
pip install faster-whisper
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Find the computer's Wi-Fi IPv4 address (`ipconfig` on Windows; `ip addr` or Network settings on Linux/macOS). Example: `192.168.1.10`. From your phone browser, verify `http://192.168.1.10:8000/api/health` loads. Allow inbound TCP port 8000 on the computer's firewall for **private networks only**. Do not forward the port to the public internet.

## 2. Generate Android project and debug APK
Install Node.js 20+, Android Studio, Android SDK (API 35 or supported latest), SDK Build-Tools, and JDK 17. Open a terminal in the **android** folder:

```bash
npm install
npm run android:init
```

`android:init` copies the web frontend into Android assets, creates the native Capacitor project, enables LAN HTTP for development, and syncs assets. Then open the native project:

```bash
npm run android:open
```

In Android Studio, wait for Gradle sync. Select **Build > Build Bundle(s) / APK(s) > Build APK(s)**. The debug APK will be at:

`android/android/app/build/outputs/apk/debug/app-debug.apk`

Alternative from the `android` folder (after Android Studio/SDK setup):

macOS/Linux:
```bash
cd android
./gradlew assembleDebug
```

Windows PowerShell:
```powershell
cd android
.\gradlew.bat assembleDebug
```

Install the APK using Android Studio, `adb install -r app-debug.apk`, or copy the APK to your phone and allow installation from that source.

## 3. Configure backend on the phone
Open ClipForge AI, enter `http://YOUR_COMPUTER_WIFI_IP:8000` in **Backend connection**, and press **Save & reconnect**. Test upload, captions and export. Phone and computer must remain on the same Wi-Fi and the backend must stay running.

## 4. Make changes
After changing frontend files, from the `android` folder run `npm run android:sync`, then rebuild the APK. Android Studio may need a Gradle sync.

## 5. Production release
For internet access use an HTTPS backend with authentication, restrictive CORS, quotas, storage retention and job persistence. Change Android network security to disallow cleartext, and use Android Studio **Build > Generate Signed Bundle / APK** with a private signing key. **Never commit or share your signing key.** For Play Store distribution, use a signed Android App Bundle (AAB).

## Known limitations
- This package contains Android source/configuration, **not** a precompiled APK. Native compilation requires Android Studio + SDK.
- Current backend jobs are in memory; restarting it loses job state. The MVP does not provide accounts or production-grade multi-user isolation.
- Captions require `faster-whisper` and language-appropriate server fonts. FFmpeg must support libass for subtitle burn-in.
- Automatic highlight scoring is heuristic, not a virality prediction.
- Native downloads depend on Android WebView behavior; for reliable Downloads-folder integration, add a Capacitor filesystem/share plugin in a later release.
- Android LAN HTTP is explicitly enabled for development only; use HTTPS for public hosting.
