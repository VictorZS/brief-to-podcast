#!/usr/bin/env python3
"""Check editorial evidence links and compression invariants, never semantic truth."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys


def spoken_text(ep):
    return "\n\n".join(s.get("text", "") for s in ep.get("segments", []))


def fingerprint(ep):
    return hashlib.sha256(json.dumps(ep, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def check_briefing(ep, need):
    """Check the three-part reading/listening contract, including review coverage."""
    order = ["inbox", "insights", "notifications"]
    for name in ("sections", "segments"):
        observed = []
        for item in ep.get(name, []):
            part = item.get("part")
            need(part in order, f"{name}: missing or invalid part")
            if not observed or part != observed[-1]:
                observed.append(part)
        need(observed == order, f"{name}: expected inbox → insights → notifications exactly once")
    briefing = ep.get("briefing", {})
    total = sum(a["count"] for a in ep.get("coverage", {}).get("accounts", []))
    need(type(briefing.get("total_count")) is int and briefing["total_count"] == total,
         "briefing.total_count must match the verified mailbox counts")
    review = briefing.get("notification_review", {})
    need(review.get("status") in {"complete", "partial"}, "Missing notification review status")
    count = review.get("reviewed_current_count")
    need(type(count) is int and 0 <= count <= total, "Invalid notification reviewed_current_count")
    need(review.get("history_status") in {"complete", "partial", "not_run"}, "Missing historical notice review status")
    need(isinstance(review.get("scope_note"), str) and bool(review["scope_note"].strip()), "Missing notification scope note")
    if review.get("status") == "complete":
        need(ep.get("coverage", {}).get("complete") is True and count == total,
             "Complete notification review requires full current-message coverage")
        need(review.get("history_status") == "complete", "Complete notification review requires historical reminder reconciliation")
    stories = {s["id"] for s in ep.get("editorial", {}).get("stories", [])}
    questions = briefing.get("research_questions", [])
    need(isinstance(questions, list) and len(questions) <= 2, "At most two research questions")
    question_ids = {q.get("id") for q in questions}
    need(len(question_ids) == len(questions) and all(question_ids), "Missing or duplicate research question IDs")
    sources = {s["id"] for s in ep.get("sources", [])}
    for q in questions:
        for field in ("question", "why_it_matters", "starting_point"):
            need(isinstance(q.get(field), str) and len(q[field].strip()) >= 8, f"Research question missing {field}")
        need(q.get("story_id") in stories, "Research question must follow a developed insight")
        need(bool(q.get("source_ids")) and set(q["source_ids"]) <= sources, "Research question has missing/unknown sources")
    if stories:
        need(bool(questions), "Developed insights need a concrete optional research direction")
    spoken_questions = set()
    for segment in ep.get("segments", []):
        refs = set(segment.get("research_question_ids", []))
        need(refs <= question_ids, "Unknown spoken research question")
        if refs:
            need(segment.get("part") == "insights", "Research questions belong in insights")
        spoken_questions |= refs
    need(question_ids <= spoken_questions, "Research directions missing from the spoken insights")
    for action in ep.get("actions", []):
        need(action.get("category") in {"renewal", "travel", "billing", "delivery", "account", "work", "optional", "other"},
             "Notification missing category")
        need(action.get("status") in {"needs_action", "upcoming", "updated", "resolved", "information", "unverified"},
             "Notification missing status")
        for field in ("change", "next_step"):
            need(isinstance(action.get(field), str) and bool(action[field].strip()), f"Notification missing {field}")
        need(bool(action.get("source_ids")), "Notification requires a source")


def check(ep):
    errors, warnings = [], []
    def need(ok, message):
        if not ok:
            errors.append(message)
    ed = ep.get("editorial", {})
    need(ed.get("version") in {2, 3}, "editorial.version must be 2 or 3")
    if ed.get("version") == 3:
        check_briefing(ep, need)
    need(isinstance(ed.get("thesis"), str) and len(ed.get("thesis", "").strip()) >= 12,
         "Missing a concrete editorial thesis")
    sources = {s["id"] for s in ep.get("sources", [])}
    facts = ed.get("facts", [])
    by_id = {f.get("id"): f for f in facts}
    need(len(by_id) == len(facts) and all(isinstance(i, str) and bool(i.strip()) for i in by_id),
         "Missing or duplicate fact IDs")
    for f in facts:
        key = f.get("id", "?")
        for field in ("text", "source_family", "scope", "caveat"):
            need(isinstance(f.get(field), str) and bool(f[field].strip()), f"{key}: missing {field}")
        need(f.get("kind") in {"observation", "survey", "forecast", "context", "deadline"}, f"{key}: invalid kind")
        need(f.get("evidence_level") in {"full_text", "email_body", "abstract", "snippet"}, f"{key}: invalid evidence_level")
        refs = f.get("source_ids", [])
        need(bool(refs) and set(refs) <= sources, f"{key}: unknown or missing source_ids")
    stories = ed.get("stories", [])
    story_ids = [story.get("id") for story in stories]
    need(all(isinstance(key, str) and key.strip() for key in story_ids)
         and len(set(story_ids)) == len(story_ids), "Missing or duplicate story IDs")
    limit = 1 if ed.get("version") == 3 else 2
    need(len(stories) <= limit, f"At most {limit} developed stories")
    if not stories:
        need(isinstance(ed.get("no_story_reason"), str) and len(ed["no_story_reason"].strip()) >= 12,
             "No story requires an explicit evidence/coverage reason; do not invent a thesis to fill space")
    story_facts = set()
    for story in stories:
        key = story.get("id", "?")
        for field in ("question", "judgment", "mechanism", "implication", "counterargument", "would_change_mind"):
            value = story.get(field, "")
            need(isinstance(value, str) and len(value.strip()) >= 8, f"{key}: missing {field}")
        ids = set(story.get("fact_ids", []))
        need(bool(ids) and ids <= by_id.keys(), f"{key}: unknown or missing fact_ids")
        story_facts |= ids
        need(all(by_id[i].get("evidence_level") != "snippet" for i in ids if i in by_id),
             f"{key}: snippet-only material cannot support the story")
        priority = story.get("priority", {})
        for axis in ("knowledge_value", "urgency"):
            need(type(priority.get(axis)) is int and 0 <= priority[axis] <= 3, f"{key}: invalid {axis}")
        need(bool(priority.get("reason")), f"{key}: missing selection reason")
        novelty = story.get("novelty", {})
        need(novelty.get("status") in {"baseline", "continued", "changed"} and bool(novelty.get("reason")),
             f"{key}: missing novelty baseline")
        need(story.get("judgment", "").strip() != story.get("mechanism", "").strip(),
             f"{key}: judgment merely repeats mechanism")
    represented, written = set(), set()
    for category in ("sections", "segments"):
        for item in ep.get(category, []):
            need(isinstance(item.get("fact_ids"), list), f"{item.get('title')}: missing fact_ids")
            ids = set(item.get("fact_ids", []))
            need(ids <= by_id.keys(), f"{item.get('title')}: unknown fact_ids")
            required_sources = {s for i in ids if i in by_id for s in by_id[i].get("source_ids", [])}
            need(required_sources <= set(item.get("source_ids", [])), f"{item.get('title')}: fact/source mismatch")
            represented |= ids
            if category == "sections":
                written |= ids
    need(story_facts <= represented, "Story evidence is missing from the delivered text")
    compression = ed.get("compression", {})
    protected = set(compression.get("protected_fact_ids", []))
    need((bool(protected) or not facts) and protected <= by_id.keys(), "Missing or invalid protected facts")
    need(protected <= written, "Protected facts must remain in the written report")
    for key in protected & by_id.keys():
        f = by_id[key]
        anchors = f.get("must_preserve", [])
        need(isinstance(anchors, list) and bool(anchors), f"{key}: no preservation anchors")
        # Check only the delivered paragraphs that actually cite this fact.
        body = "\n".join(s["text"] for s in ep.get("sections", []) if key in s.get("fact_ids", [])).casefold()
        for anchor in anchors:
            need(isinstance(anchor, str) and bool(anchor) and anchor.casefold() in body,
                 f"{key}: lost qualifier/number {anchor!r}")
    spoken = spoken_text(ep)
    need(compression.get("after_chars") == len(spoken), "compression.after_chars does not match the actual script")
    need(type(compression.get("before_chars")) is int and compression["before_chars"] > 0,
         "Missing measured initial draft length")
    for field in ("removed", "restored"):
        need(isinstance(compression.get(field), list), f"Missing compression.{field} record")
    sentences = [re.sub(r"\W+", "", s) for s in re.split(r"[。！？.!?\n]", spoken)]
    repeats = [s for s, n in Counter(s for s in sentences if len(s) >= 24).items() if n > 1]
    need(not repeats, "Repeated spoken sentences: " + " / ".join(s[:50] for s in repeats))
    meta = [phrase for phrase in ("对你的播客也是如此", "本项目可先", "好的简报应该", "我们需要逐步校准", "这个播客系统") if phrase in spoken]
    if meta:
        warnings.append("Review self-referential filler: " + " / ".join(meta))
    review = ed.get("review", {})
    need(review.get("status") == "pass", "Editorial self-review has not passed")
    need(bool(review.get("reviewer")) and isinstance(review.get("corrections"), list)
         and isinstance(review.get("remaining_limits"), list), "Missing review provenance/limits")
    family_counts = {s.get("id"): len({by_id[i].get("source_family") for i in s.get("fact_ids", []) if i in by_id}) for s in stories}
    return {"version": ed.get("version"), "status": "pass" if not errors else "revise", "episode_sha256": fingerprint(ep),
            "errors": errors, "warnings": warnings, "metrics": {"spoken_chars": len(spoken),
            "facts": len(facts), "stories": len(stories), "source_families_per_story": family_counts},
            "limits": "Structure, reference and literal-preservation checks only; not an independent factual or subjective quality assessment."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode", type=Path)
    parser.add_argument("--legacy-audit", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--output", type=Path, help="Optional report file; default prints JSON only")
    args = parser.parse_args()
    try:
        ep = json.loads(args.episode.read_text(encoding="utf-8"))
        result = check(ep)
        if args.output:
            # Use a unique temporary file so concurrent checks cannot interleave.
            from render_episode import atomic_text
            atomic_text(args.output, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as error:
        parser.exit(2, f"Cannot check episode: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
