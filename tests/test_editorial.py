import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from helpers import ROOT, config, editorial, episode, renderer, write_episode


class EditorialTests(unittest.TestCase):
    def test_synthetic_example_passes_and_discloses_partial_coverage(self):
        data = json.loads((ROOT / "examples/episode.json").read_text())
        renderer.validate(data)
        self.assertEqual(editorial.check(data)["status"], "pass")
        self.assertFalse(data["coverage"]["complete"])
        self.assertEqual(data["briefing"]["notification_review"]["status"], "partial")

    def test_compression_cannot_drop_the_limiting_condition(self):
        data = episode()
        self.assertEqual(editorial.check(data)["status"], "pass")
        data["sections"][0]["text"] = "The fictional 12-person trial took 18% longer in all situations."
        result = editorial.check(data)
        self.assertEqual(result["status"], "revise")
        self.assertTrue(any("cannot establish a general trend" in e for e in result["errors"]))

    def test_snippets_and_missing_source_links_cannot_support_a_story(self):
        data = episode()
        data["editorial"]["facts"][0]["evidence_level"] = "snippet"
        self.assertTrue(any("snippet-only" in e for e in editorial.check(data)["errors"]))
        data = episode()
        data["segments"][0]["source_ids"] = []
        self.assertTrue(any("fact/source mismatch" in e for e in editorial.check(data)["errors"]))

    def test_repeated_script_and_stale_compression_metrics_are_rejected(self):
        data = episode()
        data["segments"].append(copy.deepcopy(data["segments"][0]))
        errors = editorial.check(data)["errors"]
        self.assertTrue(any("Repeated" in e for e in errors))
        self.assertTrue(any("after_chars" in e for e in errors))

    def test_a_quiet_day_can_explicitly_have_no_story(self):
        data = episode()
        data["editorial"]["stories"] = []
        self.assertEqual(editorial.check(data)["status"], "revise")
        data["editorial"]["no_story_reason"] = "There is insufficient new evidence to develop a useful story."
        self.assertEqual(editorial.check(data)["status"], "pass")

    def test_renderer_rechecks_editorial_before_audio(self):
        data = episode()
        data["sections"][0]["text"] = "The important scope was removed."
        with tempfile.TemporaryDirectory() as tmp:
            path = write_episode(Path(tmp), data)
            with patch.object(renderer, "synthesize") as synth:
                with self.assertRaisesRegex(ValueError, "Editorial check failed"):
                    renderer.render(path, config())
                synth.assert_not_called()

    def test_configuration_can_require_v3_before_synthesis(self):
        settings = config()
        settings["editorial"]["pipeline_version"] = 3
        with tempfile.TemporaryDirectory() as tmp:
            path = write_episode(Path(tmp))
            with patch.object(renderer, "synthesize") as synth:
                with self.assertRaisesRegex(ValueError, "requires editorial version 3"):
                    renderer.render(path, settings)
                synth.assert_not_called()

    def test_editorial_receipt_must_certify_the_loaded_snapshot(self):
        result = editorial.check(episode())
        result["episode_sha256"] = "0" * 64
        completed = subprocess.CompletedProcess([], 0, stdout=json.dumps(result), stderr="")
        with tempfile.TemporaryDirectory() as tmp:
            path = write_episode(Path(tmp))
            with patch.object(renderer.subprocess, "run", return_value=completed), \
                    patch.object(renderer, "synthesize") as synth:
                with self.assertRaisesRegex(ValueError, "changed during editorial check"):
                    renderer.render(path, config())
                synth.assert_not_called()

    def test_three_part_outline_and_notification_coverage_cannot_overclaim(self):
        data = json.loads((ROOT / "examples/episode.json").read_text())
        data["segments"][0]["part"] = "insights"
        self.assertTrue(any("expected inbox" in e for e in editorial.check(data)["errors"]))
        data = json.loads((ROOT / "examples/episode.json").read_text())
        data["briefing"]["notification_review"]["status"] = "complete"
        errors = editorial.check(data)["errors"]
        self.assertTrue(any("full current-message coverage" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
