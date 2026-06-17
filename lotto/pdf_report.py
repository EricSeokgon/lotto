"""SPEC-LOTTO-005: PDF 리포트 생성 모듈.

추천 번호, 통계 요약, 시뮬레이션 결과를 단일 PDF로 출력한다.

# @MX:NOTE: [AUTO] fpdf2 내장 Helvetica 폰트 사용 — 한글은 ASCII 매핑으로 처리
# @MX:NOTE: [AUTO] NFR-PDF-003: PDF 섹션 라벨은 영문 사용으로 인코딩 안전 확보
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

# SPEC-LOTTO-045: fpdf2는 py.typed 미제공(types-fpdf2 스텁 별도). ignore_missing_imports로
# 억제되지 않는 import-untyped를 라인 단위로 무시한다 (런타임 동작 무관).
from fpdf import FPDF  # type: ignore[import-untyped]

if TYPE_CHECKING:  # pragma: no cover
    from lotto.models import Recommendation, SimulationResult, Statistics

# 한글 전략명 → 영문 매핑 (fpdf2 Helvetica는 Latin-1만 지원)
_STRATEGY_EN: dict[str, str] = {
    "고빈도": "High Frequency",
    "저빈도": "Low Frequency",
    "균형": "Balanced",
    "최근편향": "Recent Bias",
    "동반패턴": "Pair Pattern",
    "홀짝균형": "Odd/Even Balance",
    "번호대균형": "Range Balance",
    "핫콜드혼합": "Hot/Cold Mix",
}

# 등수 한글 → 영문 매핑
_PRIZE_EN: dict[str, str] = {
    "1등": "1st Prize",
    "2등": "2nd Prize",
    "3등": "3rd Prize",
    "4등": "4th Prize",
    "5등": "5th Prize",
    "낙첨": "No Prize",
}


def _safe_text(value: Any) -> str:  # noqa: ANN401
    """Latin-1로 인코딩 불가능한 문자를 안전하게 처리한다.

    한글 등 비ASCII 문자는 매핑 테이블을 우선 사용하고,
    매핑이 없으면 ASCII 외 문자를 '?'로 대체한다.
    """
    text = str(value)
    # 매핑 우선 적용
    if text in _STRATEGY_EN:
        return _STRATEGY_EN[text]
    if text in _PRIZE_EN:
        return _PRIZE_EN[text]
    # Latin-1 인코딩 불가 문자는 '?'로 대체
    try:
        text.encode("latin-1")
        return text
    except UnicodeEncodeError:
        return text.encode("ascii", errors="replace").decode("ascii")


def _add_section_title(pdf: FPDF, title: str) -> None:
    """섹션 제목을 추가한다."""
    pdf.set_font("Helvetica", "B", 14)
    pdf.ln(4)
    pdf.cell(0, 8, _safe_text(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)


def _add_recommendations_section(pdf: FPDF, recommendations: list[Recommendation] | None) -> None:
    """추천 번호 섹션 추가 (REQ-PDF-002)."""
    _add_section_title(pdf, "Recommendations")
    if not recommendations:
        pdf.cell(0, 6, "No data available", new_x="LMARGIN", new_y="NEXT")
        return
    for idx, rec in enumerate(recommendations, start=1):
        numbers_str = ", ".join(str(n) for n in rec.numbers)
        label_en = _safe_text(rec.strategy_label)
        line = f"Set {idx} [{label_en}]: {numbers_str}"
        pdf.cell(0, 6, _safe_text(line), new_x="LMARGIN", new_y="NEXT")


def _add_stats_section(pdf: FPDF, stats: Statistics | None) -> None:
    """통계 요약 섹션 추가 (REQ-PDF-003).

    상위 10개 빈출 번호 + 상위 5개 보너스 빈출 번호.
    """
    _add_section_title(pdf, "Top 10 Numbers")
    if stats is None or not getattr(stats.frequency, "absolute", None):
        pdf.cell(0, 6, "No data available", new_x="LMARGIN", new_y="NEXT")
    else:
        # 빈도 내림차순 (동률 시 번호 오름차순)
        top10 = sorted(
            stats.frequency.absolute.items(),
            key=lambda kv: (-kv[1], kv[0]),
        )[:10]
        for rank, (num, count) in enumerate(top10, start=1):
            pdf.cell(
                0,
                6,
                _safe_text(f"  {rank}. Number {num}: {count} times"),
                new_x="LMARGIN",
                new_y="NEXT",
            )

    _add_section_title(pdf, "Top Bonus Numbers")
    if stats is None or not getattr(stats.bonus_frequency, "absolute", None):
        pdf.cell(0, 6, "No data available", new_x="LMARGIN", new_y="NEXT")
    else:
        top_bonus = sorted(
            stats.bonus_frequency.absolute.items(),
            key=lambda kv: (-kv[1], kv[0]),
        )[:5]
        for rank, (num, count) in enumerate(top_bonus, start=1):
            pdf.cell(
                0,
                6,
                _safe_text(f"  {rank}. Number {num}: {count} times"),
                new_x="LMARGIN",
                new_y="NEXT",
            )


def _add_simulation_section(pdf: FPDF, simulation: SimulationResult | None) -> None:
    """시뮬레이션 결과 섹션 추가 (REQ-PDF-004)."""
    _add_section_title(pdf, "Simulation Results")
    if simulation is None or not getattr(simulation, "prize_counts", None):
        pdf.cell(0, 6, "No data available", new_x="LMARGIN", new_y="NEXT")
        return

    total_rounds = getattr(simulation, "total_rounds", 0)
    pdf.cell(
        0, 6, _safe_text(f"Total Rounds: {total_rounds}"), new_x="LMARGIN", new_y="NEXT"
    )

    # 등수 순서 고정 표시
    prize_order = ["1등", "2등", "3등", "4등", "5등", "낙첨"]
    prize_counts = simulation.prize_counts
    for prize_ko in prize_order:
        count = prize_counts.get(prize_ko, 0)
        prize_en = _safe_text(prize_ko)
        pdf.cell(
            0,
            6,
            _safe_text(f"  {prize_en}: {count}"),
            new_x="LMARGIN",
            new_y="NEXT",
        )


def generate_report(
    stats: Statistics | None = None,
    recommendations: list[Recommendation] | None = None,
    simulation: SimulationResult | None = None,
) -> bytes:
    """로또 분석 결과를 PDF 바이트로 생성한다.

    Args:
        stats: 통계 분석 결과 (None 가능)
        recommendations: 추천 번호 리스트 (None 가능)
        simulation: 시뮬레이션 결과 (None 가능)

    Returns:
        PDF 바이너리 데이터. 모든 인자가 None이어도 빈 섹션 메시지를 포함한
        정상 PDF를 반환한다 (REQ-PDF-006).
    """
    pdf = FPDF()
    pdf.add_page()

    # 제목
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "Lotto Analysis Report", new_x="LMARGIN", new_y="NEXT")

    # 생성일
    pdf.set_font("Helvetica", "", 10)
    today = datetime.date.today().isoformat()
    pdf.cell(0, 6, f"Generated: {today}", new_x="LMARGIN", new_y="NEXT")

    # 각 섹션 추가
    _add_stats_section(pdf, stats)
    _add_recommendations_section(pdf, recommendations)
    _add_simulation_section(pdf, simulation)

    # fpdf2 output()는 bytearray 반환 → bytes로 변환
    output = pdf.output()
    return bytes(output) if isinstance(output, bytearray) else output
