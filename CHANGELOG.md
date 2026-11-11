# Changelog

## Unreleased

- Add a fictional Chinese single-fact example and a preparation guide covering
  source links, character counts, installed voices, and recovery from input errors.
- Clarify the `audio_status` field and check the Chinese text example in CI.
- Document Python 3.12+ for macOS audio, which may use extended PCM WAV headers;
  text output remains supported on Python 3.10+.

## 0.1.0 — 2026-11-08

First public extraction of the briefing-to-podcast workflow:

- Evidence-linked editorial checks, including source/fact references, caveats,
  protected qualifiers and explicit coverage limits.
- Local HTML and transcript rendering, with a fully fictional example.
- macOS speech synthesis to verified M4A and optional verified MP3 conversion.
- Checksummed output, repeat-run caching, failure receipts and atomic file writes.
- Offline unit tests and a text-only CI smoke test.

Mail ingestion, AI drafting, neural voice cloning, scheduling and cloud delivery
are upstream or future integrations and are not included in this release.
