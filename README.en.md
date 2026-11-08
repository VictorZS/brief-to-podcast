# Brief to Podcast

Turn an **already edited, evidence-linked briefing** into a readable HTML page, transcript, and checked local speech audio.

[中文说明](README.md) · [Input contract](docs/input-format.md) · [Editorial prompt](prompts/editorial.md) · [MIT License](LICENSE)

The engine accepts `episode.json` from your own collection and editing workflow. It checks reference consistency, protected factual qualifiers, coverage declarations, and a three-part editorial structure before rendering. It does not connect to Gmail, write a summary with an AI service, schedule jobs, or publish files to a cloud service.

## Try the fictional example

Python 3.10+ on macOS or Linux; no third-party Python dependency for text output. Windows is not supported in v0.1.

```sh
git clone https://github.com/VictorZS/brief-to-podcast.git
cd brief-to-podcast
python3 scripts/render_episode.py examples/episode.json --output output/demo --text-only
```

Open `output/demo/index.html`. Every event, message, number, and source in the example is fictional. The example links use `example.com`; the renderer does not fetch them.

On macOS, generate M4A speech with the installed system voice:

```sh
python3 scripts/render_episode.py examples/episode.json --output output/demo
open output/demo/index.html
```

The example uses `Samantha` at 165 words per minute. List available voices with `say -v '?'`. Copy `config.example.json` to `config.local.json` to choose an installed voice suitable for your input language, then pass `--config config.local.json`. No voices or models are downloaded.

For MP3, install FFmpeg with `libmp3lame` on your `PATH`, or install the optional Python dependency in a virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-audio.txt
python3 scripts/export_mp3.py output/demo
```

MP3 export verifies the source checksum, encodes mono 44.1 kHz / 96 kbps, decodes and checks the result, and writes `mobile_audio.json`. Before using the MP3, require `status: ready` and a `render_fingerprint` matching the current manifest, then verify the file hash. Rerendering marks an old MP3 receipt `stale`; an old file remaining on disk is not proof of a current result. FFmpeg is a separately licensed tool; this repository does not distribute its binaries.

## What can be reused

- Fact and source IDs connecting written paragraphs and spoken segments to evidence.
- Literal-preservation checks for selected numbers and qualifiers during editing.
- Explicit partial coverage and current-versus-historical notification review.
- A compact structure: overview, insight, notifications; counterargument and a condition that would change the judgment.
- Empty/silent audio checks, decoding and duration checks, chapter timestamps, and output hashes.
- Per-output-directory locking, atomic writes, a manifest written last, and verified audio reuse for identical inputs and configuration.

A failed speech run still produces readable outputs. Inspect the command's exit code and `manifest.json`: `ready`, `text_only`, or `failed`. A run in progress can have `processing` status; an interrupted run is not a finished result. Use a separate output directory per episode to preserve history. Trust the manifest and its hashes rather than the existence of an output file.

**These checks do not establish factual truth or editorial quality.** They check structure, references, and literal preservation, not the semantic relationship between a claim and its source. Audio checks cannot evaluate pronunciation or listening quality. A successful local run does not establish unattended operation or mobile delivery.

## Integrate and develop

Use [the input contract](docs/input-format.md) and [the editorial prompt](prompts/editorial.md) to prepare your own JSON upstream. Treat source content as untrusted data. Keep real inputs and outputs out of the repository; `examples/` is exclusively for synthetic material.

```sh
python3 -m unittest discover -s tests -v
```

The first release includes no mailbox credentials, neural voice models, reference voices, personal reports, scheduler, cloud sync, RSS feed, or podcast platform upload. Source code is MIT licensed; your content and external tools retain their own terms.
