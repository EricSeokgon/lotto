"""SPEC-LOTTO-111: PlaywrightCollector 및 HTML 감지 테스트."""

from __future__ import annotations

import asyncio
import datetime
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import requests

from lotto.models import DrawResult


# --- 헬퍼 함수 ---

def _make_draw_json(drw_no: int = 1226) -> dict[str, Any]:
    """테스트용 유효한 당첨 번호 JSON 데이터를 반환합니다."""
    return {
        "returnValue": "success",
        "drwNo": drw_no,
        "drwNoDate": "2025-02-01",
        "drwtNo1": 3,
        "drwtNo2": 14,
        "drwtNo3": 22,
        "drwtNo4": 31,
        "drwtNo5": 38,
        "drwtNo6": 42,
        "bnusNo": 7,
        "firstWinamnt": 2000000000,
        "firstPrzwnerCo": 3,
    }


def _make_draw_result(drw_no: int = 1226) -> DrawResult:
    """테스트용 DrawResult를 반환합니다."""
    return DrawResult(
        drwNo=drw_no,
        date=datetime.date(2025, 2, 1),
        n1=3, n2=14, n3=22, n4=31, n5=38, n6=42,
        bonus=7,
        prize1Amount=2000000000,
        prize1Winners=3,
    )


# ============================================================
# 테스트 1: pre 태그에서 JSON 추출 성공
# ============================================================
@pytest.mark.asyncio
async def test_fetch_draw_success_from_pre_tag():
    """PlaywrightCollector.fetch_draw() — pre 태그에서 JSON 추출 성공 (AC-001)."""
    from lotto.playwright_collector import PlaywrightCollector

    draw_json = _make_draw_json(1226)

    # Playwright async context manager 모킹
    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.query_selector = AsyncMock()
    mock_pre = AsyncMock()
    mock_pre.inner_text = AsyncMock(return_value=json.dumps(draw_json))
    mock_page.query_selector.return_value = mock_pre

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)

    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

    # async_playwright() 콘텍스트 매니저 모킹
    mock_async_playwright = AsyncMock()
    mock_async_playwright.__aenter__ = AsyncMock(return_value=mock_playwright)
    mock_async_playwright.__aexit__ = AsyncMock(return_value=None)

    with patch("lotto.playwright_collector.async_playwright", return_value=mock_async_playwright):
        collector = PlaywrightCollector()
        result = await collector.fetch_draw(1226)

    assert result is not None
    assert result.drwNo == 1226
    assert result.numbers() == [3, 14, 22, 31, 38, 42]
    assert result.bonus == 7


# ============================================================
# 테스트 2: body에서 JSON 추출 성공 (pre 없음)
# ============================================================
@pytest.mark.asyncio
async def test_fetch_draw_success_from_body():
    """PlaywrightCollector.fetch_draw() — body에서 JSON 추출 성공 (pre 없음)."""
    from lotto.playwright_collector import PlaywrightCollector

    draw_json = _make_draw_json(1000)

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    # pre 태그 없음
    mock_page.query_selector = AsyncMock(return_value=None)
    mock_page.inner_text = AsyncMock(return_value=json.dumps(draw_json))

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)

    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

    mock_async_playwright = AsyncMock()
    mock_async_playwright.__aenter__ = AsyncMock(return_value=mock_playwright)
    mock_async_playwright.__aexit__ = AsyncMock(return_value=None)

    with patch("lotto.playwright_collector.async_playwright", return_value=mock_async_playwright):
        collector = PlaywrightCollector()
        result = await collector.fetch_draw(1000)

    assert result is not None
    assert result.drwNo == 1000


# ============================================================
# 테스트 3: HTML 파싱 실패 시 None 반환
# ============================================================
@pytest.mark.asyncio
async def test_fetch_draw_html_parse_failure_returns_none():
    """PlaywrightCollector.fetch_draw() — HTML 파싱 실패 시 None 반환."""
    from lotto.playwright_collector import PlaywrightCollector

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    # pre 태그 없음, body도 JSON이 아닌 HTML
    mock_page.query_selector = AsyncMock(return_value=None)
    mock_page.inner_text = AsyncMock(return_value="<!DOCTYPE html><html><body>Error</body></html>")

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)

    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

    mock_async_playwright = AsyncMock()
    mock_async_playwright.__aenter__ = AsyncMock(return_value=mock_playwright)
    mock_async_playwright.__aexit__ = AsyncMock(return_value=None)

    with patch("lotto.playwright_collector.async_playwright", return_value=mock_async_playwright):
        collector = PlaywrightCollector()
        result = await collector.fetch_draw(9999)

    assert result is None


