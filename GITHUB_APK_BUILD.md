# Build an installable Android APK using GitHub Actions

This project includes `.github/workflows/build-debug-apk.yml`, which compiles the Android APK on a GitHub-hosted Ubuntu runner. You do not need Android Studio on your own computer for this method.

1. Create a new **private** GitHub repository (e.g. `clipforge-ai`).
2. Upload **all the contents** of this extracted project into the repository root, including the hidden `.github/workflows` directory. GitHub's web upload interface can upload a folder's files; using Git on a computer is more reliable for preserving hidden folders.
3. Open your repository's **Actions** tab, select **Build ClipForge Android APK**, and click **Run workflow** on the `main` branch.
4. Wait for the build to finish. Open the completed run and download the artifact named `clipforge-ai-debug-apk`.
5. Unzip the downloaded artifact to get `app-debug.apk`. Copy it to your Android phone and install it. You may need to allow installation from your Files app.
6. Run the Python + FFmpeg backend on a computer as described in `ANDROID_BUILD_GUIDE.md`. Connect the phone to the same Wi-Fi and enter `http://YOUR_COMPUTER_IP:8000` in the app.

This is a **debug APK** for personal testing, not a Play Store release. It will not process video when the backend is offline. If the build fails, read the log in the Actions run; dependencies and Android tooling may change over time. No APK has been built or device-tested in the current environment.
