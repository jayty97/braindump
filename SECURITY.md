# Security

BrainDump is an early-stage local desktop application. Keep dependencies current and use API keys with appropriate provider-side limits.

Do not disclose credentials, personal transcripts, recordings, or sensitive exploit details in public issues. Use GitHub's **Security → Report a vulnerability** feature when available. If private reporting is unavailable, open an issue requesting a private contact channel without including the sensitive details.

The application sends audio and text only to the providers selected by the user when Process is clicked. A custom provider URL is a trust decision. Saved sessions are not encrypted by the application. API keys can be held in memory or saved using the operating system's credential store.