# ============================================================
# 테스트 4: returnValue != "success" 시 None 반환
# ============================================================
@pytest.mark.asyncio
async def test_fetch_draw_return_value_fail_returns_none():
    """PlaywrightCollector.fetch_draw() — returnValue != "success" 시 None 반환."""
    from lotto.playwright_collector import PlaywrightCollector

    fail_json = {"returnValue": "fail"}

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_pre = AsyncMock()
    mock_pre.inner_text = AsyncMock(return_value=json.dumps(fail_json))
    mock_page.query_selector = AsyncMock(return_value=mock_pre)

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)

    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

    mock_async_playwright = AsyncMock()
    mock_async_playwright.__aenter__ = AsyncMock(return_value=mock_playwright)
    mock_async_playwright.__aexit__ = AsyncMock(return_value=None)

    with patch("lotto.playwright_collector.async_playwright", return_value=mock_async_playwright):
        collector = PlaywrightCollector()
        result = await collector.fetch_draw(99999)

    assert result is None


# ============================================================
# 테스트 5: Playwright 미설치 시 None 반환 + 경고 로그 (AC-004)
# ============================================================
@pytest.mark.asyncio
async def test_fetch_draw_playwright_not_installed_returns_none(caplog):
    """PlaywrightCollector.fetch_draw() — Playwright 미설치 시 None 반환 + 경고."""
    import logging

    with patch.dict("sys.modules", {"playwright": None, "playwright.async_api": None}):
        # 미설치 시뮬레이션: async_playwright import 오류
        with patch(
            "lotto.playwright_collector.async_playwright",
            side_effect=ImportError("No module named 'playwright'"),
        ):
            from lotto.playwright_collector import PlaywrightCollector

            with caplog.at_level(logging.WARNING, logger="lotto.playwright_collector"):
                collector = PlaywrightCollector()
                result = await collector.fetch_draw(1226)

    assert result is None
    # 경고 로그가 출력되었는지 확인
    assert any("playwright" in record.message.lower() for record in caplog.records)


# ============================================================
# 테스트 6: _fetch_with_retry — HTML 응답 감지 → HTMLResponseError (AC-002)
# ============================================================
def test_fetch_with_retry_html_body_raises_html_response_error():
    """LottoCollector._fetch_with_retry — <!DOCTYPE 본문 수신 시 HTMLResponseError (AC-002)."""
    from lotto.collector import HTMLResponseError, LottoCollector

    html_body = "<!DOCTYPE html><html><head></head><body>Access Denied</body></html>"
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.headers = {"Content-Type": "text/html; charset=utf-8"}
    mock_response.text = html_body
    mock_response.json.side_effect = ValueError("Not JSON")

    mock_session = Mock()
    mock_session.get = Mock(return_value=mock_response)

    collector = LottoCollector(session=mock_session)

    with pytest.raises(HTMLResponseError):
        collector._fetch_with_retry(1226)


# ============================================================
# 테스트 7: _fetch_with_retry — Content-Type text/html → HTMLResponseError (AC-003)
# ============================================================
def test_fetch_with_retry_html_content_type_raises_html_response_error():
    """LottoCollector._fetch_with_retry — Content-Type: text/html → HTMLResponseError (AC-003)."""
    from lotto.collector import HTMLResponseError, LottoCollector

    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.headers = {"Content-Type": "text/html; charset=utf-8"}
    mock_response.text = '{"returnValue": "success"}'  # 본문은 JSON처럼 보여도

    mock_session = Mock()
    mock_session.get = Mock(return_value=mock_response)

    collector = LottoCollector(session=mock_session)

    with pytest.raises(HTMLResponseError):
        collector._fetch_with_retry(1226)


