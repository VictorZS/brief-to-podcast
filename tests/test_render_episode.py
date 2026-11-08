from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import wave

from helpers import config, episode, fake_synthesis, renderer, write_episode


class ValidationTests(unittest.TestCase):
    def test_unknown_sources_and_mismatched_counts_are_rejected(self):
        data = episode()
        data["segments"][0]["source_ids"] = ["invented"]
        with self.assertRaisesRegex(ValueError, "Unknown source"):
            renderer.validate(data)
        data = episode()
        data["coverage"]["accounts"][0]["count"] = 2
        with self.assertRaisesRegex(ValueError, "counts do not match"):
            renderer.validate(data)

    def test_naive_time_and_unsafe_source_urls_are_rejected(self):
        data = episode()
        data["window"]["start"] = "2026-01-01T08:00:00"
        with self.assertRaises(ValueError):
            renderer.validate(data)
        for url in ("javascript:alert(1)", "http://example.com", "https://user:pass@example.com"):
            with self.subTest(url=url):
                data = episode()
                data["sources"][0]["url"] = url
                with self.assertRaises(ValueError):
                    renderer.validate(data)

    def test_speech_commands_and_urls_are_rejected(self):
        for text in ("Read this [[rate 999]]", "Visit https://example.com now"):
            with self.subTest(text=text):
                data = episode()
                data["segments"][0]["text"] = text
                with self.assertRaisesRegex(ValueError, "Spoken text"):
                    renderer.validate(data)

    def test_html_escapes_untrusted_text(self):
        data = episode()
        data["overview"] = '<script>alert("demo")</script>'
        data["sources"][0]["title"] = '<img src=x onerror="alert(1)">'
        result = renderer.render_html(data, {"audio_status": "failed", "error": "Audio unavailable"})
        self.assertNotIn("<script>", result)
        self.assertNotIn("<img src=x", result)
        self.assertIn("&lt;script&gt;", result)
        self.assertNotIn("<audio", result)


class WaveValidationTests(unittest.TestCase):
    def test_empty_and_silent_audio_are_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audio.wav"
            for frames in (b"", b"\0" * 44100):
                with self.subTest(size=len(frames)):
                    with wave.open(str(path), "wb") as output:
                        output.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
                        output.writeframes(frames)
                    with self.assertRaises(ValueError):
                        renderer.check_wave(path)

    def test_header_duration_does_not_hide_truncated_pcm(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "truncated.wav"
            with wave.open(str(path), "wb") as output:
                output.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
                output.writeframes(struct.pack("<h", 1000) * 22050)
            path.write_bytes(path.read_bytes()[:200])
            with self.assertRaises(ValueError):
                renderer.check_wave(path)


class RenderTests(unittest.TestCase):
    def test_concurrent_renders_share_one_consistent_output_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_episode(root)
            output = root / "output"
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: renderer.render(path, config(), text_only=True,
                                                                 output_dir=output), range(2)))
            self.assertEqual(results[0], results[1])
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["audio_status"], "text_only")
            for name, digest in manifest["file_hashes"].items():
                self.assertEqual(renderer.file_hash(output / name), digest)

    def test_output_directory_keeps_input_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_episode(root)
            before = path.read_bytes()
            out = root / "output"
            manifest, code = renderer.render(path, config(), text_only=True, output_dir=out)
            self.assertEqual(code, 0)
            self.assertEqual(manifest["audio_status"], "text_only")
            self.assertEqual(path.read_bytes(), before)
            self.assertFalse((root / "manifest.json").exists())
            self.assertEqual(json.loads((out / "episode.json").read_text()), episode())
            for name, digest in manifest["file_hashes"].items():
                self.assertEqual(renderer.file_hash(out / name), digest)

    def test_cache_reuses_verified_audio_but_rebuilds_damaged_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_episode(root)
            with patch.object(renderer, "synthesize", side_effect=fake_synthesis) as synth:
                first, code = renderer.render(path, config())
                second, code = renderer.render(path, config())
                self.assertEqual(code, 0)
                self.assertEqual(first, second)
                self.assertEqual(synth.call_count, 1)
                (root / first["audio_file"]).write_bytes(b"damaged")
                third, code = renderer.render(path, config())
                self.assertEqual(code, 0)
                self.assertEqual(synth.call_count, 2)
                self.assertEqual(renderer.file_hash(root / third["audio_file"]),
                                 third["file_hashes"][third["audio_file"]])

    def test_text_only_after_audio_does_not_return_cached_ready_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_episode(root)
            with patch.object(renderer, "synthesize", side_effect=fake_synthesis):
                ready, _ = renderer.render(path, config())
            with patch.object(renderer, "synthesize") as synth:
                text, code = renderer.render(path, config(), text_only=True)
                synth.assert_not_called()
            self.assertEqual(code, 0)
            self.assertEqual(text["audio_status"], "text_only")
            self.assertNotEqual(ready["fingerprint"], text["fingerprint"])
            self.assertNotIn("audio_file", text)
            self.assertNotIn("<audio", (root / "index.html").read_text())

    def test_failed_new_episode_never_links_previous_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_episode(root)
            with patch.object(renderer, "synthesize", side_effect=fake_synthesis):
                ready, _ = renderer.render(path, config())
            revised = episode()
            revised["title"] = "A different fictional episode"
            write_episode(root, revised)
            with patch.object(renderer, "synthesize", side_effect=ValueError("empty audio")):
                failed, code = renderer.render(path, config())
            self.assertEqual(code, 1)
            self.assertEqual(failed["audio_status"], "failed")
            self.assertNotIn("audio_file", failed)
            self.assertNotIn(ready["audio_file"], (root / "index.html").read_text())
            self.assertNotIn("<audio", (root / "index.html").read_text())
            self.assertTrue((root / "transcript.txt").is_file())

    def test_manifest_is_written_after_referenced_outputs(self):
        original = renderer.atomic_text
        observations = []

        def observe(path, text):
            if path.name == "manifest.json":
                data = json.loads(text)
                if data["audio_status"] != "processing":
                    observations.append(all((path.parent / name).is_file() and
                                            renderer.file_hash(path.parent / name) == digest
                                            for name, digest in data["file_hashes"].items()))
            return original(path, text)

        with tempfile.TemporaryDirectory() as tmp:
            path = write_episode(Path(tmp))
            with patch.object(renderer, "atomic_text", side_effect=observe):
                renderer.render(path, config(), text_only=True)
        self.assertEqual(observations, [True])


if __name__ == "__main__":
    unittest.main()
