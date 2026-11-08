#!/usr/bin/env python3
"""Render an evidence-linked briefing and local macOS speech. No network I/O.

Extracted from the author's private briefing workflow; public inputs are supplied separately.
"""
from __future__ import annotations

import argparse
from array import array
from datetime import datetime
import fcntl
import hashlib
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlparse
import wave

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(ep):
    require(isinstance(ep, dict), "Episode must be an object")
    require(ep.get("schema_version") == 1, "Unsupported schema_version")
    for key in ("title", "overview", "window", "coverage", "sources", "signals", "actions", "segments"):
        require(key in ep, f"Missing {key}")
    require(isinstance(ep["title"], str) and ep["title"].strip(), "Empty title")
    require(isinstance(ep["overview"], str) and ep["overview"].strip(), "Empty overview")
    for key in ("sources", "signals", "actions", "segments", "sections"):
        require(isinstance(ep.get(key, []), list), f"{key} must be a list")
        require(all(isinstance(item, dict) for item in ep.get(key, [])), f"{key} entries must be objects")
    require(isinstance(ep["window"], dict), "Window must be an object")
    start, end = [datetime.fromisoformat(ep["window"][k]) for k in ("start", "end")]
    require(start.utcoffset() is not None and end.utcoffset() is not None and start < end,
            "Window must have timezone offsets and start < end")
    require(isinstance(ep["coverage"], dict), "Coverage must be an object")
    require(isinstance(ep["coverage"].get("complete"), bool), "Coverage complete must be boolean")
    require(isinstance(ep["coverage"].get("accounts"), list), "Coverage accounts must be a list")
    for account in ep["coverage"]["accounts"]:
        require(isinstance(account, dict) and isinstance(account.get("email"), str), "Account missing label")
        require(isinstance(account.get("categories"), dict), "Account categories must be an object")
        counts = list(account["categories"].values())
        require(all(type(n) is int and n >= 0 for n in counts), "Invalid category counts")
        require(type(account["count"]) is int and sum(counts) == account["count"],
                "Category counts do not match message count")
    sources = ep["sources"]
    require(all(isinstance(s.get("id"), str) and s["id"].strip() for s in sources), "Missing source ID")
    ids = {s["id"] for s in sources}
    require(len(ids) == len(sources), "Duplicate source IDs")
    for source in sources:
        require(isinstance(source.get("url"), str), "Source missing URL")
        url = urlparse(source["url"])
        require(url.scheme == "https" and bool(url.netloc) and not url.username,
                "Sources must use ordinary HTTPS URLs")
        for key in ("title", "origin", "published_at", "access"):
            require(isinstance(source.get(key), str), f"Source missing {key}")
    require(ep["segments"], "Empty podcast")
    for section in ep.get("sections", []) + ep["signals"] + ep["actions"] + ep["segments"]:
        require(isinstance(section.get("source_ids"), list), "Missing source_ids")
        require(all(isinstance(ref, str) for ref in section["source_ids"]), "Source IDs must be strings")
        require(set(section["source_ids"]) <= ids, "Unknown source reference")
        require(isinstance(section.get("title"), str), "Missing section title")
    for signal in ep["signals"]:
        for key in ("id", "fact", "inference", "counterevidence", "confidence", "change", "next_check"):
            require(isinstance(signal.get(key), str) and signal[key].strip(), f"Signal missing {key}")
        require(signal["source_ids"], "Signal has no evidence")
    for section in ep.get("sections", []):
        require(isinstance(section.get("text"), str), "Section missing text")
    for action in ep["actions"]:
        for key in ("priority", "detail", "deadline"):
            require(isinstance(action.get(key), str), f"Action missing {key}")
    for segment in ep["segments"]:
        require(isinstance(segment.get("text"), str) and segment["text"].strip(), "Empty segment")
        require(not re.search(r"https?://|\[\[|\]\]", segment["text"]),
                "Spoken text must not contain URLs or speech engine commands")