# ============================================================
# 테스트 8: _collect_worker — 3회 연속 HTMLResponseError → Playwright 폴백 전환 (AC-005)
# ============================================================
def test_collect_worker_playwright_fallback_after_html_errors():
    """_collect_worker — HTMLResponseError 3회 후 PlaywrightCollector 폴백 동작."""
    from lotto.collector import HTMLResponseError, LottoCollector
    from lotto.playwright_collector import PlaywrightCollector
    from lotto.web.routes.api import _collect_worker

    draw_result = _make_draw_result(1226)

    # LottoCollector.fetch_draw가 HTMLResponseError를 3번 발생시킴
    html_err_side_effects = [
        HTMLResponseError("HTML response"),
        HTMLResponseError("HTML response"),
        HTMLResponseError("HTML response"),
    ]

    # _collect_worker는 함수 내부에서 local import하므로
    # PlaywrightCollector.fetch_draw_sync 인스턴스 메서드를 직접 patch
    with (
        patch.object(LottoCollector, "load_existing", return_value=[]),
        patch.object(LottoCollector, "fetch_draw", side_effect=html_err_side_effects),
        patch.object(LottoCollector, "save_csv"),
        patch.object(PlaywrightCollector, "fetch_draw_sync", return_value=draw_result) as mock_pw_sync,
        patch("lotto.web.routes.api._run_analyze_sync"),
        patch("lotto.web.routes.api.invalidate_cache"),
        patch("time.sleep"),
    ):
        # 1226~1230 중 처음 3개(1226, 1227, 1228)는 HTML 오류 → 폴백 전환
        # 이후 1229, 1230은 playwright_mode로 실행되어야 함
        _collect_worker(full=False, start_from=1226, max_drw_no=1230)

    # PlaywrightCollector.fetch_draw_sync가 폴백으로 호출되었어야 함
    assert mock_pw_sync.called


# ============================================================
# 테스트 9: fetch_draw_sync — asyncio.run 래퍼 동작 확인
# ============================================================
def test_fetch_draw_sync_wraps_async():
    """PlaywrightCollector.fetch_draw_sync() — asyncio.run으로 async fetch_draw 호출."""
    from lotto.playwright_collector import PlaywrightCollector

    expected = _make_draw_result(1226)

    collector = PlaywrightCollector()

    with patch.object(collector, "fetch_draw", new=AsyncMock(return_value=expected)):
        result = collector.fetch_draw_sync(1226)

    assert result is not None
    assert result.drwNo == 1226


# ============================================================
# 테스트 10: _collect_worker — Playwright 폴백 후 정상 저장 확인 (AC-005 확장)
# ============================================================
def test_collect_worker_saves_after_playwright_fallback():
    """_collect_worker — Playwright 폴백 성공 후 save_csv 호출 확인."""
    from lotto.collector import HTMLResponseError, LottoCollector
    from lotto.playwright_collector import PlaywrightCollector
    from lotto.web.routes.api import _collect_worker

    draw_1229 = _make_draw_result(1229)
    draw_1230 = _make_draw_result(1230)

    # 3회 HTMLResponseError 후 추가 호출 없음
    html_errors = [
        HTMLResponseError("HTML"),
        HTMLResponseError("HTML"),
        HTMLResponseError("HTML"),
    ]

    with (
        patch.object(LottoCollector, "load_existing", return_value=[]),
        patch.object(LottoCollector, "fetch_draw", side_effect=html_errors),
        patch.object(LottoCollector, "save_csv") as mock_save,
        patch.object(PlaywrightCollector, "fetch_draw_sync", side_effect=[draw_1229, draw_1230]),
        patch("lotto.web.routes.api._run_analyze_sync"),
        patch("lotto.web.routes.api.invalidate_cache"),
        patch("time.sleep"),
    ):
        # 1226~1230 (3회 HTML 오류 후 1229, 1230 Playwright로 수집)
        _collect_worker(full=False, start_from=1226, max_drw_no=1230)

    # save_csv가 수집 결과와 함께 호출되었는지 확인
    assert mock_save.called
    saved_draws = mock_save.call_args[0][0]
    assert len(saved_draws) >= 1
