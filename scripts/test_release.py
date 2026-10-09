"""Release decisions must not overwrite releases or hide failed attempts."""

import unittest
from pathlib import Path
from unittest.mock import patch

from release import decide, main, semver


class ReleaseTests(unittest.TestCase):
    def test_published_release_has_no_write_side_effects(self):
        state = (
            "0.15.0",
            "sha",
            "owner/repo",
            Path("notes.md"),
            {"v0.15.0": "sha"},
            False,
        )
        with (
            patch("release.context", return_value=state),
            patch("release.run") as command,
            patch("sys.argv", ["release.py", "publish", "--version-file", "VERSION"]),
        ):
            main()
            command.assert_not_called()

    def test_race_with_external_release_stops_before_image_build(self):
        state = (
            "0.15.0",
            "sha",
            "owner/repo",
            Path("notes.md"),
            {"v0.15.0": "sha"},
            False,
        )
        with (
            patch("release.context", return_value=state),
            patch("release.run") as command,
            patch("sys.argv", ["release.py", "tag", "--version-file", "VERSION"]),
        ):
            with self.assertRaisesRegex(ValueError, "stop before rebuilding"):
                main()
            command.assert_not_called()

    def test_prerelease_does_not_set_latest(self):
        state = ("0.15.0-beta.1", "sha", "owner/repo", Path("notes.md"), {}, True)
        with (
            patch("release.context", return_value=state),
            patch(
                "release.run",
                side_effect=[
                    "",
                    "",
                    '{"draft":false,"prerelease":true,"html_url":"https://example.test"}',
                ],
            ) as command,
            patch("sys.argv", ["release.py", "publish", "--version-file", "VERSION"]),
        ):
            main()
            self.assertIn("sha=sha", command.call_args_list[0].args)
            self.assertIn("--verify-tag", command.call_args_list[1].args)
            self.assertIn("--prerelease", command.call_args_list[1].args)
            self.assertIn("--latest=false", command.call_args_list[1].args)

    def test_new_version(self):
        self.assertTrue(decide("0.15.0", "new", {"v0.14.0": "old"}, []))

    def test_existing_release_skips_even_on_a_later_docs_commit(self):
        published = [{"tag_name": "v0.14.0", "draft": False, "prerelease": False}]
        self.assertFalse(decide("0.14.0", "new", {"v0.14.0": "old"}, published))

    def test_retry_after_tag_creation(self):
        self.assertTrue(decide("0.15.0", "same", {"v0.15.0": "same"}, []))

    def test_tag_on_another_commit_fails(self):
        with self.assertRaisesRegex(ValueError, "another commit"):
            decide("0.15.0", "new", {"v0.15.0": "old"}, [])

    def test_downgrade_fails(self):
        with self.assertRaisesRegex(ValueError, "newer tag"):
            decide("0.14.1", "new", {"v0.15.0": "old"}, [])

    def test_draft_is_not_silently_treated_as_published(self):
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            decide(
                "0.15.0",
                "sha",
                {"v0.15.0": "sha"},
                [{"tag_name": "v0.15.0", "draft": True, "prerelease": False}],
            )

    def test_semver_order_and_invalid_values(self):
        self.assertLess(semver("0.15.0-beta.2"), semver("0.15.0-beta.10"))
        self.assertLess(semver("0.15.0-beta.10"), semver("0.15.0"))
        for version in [
            "v1.0.0",
            "01.0.0",
            "1.0.0-01",
            "1.0.0-a..b",
            "1.0.0\nother",
            "1.0.0+build",
        ]:
            with self.assertRaises(ValueError):
                semver(version)


if __name__ == "__main__":
    unittest.main()
