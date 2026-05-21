"""SPEC-LOTTO-004 REQ-INT-001: 전체 파이프라인 E2E 통합 테스트.

collect → analyze → recommend → simulate 전체 흐름이 단일 시나리오에서
정상 작동함을 보증한다.

@MX:SPEC: SPEC-LOTTO-004 REQ-INT-001
"""

from __future__ import annotations

import datetime
import random
from pathlib import Path

from lotto.analyzer import LottoAnalyzer
from lotto.collector import LottoCollector
from lotto.models import DrawResult
from lotto.recommender import LottoRecommender
from lotto.simulator import LottoSimulator


def _make_draws(n: int) -> list[DrawResult]:
    """결정적 시드로 n개의 임의 회차 데이터를 생성한다."""
    draws: list[DrawResult] = []
    for i in range(1, n + 1):
        rng = random.Random(i)
        nums = rng.sample(range(1, 46), 7)
        # n1~n6은 오름차순일 필요는 없지만 1~45 범위여야 한다.
        body = sorted(nums[:6])
        bonus = nums[6]
        draws.append(
            DrawResult(
                drwNo=i,
                date=datetime.date(2020, 1, 1) + datetime.timedelta(weeks=i),
                n1=body[0],
                n2=body[1],
                n3=body[2],
                n4=body[3],
                n5=body[4],
                n6=body[5],
                bonus=bonus,
            )
        )
    return draws


class TestPipelineIntegration:
    """REQ-INT-001: collect → analyze → recommend → simulate E2E 흐름."""

    def test_pipeline_analyze_from_draws(self) -> None:
        """Scenario 1.1: 50개 회차를 analyze하면 total_rounds == 50 이어야 한다."""
        draws = _make_draws(50)

        stats = LottoAnalyzer().analyze(draws)

        assert stats.total_rounds == 50
        # 보너스 빈도가 채워졌는지 확인 (REQ-BONUS-002 회귀 보호)
        assert stats.bonus_frequency is not None
        assert len(stats.bonus_frequency.absolute) == 45
        # 빈도 합이 50과 같아야 한다 (각 회차당 1개의 보너스)
        total_bonus = sum(stats.bonus_frequency.absolute.values())
        assert total_bonus == 50

    def test_pipeline_recommend_uses_stats(self) -> None:
        """Scenario 1.2: 통계 → 5개 추천 세트, 각 6개 번호."""
        draws = _make_draws(50)
        stats = LottoAnalyzer().analyze(draws)

        recommender = LottoRecommender(stats)
        recommendations = recommender.recommend(count=5)

        assert len(recommendations) == 5
        for rec in recommendations:
            assert len(rec.numbers) == 6
            assert len(set(rec.numbers)) == 6
            assert all(1 <= n <= 45 for n in rec.numbers)

    def test_pipeline_simulate_full(self) -> None:
        """Scenario 1.3: 100 회차 시뮬레이션은 prize_counts를 반환해야 한다."""
        draws = _make_draws(100)

        result = LottoSimulator(draws).simulate(rounds=20)

        assert result.total_rounds == 20
        # SimulationResult.prize_counts는 1등~5등/낙첨 키를 가진다
        expected_keys = {"1등", "2등", "3등", "4등", "5등", "낙첨"}
        assert set(result.prize_counts.keys()) >= expected_keys
        # 시뮬레이션 회차수와 prize_counts 합이 같아야 한다.
        assert sum(result.prize_counts.values()) == 20
        # details는 각 회차에 대한 항목을 가진다.
        assert len(result.details) == 20

    def test_pipeline_collector_save_load(self, tmp_path: Path) -> None:
        """Scenario 1.4: save_csv → load_existing 라운드트립."""
        draws = _make_draws(10)
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        collector = LottoCollector(data_dir=data_dir)
        collector.save_csv(draws)

        # 새 컬렉터 인스턴스로 로드
        loaded = LottoCollector(data_dir=data_dir).load_existing()

        assert len(loaded) == len(draws)
        assert loaded[0].drwNo == draws[0].drwNo
        assert loaded[0].bonus == draws[0].bonus
        assert loaded[-1].drwNo == draws[-1].drwNo

    def test_pipeline_full_end_to_end(self, tmp_path: Path) -> None:
        """전체 파이프라인을 임시 디렉토리에서 End-to-End 실행한다."""
        draws = _make_draws(30)
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        # 1. collect (save)
        LottoCollector(data_dir=data_dir).save_csv(draws)

        # 2. load + analyze
        loaded = LottoCollector(data_dir=data_dir).load_existing()
        stats = LottoAnalyzer().analyze(loaded)
        assert stats.total_rounds == 30

        # 3. analyze → save_stats → load_stats
        stats_path = data_dir / "stats.json"
        LottoAnalyzer().save_stats(stats, stats_path)
        assert stats_path.exists()
        loaded_stats = LottoAnalyzer.load_stats(stats_path)
        assert loaded_stats.total_rounds == 30

        # 4. recommend
        recs = LottoRecommender(loaded_stats).recommend(count=3)
        assert len(recs) == 3

        # 5. simulate
        sim_result = LottoSimulator(loaded).simulate(rounds=5)
        assert sim_result.total_rounds == 5
