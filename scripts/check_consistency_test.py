#!/usr/bin/env python3
"""Tests for check_consistency.py — validates the validator itself."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import TestCase, main

from check_consistency import (
    CHANGELOG_VERSION_RE,
    SEMVER_RE,
    Finding,
)


class TestSemverRegex(TestCase):
    def test_valid(self):
        for v in ("0.0.0", "1.0.0", "0.1.0", "10.20.30"):
            self.assertIsNotNone(SEMVER_RE.match(v), f"{v} should be valid semver")

    def test_invalid(self):
        for v in ("1", "1.0", "v1.0.0", "1.0.0-beta", "01.0.0"):
            self.assertIsNone(SEMVER_RE.match(v), f"{v} should not be valid semver")


class TestChangelogRegex(TestCase):
    def test_extracts_version(self):
        text = "## [1.2.3] - 2026-02-25\n\n### Added\n- stuff"
        m = CHANGELOG_VERSION_RE.search(text)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "1.2.3")

    def test_no_version(self):
        text = "# Changelog\n\nNo versions yet."
        m = CHANGELOG_VERSION_RE.search(text)
        self.assertIsNone(m)


class TestFinding(TestCase):
    def test_str_format(self):
        f = Finding("CRITICAL", "herald", "Version mismatch", {"a": "1", "b": "2"})
        s = str(f)
        self.assertIn("[CRITICAL]", s)
        self.assertIn("herald", s)
        self.assertIn("a=1", s)

    def test_to_dict(self):
        f = Finding("HIGH", "sigil", "Missing field")
        d = f.to_dict()
        self.assertEqual(d["severity"], "HIGH")
        self.assertEqual(d["plugin"], "sigil")


if __name__ == "__main__":
    main()
