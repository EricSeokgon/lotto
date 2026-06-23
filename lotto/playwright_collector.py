"""PlaywrightCollector — Playwright 기반 동행복권 크롤러.

SPEC-LOTTO-111: HTTP API가 HTML을 반환할 때 폴백으로 사용하는 브라우저 기반 수집기.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
from typing import Any, Optional  # noqa: UP035 — Python 3.9 호환

from lotto.config import settings
from lotto.models import DrawResult

logger = logging.getLogger(__name__)

# @MX:NOTE: [AUTO] SPEC-LOTTO-111 — API URL은 LottoCollector와 동일한 설정을 공유
API_URL = settings.api_url


try:
    from playwright.async_api import async_playwright  # type: ignore[import]
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    async_playwright = None  # type: ignore[assignment, misc]
    _PLAYWRIGHT_AVAILABLE = False


def _parse_draw_json(data: dict[str, Any]) -> Optional[DrawResult]:  # noqa: UP045
    """API JSON 응답에서 DrawResult를 파싱합니다. 실패 시 None 반환."""
    if data.get("returnValue") != "success":
        return None
    try:
        raw_amount = data.get("firstWinamnt")
        raw_winners = data.get("firstPrzwnerCo")
        return DrawResult(
            drwNo=int(data["drwNo"]),
            date=datetime.date.fromisoformat(str(data["drwNoDate"])),
            n1=int(data["drwtNo1"]),
            n2=int(data["drwtNo2"]),
            n3=int(data["drwtNo3"]),
            n4=int(data["drwtNo4"]),
            n5=int(data["drwtNo5"]),
            n6=int(data["drwtNo6"]),
            bonus=int(data["bnusNo"]),
            prize1Amount=int(raw_amount) if raw_amount is not None else None,
            prize1Winners=int(raw_winners) if raw_winners is not None else None,
        )
    except (KeyError, ValueError):
        return None


class PlaywrightCollector:
    """Playwright 기반 동행복권 크롤러.

    # @MX:ANCHOR: [AUTO] SPEC-LOTTO-111 REQ-PW-002 — HTTP 폴백 수집기 공개 API
    # @MX:REASON: _collect_worker와 테스트에서 3곳 이상 직접 참조되는 공개 진입점
    """

    async def fetch_draw(self, drw_no: int) -> Optional[DrawResult]:  # noqa: UP045
        """브라우저를 통해 단일 회차 데이터를 수집합니다.

        추출 전략 (REQ-PW-003):
        1. <pre> 태그 텍스트를 JSON으로 파싱
        2. body 전체를 JSON으로 파싱
        3. 두 방법 모두 실패하면 None 반환
        """
        if async_playwright is None:
            logger.warning(
                "playwright 패키지가 설치되지 않았습니다. "
                "pip install playwright 후 playwright install chromium을 실행하세요."
            )
            return None

        url = API_URL.format(drw_no=drw_no)
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                await page.goto(url)

                # 전략 1: <pre> 태그에서 JSON 추출
                pre = await page.query_selector("pre")
                if pre is not None:
                    text = await pre.inner_text()
                    try:
                        data = json.loads(text)
                        return _parse_draw_json(data)
                    except (json.JSONDecodeError, ValueError):
                        pass

                # 전략 2: body 전체를 JSON으로 파싱
                body_text = await page.inner_text("body")
                try:
                    data = json.loads(body_text)
                    return _parse_draw_json(data)
                except (json.JSONDecodeError, ValueError):
                    pass

                return None

        except ImportError as exc:
            logger.warning("playwright 사용 불가: %s", exc)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Playwright 수집 실패 (회차 %d): %s", drw_no, exc)
            return None

    def fetch_draw_sync(self, drw_no: int) -> Optional[DrawResult]:  # noqa: UP045
        """동기 래퍼 — asyncio.run()으로 async fetch_draw를 호출합니다.

        REQ-PW-005: _collect_worker는 동기 컨텍스트에서 이 메서드를 호출합니다.
        """
        return asyncio.run(self.fetch_draw(drw_no))
