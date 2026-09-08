# Validation — 0.1.0

Locally checked September 8, 2026, on Windows with Python 3.12.4.

- 28 automated tests passed, using synthetic audio and mocked HTTP responses.
- Simulated one-hour recording split into 13 overlapping chunks with complete coverage and bounded upload size.
- High-sample-rate uploads remained below 20 MB.
- Recorder queue draining, pause behavior, and overflow handling passed.
- Interrupted processing reused completed transcription work; changed context regenerated only the prompt.
- Provider request contracts checked for OpenAI Responses / current transcription language hints, compatible Chat Completions, Groq-style transcription, and ElevenLabs auth / multipart fields.
- Incomplete responses, truncation, unsafe URLs, and redacted error handling checked.
- UI session loading, prompt edit persistence, cleared text persistence, key isolation, current defaults, and NVIDIA device fallback checked.
- Real Qt interface rendered and visually inspected with synthetic example content.
- Local default microphone accepted a 16 kHz mono input configuration. No NVIDIA Broadcast / RTX Voice virtual input was detected.
- Dependency consistency check passed. Python source and wheel distributions built successfully.

Not yet verified: real speech recording quality, paid transcription or writing requests, a real 30–60 minute hardware recording, NVIDIA virtual-device audio quality, and macOS/Linux hardware behavior. Those checks require the user's configured devices / provider accounts and suitable platforms. No keys were supplied and no paid API calls were made during development.

The project is MIT licensed. Cross-platform CI is configured in the [GitHub repository](https://github.com/jayty97/braindump/actions/workflows/tests.yml); consult its actual run results for current Windows, Linux, and macOS test status. CI uses mocked audio and providers and does not replace the manual hardware checks above.