def atomic_text(path, text):
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".write-", delete=False) as out:
        tmp = Path(out.name)
        out.write(text)
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def episode_hash(ep):
    return hashlib.sha256(json.dumps(ep, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def safe_file(directory, name):
    """Manifest references must stay within their output directory, without symlinks."""
    require(isinstance(name, str) and name not in {"", ".", ".."}
            and Path(name).name == name and "/" not in name and "\\" not in name,
            "Unsafe manifest filename")
    path = directory / name
    require(not path.is_symlink(), "Manifest file cannot be a symlink")
    return path


def check_wave(path, min_seconds=1):
    with wave.open(str(path), "rb") as src:
        require(src.getsampwidth() == 2, "Expected 16-bit PCM audio")
        frame_width = src.getsampwidth() * src.getnchannels()
        declared_frames = src.getnframes()
        duration = declared_frames / src.getframerate()
        require(duration >= min_seconds, "Speech engine returned empty or truncated audio")
        peak = 0
        actual_bytes = 0
        while data := src.readframes(65536):
            actual_bytes += len(data)
            require(len(data) % frame_width == 0, "Truncated PCM frame")
            samples = array("h", data)
            if sys.byteorder != "little":
                samples.byteswap()
            peak = max(peak, max((abs(n) for n in samples), default=0))
        require(actual_bytes == declared_frames * frame_width, "Truncated PCM audio")
        require(peak > 32, "Speech engine returned silent audio")
    return duration


def run(command):
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=600)


def synthesize(ep, config, directory):
    require(config.get("speech_engine", "macos") == "macos", "Unsupported speech engine")
    require(sys.platform == "darwin", "Audio synthesis requires macOS; use --text-only on Linux")
    chapters = []
    output = directory / "episode.wav"
    with wave.open(str(output), "wb") as combined:
        combined.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
        elapsed = 0.0
        for i, segment in enumerate(ep["segments"]):
            speech = directory / f"part-{i}.txt"
            sound = directory / f"part-{i}.wav"
            speech.write_text(segment["text"], encoding="utf-8")
            run(["/usr/bin/say", "-v", config["voice"], "-r", str(config["speaking_rate"]),
                 "-f", str(speech), "-o", str(sound), "--data-format=LEI16@22050", "--channels=1"])
            duration = check_wave(sound, max(1, len(segment["text"]) / 25))
            chapters.append({"title": segment["title"], "start_seconds": round(elapsed, 3),
                             "duration_seconds": round(duration, 3)})
            with wave.open(str(sound), "rb") as part:
                require(part.getframerate() == 22050 and part.getnchannels() == 1,
                        "Unexpected speech sample format")
                while data := part.readframes(65536):
                    combined.writeframes(data)
            elapsed += duration
            if i < len(ep["segments"]) - 1:
                combined.writeframes(b"\0" * 22050)  # Half a second, mono 16-bit.
                elapsed += 0.5
    duration = check_wave(output)
    compressed = directory / "episode.m4a"
    run(["/usr/bin/afconvert", "-f", "m4af", "-d", "aac", "-b", "64000", str(output), str(compressed)])
    require(compressed.stat().st_size > 1000, "Encoded audio is empty")
    decoded = directory / "verified.wav"
    run(["/usr/bin/afconvert", "-f", "WAVE", "-d", "LEI16@22050", str(compressed), str(decoded)])
    decoded_duration = check_wave(decoded)
    require(abs(duration - decoded_duration) < 2, "Encoded audio failed duration check")
    return compressed, duration, chapters


def render_html(ep, manifest):
    esc = lambda value: html.escape(str(value), quote=True)
    source_map = {s["id"]: s for s in ep["sources"]}
    def refs(ids):
        return '<p class="sources">' + " · ".join(
            f'<a href="{esc(source_map[i]["url"])}">{esc(source_map[i]["title"])}</a>' for i in ids) + '</p>'
    def paras(text):
        return "".join(f"<p>{esc(p)}</p>" for p in text.split("\n") if p.strip())
    parts = [f'<header><p class="eyebrow">每日信息简报 · AI 合成语音</p><h1>{esc(ep["title"])}</h1>',
             f'<p class="meta">{esc(ep["window"]["start"])} — {esc(ep["window"]["end"])}</p></header>']
    if manifest["audio_status"] == "ready":
        mins, secs = divmod(round(manifest["duration_seconds"]), 60)
        parts.append(f'<section class="player"><strong>{mins} 分 {secs:02d} 秒 · 本机合成语音</strong>'
                     f'<audio controls preload="metadata" src="{esc(manifest["audio_file"])}"></audio>'
                     f'<a href="{esc(manifest["audio_file"])}" download>下载音频</a> · '
                     '<a href="transcript.txt" download>下载逐字稿</a></section>')
    else:
        parts.append(f'<p class="notice">文字已完成，音频未生成。{esc(manifest.get("error", ""))}</p>')
    structured = ep.get("editorial", {}).get("version") == 3
    if structured:
        for part, heading in [("inbox", "一 邮箱全貌"), ("insights", "二 洞察浓缩"), ("notifications", "三 通知与近期事项")]:
            parts.append(f'<section data-part="{part}"><h2>{heading}</h2>')
            for section in ep.get("sections", []):
                if section["part"] == part:
                    parts.append(f'<article><h3>{esc(section["title"])}</h3>' + paras(section["text"])
                                 + refs(section["source_ids"]) + '</article>')
            if part == "inbox":
                parts.append('<table><tr><th>账户</th><th>邮件数</th><th>分类</th></tr>')
                for account in ep["coverage"]["accounts"]:
                    categories = "；".join(f"{k} {v} 封" for k, v in account["categories"].items())
                    parts.append(f'<tr><td>{esc(account["email"])}</td><td>{account["count"]}</td><td>{esc(categories)}</td></tr>')
                parts.append('</table>')
            if part == "insights":
                questions = ep["briefing"]["research_questions"]
                if questions:
                    parts.append('<h3>可以继续追问</h3>')
                    for q in questions:
                        parts.append(f'<article><h3>{esc(q["question"])}</h3><p>{esc(q["why_it_matters"])}</p>'
                                     f'<p>调研起点：{esc(q["starting_point"])}</p>' + refs(q["source_ids"]) + '</article>')
            if part == "notifications":
                for action in ep["actions"]:
                    parts.append(f'<article><h3>{esc(action["priority"])} · {esc(action["title"])}</h3>'
                                 + paras(action["detail"]) + f'<p>进展：{esc(action["change"])}</p>'
                                 + f'<p>期限：{esc(action["deadline"])}</p><p>下一步：{esc(action["next_step"])}</p>'
                                 + refs(action["source_ids"]) + '</article>')
                parts.append('<p class="meta">' + esc(ep["briefing"]["notification_review"]["scope_note"]) + '</p>')
            parts.append('</section>')
        parts.append('<details><summary>依据与完整口播</summary>')
    else:
        parts.append('<section><h2>今天的整体判断</h2>' + paras(ep["overview"]) + '</section>')
    for section in ([] if structured else ep.get("sections", [])):
        parts.append(f'<section><h2>{esc(section["title"])}</h2>' + paras(section["text"]) + refs(section["source_ids"]) + '</section>')
    parts.append('<section><h2>值得持续观察的信号</h2>')
    for signal in ep["signals"]:
        parts.append(f'<article><h3>{esc(signal["title"])}</h3>')
        for key, label in [("fact", "事实"), ("inference", "判断"), ("counterevidence", "其他解释 / 反证"),
                           ("confidence", "置信度"), ("change", "相对历史"), ("next_check", "下一步验证")]:
            parts.append(f'<p><b>{label}：</b>{esc(signal[key])}</p>')
        parts.append(refs(signal["source_ids"]) + '</article>')
    if not ep["signals"]:
        parts.append('<p>本次没有足够证据形成新的信号。</p>')
    parts.append('</section>')
    if not structured:
        parts.append('<section><h2>需要我做什么</h2>')
    for action in ([] if structured else ep["actions"]):
        parts.append(f'<article><h3>{esc(action["priority"])} · {esc(action["title"])}</h3>'
                     + paras(action["detail"]) + f'<p>期限：{esc(action["deadline"])}</p>' + refs(action["source_ids"]) + '</article>')
    if not structured and not ep["actions"]:
        parts.append('<p>没有需要立即处理的事项。</p>')
    if not structured:
        parts.append('</section>')
    parts.append('<section><h2>覆盖范围与降噪</h2>')
    parts.append('<p>检索状态：' + ('本次范围已完整翻页' if ep["coverage"]["complete"] else '覆盖不完整') + '</p>')
    for account in ([] if structured else ep["coverage"]["accounts"]):
        parts.append(f'<h3>{esc(account["email"])} · {account["count"]} 封</h3><table><tr><th>分类</th><th>数量</th></tr>')
        for category, count in account["categories"].items():
            parts.append(f'<tr><td>{esc(category)}</td><td>{count}</td></tr>')
        parts.append('</table>')
    for note in ep["coverage"].get("notes", []):
        parts.append(f'<p>{esc(note)}</p>')
    parts.append(paras(ep.get("noise_summary", "")) + '</section><section><h2>口播稿与章节</h2>')
    chapters = manifest.get("chapters", [])
    for i, segment in enumerate(ep["segments"]):
        stamp = ""
        if chapters:
            m, s = divmod(int(chapters[i]["start_seconds"]), 60)
            stamp = f"{m:02d}:{s:02d} · "
        parts.append(f'<details><summary>{stamp}{esc(segment["title"])}</summary>' + paras(segment["text"]) + refs(segment["source_ids"]) + '</details>')
    parts.append('</section><section><h2>来源与版本</h2>')
    for source in ep["sources"]:
        parts.append(f'<p><a href="{esc(source["url"])}">{esc(source["title"])}</a><br><small>'
                     f'{esc(source["origin"])} · {esc(source["published_at"])} · {esc(source["access"])}</small></p>')
    parts.append('</section>' + ('</details>' if structured else '') + '<footer>音频在本机合成。内容由上游编辑提供；本工具检查结构与引用关系，不独立验证事实。</footer>')
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer"><title>''' + esc(ep["title"]) + '''</title><style>
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#f6f5f0;color:#213234;font:17px/1.85 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}main{max-width:880px;margin:0 auto;padding:48px 24px 64px}h1{font-size:36px;line-height:1.35;letter-spacing:-.5px}h2{font-size:24px;margin:0 0 18px}h3{font-size:19px;line-height:1.6}p{margin:12px 0}header{padding:0 4px 24px}.eyebrow{color:#53716a;font-size:14px;letter-spacing:2px}.meta,small,footer{font-size:13px;color:#667976}section{background:white;border:1px solid #dfe7e1;border-radius:18px;padding:28px;margin:22px 0}article+article{border-top:1px solid #e6ece8;margin-top:22px;padding-top:12px}a{color:#176b59;text-decoration-thickness:1px;text-underline-offset:3px;overflow-wrap:anywhere}.sources{font-size:13px;color:#667976}.player{background:#e6f0e8}audio{display:block;width:100%;margin:18px 0}table{border-collapse:collapse;width:100%;font-size:15px}th,td{border-bottom:1px solid #e3e9e5;padding:7px;text-align:left}summary{cursor:pointer;font-weight:600;padding:12px 0}details{border-bottom:1px solid #e3e9e5}.notice{padding:16px;background:#fff2d8;border-radius:12px}footer{padding:12px}@media(max-width:600px){main{padding:24px 16px}h1{font-size:29px}section{padding:20px}body{font-size:16px}}
</style><main>''' + "\n".join(parts) + '</main></html>'


def render(episode_path, config, text_only=False, output_dir=None):
    episode_path = Path(episode_path)
    ep = json.loads(episode_path.read_text(encoding="utf-8"))
    validate(ep)
    require(isinstance(config, dict), "Configuration must be an object")
    editorial_config = config.get("editorial", {})
    require(isinstance(editorial_config, dict), "Editorial configuration must be an object")
    minimum_version = editorial_config.get("pipeline_version", 2)
    if editorial_config.get("required"):
        require(ep.get("editorial", {}).get("version", 0) >= minimum_version,
                f"Current config requires editorial version {minimum_version}")
    editorial_result = None
    if ep.get("editorial") or editorial_config.get("required"):
        checked = subprocess.run([sys.executable, str(ROOT / "scripts/check_editorial.py"),
                                  str(episode_path), "--legacy-audit"],
                                 capture_output=True, text=True, timeout=30)
        require(checked.returncode == 0,
                "Editorial check failed; revise before rendering: " + checked.stdout[-2500:] + checked.stderr[-500:])
        editorial_result = json.loads(checked.stdout)
        require(editorial_result.get("episode_sha256") == episode_hash(ep),
                "Episode changed during editorial check; retry with a stable input")
    require(isinstance(config.get("voice"), str) and config["voice"].strip(), "Invalid voice")
    require(type(config.get("speaking_rate")) is int and 80 <= config["speaking_rate"] <= 300,
            "Invalid speaking_rate")
    require(config.get("speech_engine", "macos") == "macos", "Unsupported speech engine")
    fingerprint = hashlib.sha256(json.dumps(
        {"episode": ep, "config": config, "renderer": VERSION, "text_only": bool(text_only)},
        ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    outdir = Path(output_dir) if output_dir is not None else episode_path.parent
    outdir.mkdir(parents=True, exist_ok=True)
    with safe_file(outdir, ".render.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        manifest_path = safe_file(outdir, "manifest.json")
        if manifest_path.exists():
            try:
                old = json.loads(manifest_path.read_text(encoding="utf-8"))
                wanted_status = "text_only" if text_only else "ready"
                if old.get("fingerprint") == fingerprint and old.get("audio_status") == wanted_status:
                    checks = old.get("file_hashes", {})
                    expected = {"episode.json", "index.html", "transcript.txt"}
                    if editorial_result:
                        expected.add("editorial_check.json")
                    if not text_only:
                        expected.add(old.get("audio_file", ""))
                    if expected <= checks.keys() and all(
                            safe_file(outdir, name).is_file() and file_hash(safe_file(outdir, name)) == digest
                            for name, digest in checks.items()):
                        return old, 0
            except (ValueError, TypeError, KeyError, AttributeError, OSError):
                pass  # A damaged cache is rebuilt, never treated as a completed run.
        # Invalidate prior completion receipts before replacing any delivered file.
        atomic_text(manifest_path, json.dumps({"version": VERSION, "fingerprint": fingerprint,
                                             "audio_status": "processing"}) + "\n")
        mobile_receipt = safe_file(outdir, "mobile_audio.json")
        if mobile_receipt.exists():
            atomic_text(mobile_receipt, json.dumps({"version": 1, "status": "stale",
                                                   "render_fingerprint": fingerprint,
                                                   "reason": "Render changed; export MP3 again"}) + "\n")
        transcript = "\n\n".join(segment["text"] for segment in ep["segments"]) + "\n"
        atomic_text(safe_file(outdir, "episode.json"), json.dumps(ep, ensure_ascii=False, indent=2) + "\n")
        atomic_text(safe_file(outdir, "transcript.txt"), transcript)
        manifest = {"version": VERSION, "fingerprint": fingerprint, "title": ep["title"],
                    "episode_sha256": episode_hash(ep),
                    "created_at": datetime.now().astimezone().isoformat(), "audio_status": "text_only",
                    "speech_engine": "macos", "voice": config["voice"],
                    "speaking_rate": config["speaking_rate"], "text_only": bool(text_only)}
        if editorial_result:
            manifest["editorial_status"] = editorial_result["status"]
            manifest["editorial_episode_sha256"] = editorial_result["episode_sha256"]
            atomic_text(safe_file(outdir, "editorial_check.json"),
                        json.dumps(editorial_result, ensure_ascii=False, indent=2) + "\n")
        exit_code = 0
        if not text_only:
            try:
                with tempfile.TemporaryDirectory(prefix=".audio-", dir=outdir) as tmp:
                    sound, duration, chapters = synthesize(ep, config, Path(tmp))
                    filename = f"episode-{fingerprint[:12]}.m4a"
                    os.replace(sound, safe_file(outdir, filename))
                    manifest.update(audio_status="ready", audio_file=filename,
                                    duration_seconds=round(duration, 3), chapters=chapters)
            except (ValueError, OSError, EOFError, wave.Error, subprocess.SubprocessError) as error:
                manifest.update(audio_status="failed", error=str(error))
                exit_code = 1
        atomic_text(safe_file(outdir, "index.html"), render_html(ep, manifest))
        names = ["episode.json", "index.html", "transcript.txt"]
        if editorial_result:
            names.append("editorial_check.json")
        if manifest["audio_status"] == "ready":
            names.append(manifest["audio_file"])
        manifest["file_hashes"] = {name: file_hash(safe_file(outdir, name)) for name in names}
        # This is the completion receipt; consumers must verify its hashes.
        atomic_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        return manifest, exit_code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode", type=Path)
    parser.add_argument("--config", type=Path, default=ROOT / "config.example.json")
    parser.add_argument("--output", type=Path, help="Output directory (default: alongside episode)")
    parser.add_argument("--text-only", action="store_true")
    args = parser.parse_args()
    try:
        manifest, status = render(args.episode.resolve(), json.loads(args.config.read_text(encoding="utf-8")),
                                  args.text_only, args.output)
    except (ValueError, KeyError, TypeError, AttributeError, OSError, subprocess.SubprocessError) as error:
        parser.exit(2, f"Cannot render episode: {error}\n")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return status


if __name__ == "__main__":
    sys.exit(main())
