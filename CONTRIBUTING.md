# Contributing

Keep Dictate focused on one workflow: record a walkthrough and produce a faithful next-iteration prompt.

Use Python 3.11+, install `.[dev]`, and run `python -m pytest -q`. Include a focused regression test when changing recording, persistence, request routing, or retry behavior. Tests must use synthetic audio and mocked requests; never require a real API key.

Keep microphone callbacks free of disk and network work. Keep UI changes on the Qt main thread. Preserve existing session audio on errors. New providers need official API references and contract tests. Do not silently select a different provider or send credentials to an unrelated URL.

Do not include personal recordings, keys, `.env` files, local settings, or transcripts in contributions. Use synthetic examples for screenshots. Check [docs/RELEASING.md](docs/RELEASING.md) before packaging.

The project owner must select a license before external contributions or public distribution. See [LICENSE-PENDING.md](LICENSE-PENDING.md).
