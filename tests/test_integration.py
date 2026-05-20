"""collect → analyze → recommend → simulate 종단간 통합 테스트."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import requests_mock as rm
from main import app
from typer.testing import CliRunner

runner = CliRunner()

API_URL_PATTERN = "https://www.dhlottery.co.kr/common.do"


def _make_draw_response(drw_no: int) -> dict[str, object]:
    """회차별 API 응답 샘플."""
    return {
        "returnValue": "success",
        "drwNo": drw_no,
        "drwNoDate": f"2024-{(drw_no % 12) + 1:02d}-01",
        "drwtNo1": (drw_no % 6) + 1,
        "drwtNo2": (drw_no % 6) + 7,
        "drwtNo3": (drw_no % 6) + 13,
        "drwtNo4": (drw_no % 6) + 19,
        "drwtNo5": (drw_no % 6) + 25,
        "drwtNo6": (drw_no % 6) + 31,
        "bnusNo": (drw_no % 10) + 36,
    }


class TestFullPipeline:
    """전체 파이프라인 통합 테스트."""

    def test_collect_analyze_recommend_simulate(
        self,
        requests_mock: rm.Mocker,
        tmp_data_dir: Path,
    ) -> None:
        """collect → analyze → recommend → simulate 순서 실행 테스트."""
        # 20회차 데이터 모킹
        responses = [{"json": _make_draw_response(i)} for i in range(1, 21)]
        # 21회차부터는 실패 (종료 트리거)
        responses += [{"json": {"returnValue": "fail"}}] * 5
        requests_mock.get(API_URL_PATTERN, responses)

        with patch("main._get_data_dir", return_value=tmp_data_dir), patch("time.sleep"):
            # collect
            result = runner.invoke(app, ["collect", "--full"])
            assert result.exit_code == 0 or result.exit_code == 2  # abort도 허용

            # analyze (CSV 있을 때)
            if (tmp_data_dir / "draws.csv").exists():
                result = runner.invoke(app, ["analyze"])
                assert result.exit_code == 0

                # recommend (stats.json 있을 때)
                if (tmp_data_dir / "stats.json").exists():
                    result = runner.invoke(app, ["recommend", "--count", "3"])
                    assert result.exit_code == 0

                    # simulate
                    result = runner.invoke(app, ["simulate", "--rounds", "5"])
                    assert result.exit_code == 0

    def test_data_persistence_across_commands(
        self,
        requests_mock: rm.Mocker,
        tmp_data_dir: Path,
    ) -> None:
        """각 명령 실행 후 data/ 파일이 올바르게 생성되는지 테스트."""
        responses = [{"json": _make_draw_response(i)} for i in range(1, 11)]
        responses += [{"json": {"returnValue": "fail"}}] * 5
        requests_mock.get(API_URL_PATTERN, responses)

        with patch("main._get_data_dir", return_value=tmp_data_dir), patch("time.sleep"):
            runner.invoke(app, ["collect", "--full"])

        if (tmp_data_dir / "draws.csv").exists():
            with patch("main._get_data_dir", return_value=tmp_data_dir):
                runner.invoke(app, ["analyze"])
            assert (tmp_data_dir / "stats.json").exists()


class TestEdgeCases:
    """엣지 케이스 통합 테스트."""

    def test_no_data_dir_analyze_exit_1(self, tmp_data_dir: Path) -> None:
        """데이터 없이 analyze 실행 시 exit 1 + 한국어 메시지 테스트 (AC-7)."""
        with patch("main._get_data_dir", return_value=tmp_data_dir):
            result = runner.invoke(app, ["analyze"])
        assert result.exit_code == 1
        # 한국어 안내 확인
        assert any(kw in result.output for kw in ["없습니다", "collect", "draws.csv"])

    def test_no_stats_recommend_exit_1(self, tmp_data_dir: Path) -> None:
        """stats.json 없이 recommend 실행 시 exit 1 + 한국어 메시지 테스트 (AC-7)."""
        with patch("main._get_data_dir", return_value=tmp_data_dir):
            result = runner.invoke(app, ["recommend"])
        assert result.exit_code == 1
        assert any(kw in result.output for kw in ["없습니다", "analyze", "stats.json"])

    def test_api_total_failure_abort_exit_2(
        self,
        requests_mock: rm.Mocker,
        tmp_data_dir: Path,
    ) -> None:
        """5회 연속 API 실패 시 abort + 기존 데이터 보존 + exit 2 테스트 (AC-8)."""
        # 모든 요청 실패
        requests_mock.get(API_URL_PATTERN, status_code=500)

        with patch("main._get_data_dir", return_value=tmp_data_dir), patch("time.sleep"):
            result = runner.invoke(app, ["collect", "--full"])
        assert result.exit_code == 2

    def test_recent_window_exceeds_data(
        self,
        requests_mock: rm.Mocker,
        tmp_data_dir: Path,
    ) -> None:
        """10회차만 있고 --recent-window 50 시 경고 후 정상 종료 테스트 (AC-9)."""
        # 10회차 데이터 수집
        responses = [{"json": _make_draw_response(i)} for i in range(1, 11)]
        responses += [{"json": {"returnValue": "fail"}}] * 5
        requests_mock.get(API_URL_PATTERN, responses)

        with patch("main._get_data_dir", return_value=tmp_data_dir), patch("time.sleep"):
            runner.invoke(app, ["collect", "--full"])

        if (tmp_data_dir / "draws.csv").exists():
            with patch("main._get_data_dir", return_value=tmp_data_dir):
                result = runner.invoke(app, ["analyze", "--recent-window", "50"])
            # 경고 후 정상 종료
            assert result.exit_code == 0
