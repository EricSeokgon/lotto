"""DrawResult, Statistics, Recommendation 모델 TDD 테스트."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from lotto.models import DrawResult, Recommendation, Statistics


class TestDrawResult:
    """DrawResult 모델 테스트."""

    def test_valid_draw_result(self) -> None:
        """유효한 DrawResult 생성 테스트."""
        draw = DrawResult(
            drwNo=1,
            date=date(2002, 12, 7),
            n1=1, n2=10, n3=20, n4=30, n5=40, n6=45,
            bonus=5,
        )
        assert draw.drwNo == 1
        assert draw.date == date(2002, 12, 7)
        assert draw.n1 == 1
        assert draw.bonus == 5

    def test_numbers_sorted(self) -> None:
        """numbers() 메서드가 정렬된 리스트를 반환하는지 테스트."""
        draw = DrawResult(
            drwNo=1,
            date=date(2002, 12, 7),
            n1=45, n2=1, n3=30, n4=10, n5=20, n6=5,
            bonus=3,
        )
        result = draw.numbers()
        assert result == [1, 5, 10, 20, 30, 45]
        assert result == sorted(result)

    def test_invalid_number_range(self) -> None:
        """번호 범위 검증 (1~45 벗어나면 ValidationError)."""
        with pytest.raises(ValidationError):
            DrawResult(
                drwNo=1,
                date=date(2002, 12, 7),
                n1=46, n2=2, n3=3, n4=4, n5=5, n6=6,
                bonus=7,
            )
        with pytest.raises(ValidationError):
            DrawResult(
                drwNo=1,
                date=date(2002, 12, 7),
                n1=0, n2=2, n3=3, n4=4, n5=5, n6=6,
                bonus=7,
            )

    def test_json_serialization(self) -> None:
        """JSON 직렬화/역직렬화 일관성 테스트."""
        draw = DrawResult(
            drwNo=1148,
            date=date(2024, 12, 28),
            n1=3, n2=14, n3=26, n4=33, n5=38, n6=45,
            bonus=8,
        )
        json_str = draw.model_dump_json()
        loaded = DrawResult.model_validate_json(json_str)
        assert loaded == draw


class TestStatistics:
    """Statistics 모델 테스트."""

    def test_default_statistics(self) -> None:
        """기본 Statistics 생성 테스트."""
        stats = Statistics()
        assert stats.total_rounds == 0
        assert stats.frequency.absolute == {}
        assert stats.frequency.relative == {}
        assert stats.recent_pattern.counts == {}
        assert stats.consecutive_pattern.current_streak == {}
        assert stats.pair_analysis.top_pairs == []

    def test_json_roundtrip(self) -> None:
        """Statistics JSON 직렬화/역직렬화 테스트."""
        stats = Statistics(total_rounds=100)
        stats.frequency.absolute = {1: 30, 2: 20}
        stats.frequency.relative = {1: 0.05, 2: 0.03}
        json_str = stats.model_dump_json()
        loaded = Statistics.model_validate_json(json_str)
        assert loaded.total_rounds == 100
        assert loaded.frequency.absolute == {1: 30, 2: 20}


class TestRecommendation:
    """Recommendation 모델 테스트."""

    def test_valid_recommendation(self) -> None:
        """유효한 Recommendation 생성 및 오름차순 정렬 테스트."""
        rec = Recommendation(
            numbers=[45, 1, 20, 10, 30, 5],
            strategy_label="고빈도",
        )
        assert rec.numbers == [1, 5, 10, 20, 30, 45]
        assert rec.strategy_label == "고빈도"

    def test_duplicate_numbers_rejected(self) -> None:
        """중복 번호 포함 시 ValidationError 발생 테스트."""
        with pytest.raises(ValidationError):
            Recommendation(
                numbers=[1, 1, 2, 3, 4, 5],
                strategy_label="고빈도",
            )

    def test_wrong_count_rejected(self) -> None:
        """6개가 아닌 번호 개수 시 ValidationError 발생 테스트."""
        with pytest.raises(ValidationError):
            Recommendation(
                numbers=[1, 2, 3, 4, 5],
                strategy_label="고빈도",
            )

    def test_out_of_range_rejected(self) -> None:
        """범위 초과 번호 시 ValidationError 발생 테스트."""
        with pytest.raises(ValidationError):
            Recommendation(
                numbers=[0, 1, 2, 3, 4, 5],
                strategy_label="고빈도",
            )
        with pytest.raises(ValidationError):
            Recommendation(
                numbers=[1, 2, 3, 4, 5, 46],
                strategy_label="고빈도",
            )
