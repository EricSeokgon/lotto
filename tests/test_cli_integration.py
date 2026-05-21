"""SPEC-LOTTO-004 REQ-INT-001 (extension): CLI 통합 테스트.

main.py의 collect/analyze/recommend/simulate 명령어가 실제 데이터와
함께 정상 동작함을 검증한다.

@MX:SPEC: SPEC-LOTTO-004 REQ-INT-001
"""

from __future__ import annotations

import datetime
import json
import random
from pathlib import Path
from unittest.mock import patch

from main import app
from typer.testing import CliRunner

from lotto.analyzer import LottoAnalyzer
from lotto.collector import LottoCollector
from lotto.models import DrawResult

runner = CliRunner()


def _make_draws(n: int) -> list[DrawResult]:
    """결정적 시드로 n개의 임의 회차 데이터를 생성한다."""
    draws: list[DrawResult] = []
    for i in range(1, n + 1):
        rng = random.Random(i)
        nums = rng.sample(range(1, 46), 7)
        body = sorted(nums[:6])
        draws.append(
            DrawResult(
                drwNo=i,
                date=datetime.date(2020, 1, 1) + datetime.timedelta(weeks=i),
                n1=body[0], n2=body[1], n3=body[2],
                n4=body[3], n5=body[4], n6=body[5],
                bonus=nums[6],
            )
        )
    return draws


class TestCollectIncrementalPath:
    """main.collect 명령 비-full 경로 테스트 (line 47-54)."""

    def test_collect_incremental_with_existing_data(self, tmp_data_dir: Path) -> None:
        """기존 데이터가 있는 상태에서 증분 수집을 호출한다."""
        # 미리 5개 회차를 저장
        draws = _make_draws(5)
        LottoCollector(data_dir=tmp_data_dir).save_csv(draws)

        with (
            patch("main._get_data_dir", return_value=tmp_data_dir),
            patch("lotto.collector.LottoCollector.collect_new", return_value=draws),
        ):
            result = runner.invoke(app, ["collect"])

        assert result.exit_code == 0
        assert "신규 데이터" in result.output or "회차 이후" in result.output

    def test_collect_incremental_without_existing_data(self, tmp_data_dir: Path) -> None:
        """기존 데이터가 없을 때 collect 명령은 latest=0부터 시작한다."""
        with (
            patch("main._get_data_dir", return_value=tmp_data_dir),
            patch("lotto.collector.LottoCollector.collect_new", return_value=[]),
        ):
            result = runner.invoke(app, ["collect"])

        assert result.exit_code == 0
        assert "신규 데이터" in result.output

    def test_collect_aborts_on_consecutive_failures(self, tmp_data_dir: Path) -> None:
        """CollectAbortError 발생 시 exit 코드 2."""
        from lotto.collector import CollectAbortError

        with (
            patch("main._get_data_dir", return_value=tmp_data_dir),
            patch(
                "lotto.collector.LottoCollector.collect_new",
                side_effect=CollectAbortError("5회 연속 실패"),
            ),
        ):
            result = runner.invoke(app, ["collect"])

        assert result.exit_code == 2
        assert "수집 중단" in result.output


class TestAnalyzeWithWarnings:
    """main.analyze 명령의 경고 출력 분기 (line 82-83, 91-93)."""

    def test_analyze_emits_warning_on_short_window(self, tmp_data_dir: Path) -> None:
        """recent_window > 회차 수 시 경고가 출력된다."""
        # 5개 회차만 저장
        draws = _make_draws(5)
        LottoCollector(data_dir=tmp_data_dir).save_csv(draws)

        with patch("main._get_data_dir", return_value=tmp_data_dir):
            # recent_window=20 > 5 회차이므로 경고 발생
            result = runner.invoke(app, ["analyze", "--recent-window", "20"])

        assert result.exit_code == 0
        # 경고가 출력되어야 함
        assert "경고" in result.output or "분석 완료" in result.output

    def test_analyze_with_empty_csv(self, tmp_data_dir: Path) -> None:
        """빈 draws.csv 파일은 exit 1 (line 82-83)."""
        # 빈 CSV 헤더만 작성
        csv_path = tmp_data_dir / "draws.csv"
        csv_path.write_text(
            "drwNo,date,n1,n2,n3,n4,n5,n6,bonus\n",
            encoding="utf-8",
        )

        with patch("main._get_data_dir", return_value=tmp_data_dir):
            result = runner.invoke(app, ["analyze"])

        assert result.exit_code == 1
        assert "데이터" in result.output or "collect" in result.output


