# Release checklist

## Current release candidate

Version: `0.1.0` (alpha). Project: https://github.com/jayty97/braindump. Original source is MIT licensed. Python source/wheel packages and Windows launchers are provided; native installers are not included.

## Before publication

1. Check version metadata, the MIT license, third-party notices, and the changelog.
2. Run `python -m pytest -q` and build with `python -m build`.
3. Run a real microphone walkthrough: record, pause, resume, minimize, stop from the tray, reopen, and verify duration.
4. With explicitly supplied test credentials, smoke-test the selected providers on non-sensitive audio. Confirm billing and model access in the provider dashboard. Test offline/network failure, a longer recording, and successful retry.
5. Inspect the source distribution for credentials or personal session material. User data belongs outside the repository. The checked-in screenshot contains synthetic text only.
6. Review the GitHub Actions results for all supported test platforms. Publish only to the authorized repository, with accurate alpha/validation notes. Never force-push over unrelated user work.

## Optional Windows executable

On Windows, after installing `.[dev]`:

```powershell
python -m PyInstaller --noconfirm --windowed --onedir --name DictateWorkbench --collect-all sounddevice --hidden-import keyring.backends.Windows launch.pyw
```

Distribute the entire `dist/DictateWorkbench` directory, not just the executable. Test from a fresh Windows user account without Python installed. Executables are unsigned until the owner supplies a signing process. Review bundled dependencies and include their required license notices before distribution.

The GitHub workflow runs tests and builds Python source/wheel artifacts on Windows, Ubuntu, and macOS. It never publishes packages or GitHub releases automatically. Running workflows on the remote repository is subject to the owner's GitHub Actions settings.

## Compatibility

Windows is the initial locally tested platform. macOS/Linux are included in CI, but still need platform-specific microphone and tray testing before declaring production readiness. GPU filtering is optional on Windows through a separately installed Broadcast / RTX Voice virtual microphone. The app does not redistribute NVIDIA software.
