"""SPEC-LOTTO-005: PDF 리포트 생성 모듈 테스트.

# @MX:NOTE: [AUTO] generate_report() 단위 테스트 — 추천/통계/시뮬레이션 섹션 검증
"""

from __future__ import annotations

from lotto.analyzer import FrequencyStats, Statistics
from lotto.recommender import Recommendation
from lotto.simulator import SimulationResult


def _build_recommendation(numbers: list[int], label: str) -> Recommendation:
    """테스트용 Recommendation 인스턴스 빌더."""
    return Recommendation(
        numbers=numbers,
        strategy_label=label,
        strategy_desc=f"{label} 전략 설명",
        scores=dict.fromkeys(numbers, 0.5),
    )


def _build_statistics() -> Statistics:
    """테스트용 Statistics 인스턴스 빌더 — 빈도 통계 포함."""
    freq_abs = {i: (50 - i) for i in range(1, 46)}
    bonus_abs = {i: (10 + (i % 7)) for i in range(1, 46)}
    freq_rel = {k: v / 100 for k, v in freq_abs.items()}
    bonus_rel = {k: v / 50 for k, v in bonus_abs.items()}
    return Statistics(
        frequency=FrequencyStats(absolute=freq_abs, relative=freq_rel),
        bonus_frequency=FrequencyStats(absolute=bonus_abs, relative=bonus_rel),
        total_rounds=100,
    )


def _build_simulation() -> SimulationResult:
    """테스트용 SimulationResult 인스턴스 빌더."""
    return SimulationResult(
        total_rounds=1000,
        prize_counts={"1등": 1, "2등": 3, "3등": 15, "4등": 80, "5등": 400, "낙첨": 501},
        hit_rate=0.499,
        details=[],
    )


class TestGenerateReport:
    """generate_report() 함수 단위 테스트."""

    def test_generate_pdf_returns_bytes(self) -> None:
        """모든 인자 None일 때도 bytes를 반환해야 한다 (REQ-PDF-006)."""
        from lotto.pdf_report import generate_report

        result = generate_report(stats=None, recommendations=None, simulation=None)

        assert isinstance(result, (bytes, bytearray))
        assert len(result) > 0
        # PDF magic bytes
        assert bytes(result[:4]) == b"%PDF"

    def test_generate_pdf_with_recommendations(self) -> None:
        """추천 데이터를 포함하면 PDF가 정상 생성된다 (REQ-PDF-002)."""
        from lotto.pdf_report import generate_report

        recs = [
            _build_recommendation([1, 2, 3, 4, 5, 6], "고빈도"),
            _build_recommendation([7, 8, 9, 10, 11, 12], "균형"),
        ]
        result = generate_report(stats=None, recommendations=recs, simulation=None)

        assert isinstance(result, (bytes, bytearray))
        assert len(result) > 0
        assert bytes(result[:4]) == b"%PDF"

    def test_generate_pdf_with_stats(self) -> None:
        """통계 데이터를 포함하면 PDF가 정상 생성된다 (REQ-PDF-003)."""
        from lotto.pdf_report import generate_report

        stats = _build_statistics()
        result = generate_report(stats=stats, recommendations=None, simulation=None)

        assert isinstance(result, (bytes, bytearray))
        assert len(result) > 0
        assert bytes(result[:4]) == b"%PDF"

    def test_generate_pdf_with_simulation(self) -> None:
        """시뮬레이션 데이터를 포함하면 PDF가 정상 생성된다 (REQ-PDF-004)."""
        from lotto.pdf_report import generate_report

        sim = _build_simulation()
        result = generate_report(stats=None, recommendations=None, simulation=sim)

        assert isinstance(result, (bytes, bytearray))
        assert len(result) > 0
        assert bytes(result[:4]) == b"%PDF"

    def test_generate_pdf_all_sections(self) -> None:
        """모든 섹션 데이터를 포함해도 예외 없이 PDF가 생성된다."""
        from lotto.pdf_report import generate_report

        recs = [_build_recommendation([1, 2, 3, 4, 5, 6], "고빈도")]
        stats = _build_statistics()
        sim = _build_simulation()
        result = generate_report(stats=stats, recommendations=recs, simulation=sim)

        assert isinstance(result, (bytes, bytearray))
        assert len(result) > 0
        assert bytes(result[:4]) == b"%PDF"

    def test_generate_pdf_all_none(self) -> None:
        """모든 인자가 None이어도 빈 섹션을 표시한 PDF를 생성한다 (REQ-PDF-006)."""
        from lotto.pdf_report import generate_report

        result = generate_report(stats=None, recommendations=None, simulation=None)

        # 예외 없이 정상 생성되어야 함
        assert isinstance(result, (bytes, bytearray))
        assert len(result) > 100  # 최소한의 PDF 구조 포함

    def test_pdf_contains_korean_safe(self) -> None:
        """한글 전략명이 포함된 데이터도 인코딩 에러 없이 처리된다 (NFR-PDF-003)."""
        from lotto.pdf_report import generate_report

        # STRATEGY_LABELS의 한글 라벨 사용
        recs = [
            _build_recommendation([1, 2, 3, 4, 5, 6], "고빈도"),
            _build_recommendation([7, 8, 9, 10, 11, 12], "저빈도"),
            _build_recommendation([13, 14, 15, 16, 17, 18], "홀짝균형"),
        ]
        # 예외 발생하지 않아야 함
        result = generate_report(stats=None, recommendations=recs, simulation=None)

        assert isinstance(result, (bytes, bytearray))
        assert len(result) > 0

    def test_generate_pdf_empty_recommendations(self) -> None:
        """추천 리스트가 빈 리스트일 때도 정상 처리된다."""
        from lotto.pdf_report import generate_report

        result = generate_report(stats=None, recommendations=[], simulation=None)

        assert isinstance(result, (bytes, bytearray))
        assert len(result) > 0

    def test_generate_pdf_partial_data(self) -> None:
        """일부 데이터만 있는 경우에도 정상 처리된다."""
        from lotto.pdf_report import generate_report

        stats = _build_statistics()
        # recommendations와 simulation은 None
        result = generate_report(stats=stats, recommendations=None, simulation=None)

        assert isinstance(result, (bytes, bytearray))
        assert len(result) > 0


def test_safe_text_non_latin1_falls_back_to_ascii() -> None:
    """매핑 없는 non-latin-1 문자열은 ASCII 대체 문자(?)로 변환된다."""
    from lotto.pdf_report import _safe_text

    # 한글 "가나다"는 매핑 없고 latin-1 인코딩 불가 → UnicodeEncodeError 경로
    result = _safe_text("가나다")
    assert result == "???"
