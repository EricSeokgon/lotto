"""TistoryScraper — 블로그에서 로또 당첨 번호 크롤링.

# @MX:ANCHOR: [AUTO] 블로그 크롤링 진입점 — API 수집 불가 시 대체 데이터 소스
# @MX:REASON: 동행복권 API 차단 환경에서 유일한 전체 데이터 획득 경로
"""

from __future__ import annotations

import datetime
import logging
from html.parser import HTMLParser
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

import requests

from lotto.config import settings
from lotto.models import DrawResult

# SPEC-LOTTO-002: 스크래퍼 URL 외부화 — LOTTO_SCRAPER_URL_1 / LOTTO_SCRAPER_URL_2 로 오버라이드
# URL[0]: 1~1000회, URL[1]: 1001~최신회
SCRAPE_URLS = list(settings.scraper_urls)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; LottoBot/1.0)"}

# SPEC-LOTTO-003 REQ-SCRAPER-001: 무음 None 반환을 구조화 경고 로깅으로 격상
logger = logging.getLogger(__name__)


class _TableParser(HTMLParser):
    """HTML 첫 번째 <table>에서 td/th 셀 텍스트 행을 추출합니다."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] = []
        self._cell: list[str] = []
        self._in_cell = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._in_cell = True
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "tr":
            if self._row:
                self.rows.append(self._row[:])
        elif tag in ("td", "th"):
            self._in_cell = False
            text = " ".join(self._cell).strip()
            self._row.append(text)

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            d = data.strip()
            if d:
                self._cell.append(d)


def _parse_table(html: str) -> list[list[str]]:
    """HTML에서 첫 번째 table 요소의 행 데이터를 반환합니다."""
    start = html.find("<table")
    if start < 0:
        return []
    end = html.find("</table>", start) + len("</table>")
    parser = _TableParser()
    parser.feed(html[start:end])
    return parser.rows


def _parse_draw_row(row: list[str]) -> DrawResult | None:
    """테이블 데이터 행 → DrawResult 변환. 형식 불일치 시 None 반환.

    행 형식: [회차, 추첨일(YYYY.MM.DD), 당첨자수, 당첨금액, n1..n6, bonus]

    SPEC-LOTTO-003 REQ-SCRAPER-001: 모든 파싱 실패는 logger.warning 로 기록 후 None 반환.
    """
    if len(row) < 11:  # noqa: PLR2004
        # SPEC-LOTTO-003 REQ-SCRAPER-001: 짧은 행에도 경고 로그
        logger.warning(
            "Scraper: row too short (len=%d, expected>=11): first=%r",
            len(row),
            row[0] if row else "<empty>",
        )
        return None
    try:
        drw_no = int(row[0].replace("회", "").strip())
        date_raw = row[1].replace(" ", "").strip()
        parts = date_raw.split(".")
        date = datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
        nums = [int(row[i]) for i in range(4, 10)]
        bonus = int(row[10])
        return DrawResult(
            drwNo=drw_no,
            date=date,
            n1=nums[0],
            n2=nums[1],
            n3=nums[2],
            n4=nums[3],
            n5=nums[4],
            n6=nums[5],
            bonus=bonus,
        )
    except (ValueError, IndexError) as exc:
        # SPEC-LOTTO-003 REQ-SCRAPER-001: 무음 None 반환 → 구조화 경고 로깅
        logger.warning(
            "Scraper: failed to parse row (first=%r): %s",
            row[0] if row else "<empty>",
            exc,
        )
        return None


def scrape_all(
    on_progress: Callable[[int, int, int], None] | None = None,
) -> list[DrawResult]:
    """두 블로그 URL에서 전체 회차 데이터를 크롤링합니다.

    Args:
        on_progress: (현재_회차, 처리_행수, 누적_수집수) 콜백 (선택)

    Returns:
        drwNo 오름차순으로 정렬된 DrawResult 목록
    """
    all_draws: dict[int, DrawResult] = {}
    session = requests.Session()
    session.headers.update(_HEADERS)

    for url in SCRAPE_URLS:
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"URL 접근 실패: {url} — {exc}") from exc

        rows = _parse_table(resp.text)
        data_rows = [r for r in rows[2:] if len(r) >= 11]  # 헤더 2행 제외

        for idx, row in enumerate(data_rows):
            draw = _parse_draw_row(row)
            if draw:
                all_draws[draw.drwNo] = draw
            if on_progress:
                on_progress(
                    draw.drwNo if draw else 0,
                    idx + 1,
                    len(all_draws),
                )

    return sorted(all_draws.values(), key=lambda d: d.drwNo)