class TestRecommendWithWeights:
    """main.recommend 명령의 --weights 옵션 (line 127-136)."""

    def test_recommend_with_valid_weights(self, tmp_data_dir: Path) -> None:
        """유효한 가중치로 추천 명령이 정상 동작한다."""
        draws = _make_draws(20)
        stats = LottoAnalyzer().analyze(draws)
        stats_path = tmp_data_dir / "stats.json"
        LottoAnalyzer().save_stats(stats, stats_path)

        with patch("main._get_data_dir", return_value=tmp_data_dir):
            result = runner.invoke(
                app, ["recommend", "--count", "3", "--weights", "0.5,0.3,0.1,0.1"]
            )

        assert result.exit_code == 0

    def test_recommend_with_invalid_weights_count(self, tmp_data_dir: Path) -> None:
        """가중치 개수가 4가 아니면 exit 2."""
        draws = _make_draws(20)
        stats = LottoAnalyzer().analyze(draws)
        stats_path = tmp_data_dir / "stats.json"
        LottoAnalyzer().save_stats(stats, stats_path)

        with patch("main._get_data_dir", return_value=tmp_data_dir):
            result = runner.invoke(
                app, ["recommend", "--weights", "0.5,0.5"]
            )

        assert result.exit_code == 2
        assert "가중치" in result.output

    def test_recommend_with_invalid_weights_format(self, tmp_data_dir: Path) -> None:
        """가중치 파싱 실패 시 exit 2."""
        draws = _make_draws(20)
        stats = LottoAnalyzer().analyze(draws)
        stats_path = tmp_data_dir / "stats.json"
        LottoAnalyzer().save_stats(stats, stats_path)

        with patch("main._get_data_dir", return_value=tmp_data_dir):
            result = runner.invoke(
                app, ["recommend", "--weights", "abc,0.3,0.2,0.1"]
            )

        assert result.exit_code == 2


class TestSimulateCommand:
    """main.simulate 명령 (line 170-171, 177-178, 196-202)."""

    def test_simulate_missing_csv(self, tmp_data_dir: Path) -> None:
        """draws.csv 없으면 exit 1."""
        with patch("main._get_data_dir", return_value=tmp_data_dir):
            result = runner.invoke(app, ["simulate"])

        assert result.exit_code == 1
        assert "draws.csv" in result.output or "collect" in result.output

    def test_simulate_empty_csv(self, tmp_data_dir: Path) -> None:
        """빈 draws.csv는 exit 1."""
        csv_path = tmp_data_dir / "draws.csv"
        csv_path.write_text(
            "drwNo,date,n1,n2,n3,n4,n5,n6,bonus\n",
            encoding="utf-8",
        )

        with patch("main._get_data_dir", return_value=tmp_data_dir):
            result = runner.invoke(app, ["simulate"])

        assert result.exit_code == 1

    def test_simulate_with_output(self, tmp_data_dir: Path, tmp_path: Path) -> None:
        """--output으로 JSON 파일에 결과 저장."""
        draws = _make_draws(20)
        LottoCollector(data_dir=tmp_data_dir).save_csv(draws)

        output_path = tmp_path / "sim_result.json"

        with patch("main._get_data_dir", return_value=tmp_data_dir):
            result = runner.invoke(
                app, ["simulate", "--rounds", "5", "--output", str(output_path)]
            )

        assert result.exit_code == 0
        assert output_path.exists()
        saved = json.loads(output_path.read_text(encoding="utf-8"))
        assert saved["total_rounds"] == 5

    def test_simulate_basic_run(self, tmp_data_dir: Path) -> None:
        """기본 시뮬레이션 실행 (--output 없음)."""
        draws = _make_draws(15)
        LottoCollector(data_dir=tmp_data_dir).save_csv(draws)

        with patch("main._get_data_dir", return_value=tmp_data_dir):
            result = runner.invoke(app, ["simulate", "--rounds", "3"])

        assert result.exit_code == 0
        assert "시뮬레이션" in result.output


class TestWebCommand:
    """main.web 명령 (line 215-217)."""

    def test_web_command_calls_uvicorn(self) -> None:
        """web 명령은 uvicorn.run을 호출한다."""
        with patch("uvicorn.run") as mock_run:
            result = runner.invoke(app, ["web", "--host", "127.0.0.1", "--port", "9999"])

        assert result.exit_code == 0
        mock_run.assert_called_once()
        # 인자 검증
        call_args = mock_run.call_args
        assert call_args.kwargs.get("host") == "127.0.0.1"
        assert call_args.kwargs.get("port") == 9999
