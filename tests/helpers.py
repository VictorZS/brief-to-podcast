"""Synthetic fixtures and imports for offline tests; no account data."""
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_editorial as editorial
import render_episode as renderer


def config():
    return {"voice": "Samantha", "speaking_rate": 165, "speech_engine": "macos",
            "editorial": {"required": True, "pipeline_version": 2}}


def episode():
    """A deliberately fictional v2 brief with one protected qualification."""
    text = "A fictional 12-person trial took 18% longer; this small sample cannot establish a general trend."
    section = {"title": "Fictional trial", "text": text,
               "source_ids": ["s1"], "fact_ids": ["f1"]}
    return {
        "schema_version": 1, "title": "Fictional demonstration",
        "overview": "All facts in this fixture are invented for software testing.",
        "window": {"start": "2026-01-01T08:00:00+00:00", "end": "2026-01-02T08:00:00+00:00"},
        "coverage": {"complete": False, "accounts": [
            {"email": "demo@example.com", "count": 1, "categories": {"newsletter": 1}}],
            "notes": ["Synthetic input; no mailbox was queried."]},
        "sources": [{"id": "s1", "title": "Fictional trial report",
                     "url": "https://example.com/fictional-trial", "origin": "Synthetic fixture",
                     "published_at": "2026-01-01", "access": "full_text"}],
        "sections": [copy.deepcopy(section)], "segments": [copy.deepcopy(section)],
        "signals": [], "actions": [],
        "editorial": {
            "version": 2, "thesis": "A fictional small trial illustrates the need to preserve qualifications.",
            "facts": [{"id": "f1", "text": text, "kind": "observation", "source_ids": ["s1"],
                       "source_family": "fictional-study", "evidence_level": "full_text",
                       "scope": "Twelve fictional participants", "caveat": "Do not generalize a small sample.",
                       "must_preserve": ["12-person", "18%", "cannot establish a general trend"]}],
            "stories": [{"id": "story1", "question": "Can this small sample support a broad conclusion?",
                         "judgment": "The fictional result is limited to this sample.",
                         "mechanism": "A narrow sample can differ from the wider population.",
                         "implication": "Collect a broader comparison before deciding.",
                         "counterargument": "A repeatable effect could remain meaningful in similar settings.",
                         "would_change_mind": "A larger controlled replication would change this assessment.",
                         "fact_ids": ["f1"], "novelty": {"status": "baseline", "reason": "First synthetic fixture."},
                         "priority": {"knowledge_value": 2, "urgency": 0, "reason": "Demonstration only."}}],
            "compression": {"before_chars": len(text) + 30, "after_chars": len(text),
                            "protected_fact_ids": ["f1"], "removed": ["Synthetic filler"], "restored": ["Scope"]},
            "review": {"status": "pass", "reviewer": "Synthetic fixture author",
                       "corrections": [], "remaining_limits": ["Not real research."]},
        },
    }


def write_episode(directory, data=None):
    path = directory / "episode.json"
    path.write_text(json.dumps(data or episode()), encoding="utf-8")
    return path


def fake_synthesis(ep, settings, directory):
    # The real synthesizer validates audio before returning. This mock isolates
    # render/cache behavior; its bytes are intentionally not playable audio.
    audio = directory / "episode.m4a"
    audio.write_bytes(b"synthetic-unit-test-audio")
    return audio, 5.0, [{"title": "Fictional trial", "start_seconds": 0, "duration_seconds": 5}]
