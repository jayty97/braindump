# Release checklist

## Current release candidate

Version: `0.1.0`. Source and a Windows launcher are provided. No GitHub repository, public release, or paid API test is created automatically.

## Before publication

1. Obtain the owner's license choice. Replace `LICENSE-PENDING.md` with the full approved license and add license metadata to `pyproject.toml`. This is required before claiming an open-source release.
2. Run `python -m pytest -q` and build with `python -m build`.
3. Run a real microphone walkthrough: record, pause, resume, minimize, stop from the tray, reopen, and verify duration.
4. With explicitly supplied test credentials, smoke-test the selected providers on non-sensitive audio. Confirm billing and model access in the provider dashboard. Test offline/network failure, a longer recording, and successful retry.
5. Inspect the source distribution for credentials or personal session material. User data belongs outside the repository. The checked-in screenshot contains synthetic text only.
6. Confirm the requested GitHub owner, repository name, visibility, and authorization before publishing.

## Optional Windows executable

On Windows, after installing `.[dev]`:

```powershell
python -m PyInstaller --noconfirm --windowed --onedir --name DictateWorkbench --collect-all sounddevice --hidden-import keyring.backends.Windows launch.pyw
```

Distribute the entire `dist/DictateWorkbench` directory, not just the executable. Test from a fresh Windows user account without Python installed. Executables are unsigned until the owner supplies a signing process. Review bundled dependencies and include their required license notices before distribution.

The GitHub workflow runs tests and builds Python source/wheel artifacts on Windows. It never publishes packages or GitHub releases. Running workflows on a remote repository is subject to the owner's GitHub Actions settings.

## Compatibility

Windows is the initial locally tested platform. macOS/Linux support needs platform-specific microphone and tray testing before declaring it release-ready. GPU filtering is optional through a separately installed Broadcast / RTX Voice virtual microphone. The app does not redistribute NVIDIA software.
