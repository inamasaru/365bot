"""Unit tests for the B2B AI pipeline modules."""

from __future__ import annotations

import sys
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collector.run import run as collector_run
from kpi.run import run as kpi_run
from generator.run import _sanitize, _template_copy, _render_html


class TestCollector:
    def test_creates_leads_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            (base_dir / "data").mkdir()
            collector_run(base_dir)
            leads_file = base_dir / "data" / "leads.csv"
            assert leads_file.exists()
            content = leads_file.read_text()
            assert "company" in content.lower() or "email" in content.lower()


class TestKpi:
    def test_creates_decision_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            data_dir = base_dir / "data"
            data_dir.mkdir()
            reports_dir = base_dir / "reports"
            reports_dir.mkdir()

            leads_csv = data_dir / "leads.csv"
            leads_csv.write_text("company,email,cost\nTest Inc,test@example.com,100000\n")

            kpi_run(base_dir)

            decision_file = reports_dir / "decision.json"
            assert decision_file.exists()


class TestGenerator:
    def test_sanitize_removes_banned_words(self):
        text = "これは必ず成功します！絶対に効果があります。100%保証！"
        result = _sanitize(text)
        assert "必ず" not in result
        assert "絶対" not in result
        assert "100%" not in result

    def test_template_copy_returns_required_keys(self):
        copy = _template_copy()
        assert "headline" in copy
        assert "subheadline" in copy
        assert "cta" in copy

    def test_render_html_produces_valid_html(self):
        copy = _template_copy()
        html = _render_html(copy)
        assert "<!doctype html>" in html.lower()
        assert copy["headline"] in html
        assert copy["cta"] in html
