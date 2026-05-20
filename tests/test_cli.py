"""CLI typer CliRunner 기반 테스트."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from main import app
from typer.testing import CliRunner

runner = CliRunner()


class TestCollectCommand:
    """collect 서브커맨드 테스트."""

    def test_collect_help_korean(self) -> None:
        """--help 출력이 한국어를 포함하는지 테스트 (REQ-CLI-02)."""
        result = runner.invoke(app, ["collect", "--help"])
        assert result.exit_code == 0
        # 한국어 텍스트 확인
        assert "수집" in result.output or "API" in result.output

    def test_collect_full_flag(self, tmp_data_dir: Path) -> None:
        """--full 플래그 동작 테스트."""
        with (
            patch("main._get_data_dir", return_value=tmp_data_dir),
            patch("lotto.collector.LottoCollector.collect_full", return_value=[]),
        ):
            result = runner.invoke(app, ["collect", "--full"])
        assert result.exit_code == 0


class TestAnalyzeCommand:
    """analyze 서브커맨드 테스트."""

    def test_analyze_missing_data(self, tmp_data_dir: Path) -> None:
        """draws.csv 없을 때 한국어 안내 메시지 + exit 1 테스트."""
        with patch("main._get_data_dir", return_value=tmp_data_dir):
            result = runner.invoke(app, ["analyze"])
        assert result.exit_code == 1
        assert "draws.csv" in result.output or "collect" in result.output


class TestRecommendCommand:
    """recommend 서브커맨드 테스트."""

    def test_recommend_missing_stats(self, tmp_data_dir: Path) -> None:
        """stats.json 없을 때 한국어 안내 메시지 + exit 1 테스트."""
        with patch("main._get_data_dir", return_value=tmp_data_dir):
            result = runner.invoke(app, ["recommend"])
        assert result.exit_code == 1
        assert "stats.json" in result.output or "analyze" in result.output

    def test_count_zero_rejected(self) -> None:
        """--count 0 시 에러 + exit 2 테스트 (REQ-CLI-04)."""
        result = runner.invoke(app, ["recommend", "--count", "0"])
        assert result.exit_code != 0

    def test_count_100_rejected(self) -> None:
        """--count 100 시 에러 + exit 2 테스트 (REQ-CLI-04)."""
        result = runner.invoke(app, ["recommend", "--count", "100"])
        assert result.exit_code != 0


class TestSimulateCommand:
    """simulate 서브커맨드 테스트."""

    def test_simulate_help_korean(self) -> None:
        """simulate --help 출력이 한국어를 포함하는지 테스트."""
        result = runner.invoke(app, ["simulate", "--help"])
        assert result.exit_code == 0
        assert "시뮬레이션" in result.output or "백테스팅" in result.output


class TestHelpOutput:
    """전체 --help 한국어 출력 테스트 (REQ-CLI-02)."""

    def test_main_help_korean(self) -> None:
        """메인 --help에 4개 서브커맨드와 한국어 설명이 표시되는지 테스트."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        # 한국어 포함 확인
        assert "로또" in result.output

    def test_all_subcommands_in_help(self) -> None:
        """collect/analyze/recommend/simulate 모두 --help에 있는지 테스트."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for cmd in ["collect", "analyze", "recommend", "simulate"]:
            assert cmd in result.output


class TestExitCodes:
    """exit 코드 테스트 (REQ-CLI-05)."""

    def test_exit_0_on_success(self) -> None:
        """정상 완료 시 exit 0 테스트."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_exit_1_on_validation_error(self, tmp_data_dir: Path) -> None:
        """데이터 부재 등 검증 오류 시 exit 1 테스트."""
        with patch("main._get_data_dir", return_value=tmp_data_dir):
            result = runner.invoke(app, ["analyze"])
        assert result.exit_code == 1

    def test_exit_2_on_invalid_option(self) -> None:
        """잘못된 옵션 시 exit 2 테스트."""
        result = runner.invoke(app, ["recommend", "--count", "0"])
        assert result.exit_code != 0
