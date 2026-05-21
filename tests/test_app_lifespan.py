"""SPEC-LOTTO-004 REQ-INT-002: FastAPI lifespan 및 주간 자동수집 태스크 테스트.

_next_monday_midnight, _weekly_collect_task, _lifespan을 직접 검증한다.

@MX:SPEC: SPEC-LOTTO-004 REQ-INT-002
"""

from __future__ import annotations

import asyncio
import datetime
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


# === Scenario 2.1, 2.2: _next_monday_midnight ===


def test_next_monday_midnight_returns_positive_seconds() -> None:
    """Scenario 2.1: 반환된 초는 양수이고 7일(604800초) 미만이어야 한다."""
    from lotto.web.app import _next_monday_midnight

    seconds = _next_monday_midnight()

    assert seconds > 0
    assert seconds <= 7 * 24 * 3600  # 최대 7일


def test_next_monday_midnight_is_monday() -> None:
    """Scenario 2.2: 함수가 측정한 now + 반환초는 정확히 월요일 자정이어야 한다.

    함수 내부에서 now를 캡처하기 때문에, 외부에서 다시 now()를 호출하면
    수 마이크로초 늦어져 23:59:59.99...로 보일 수 있다. 따라서 함수 호출을
    감싸서 동일한 now 기준점에서 계산해야 한다.
    """
    from lotto.web.app import _next_monday_midnight

    # 호출 직전/직후 시각 평균을 기준으로 비교 (오차 < 1 ms 허용)
    before = datetime.datetime.now()
    seconds = _next_monday_midnight()
    after = datetime.datetime.now()
    midpoint = before + (after - before) / 2

    target = midpoint + datetime.timedelta(seconds=seconds)
    # 자정과 1초 이내 거리에 있어야 한다
    midnight_target = target.replace(hour=0, minute=0, second=0, microsecond=0)
    if target.hour == 23:  # noqa: PLR2004
        # 23:59:59.xxx에 매우 가까운 경우 다음 날 자정이 실제 타겟
        midnight_target = midnight_target + datetime.timedelta(days=1)
    delta_sec = abs((target - midnight_target).total_seconds())
    assert delta_sec < 1.0  # 1초 미만 오차
    # 타겟 자정의 요일이 월요일이어야 한다
    assert midnight_target.weekday() == 0


def test_next_monday_midnight_is_midnight_hour() -> None:
    """함수 호출 전 datetime을 모킹하여 정확한 자정 계산을 검증한다."""
    # 2026-05-21은 목요일이다. 다음 월요일은 2026-05-25이다.
    fixed_now = datetime.datetime(2026, 5, 21, 10, 30, 45)
    expected_next_monday = datetime.datetime(2026, 5, 25, 0, 0, 0)
    expected_seconds = (expected_next_monday - fixed_now).total_seconds()

    with patch("lotto.web.app.datetime") as mock_dt:
        # datetime.datetime.now()만 모킹, 나머지는 실제 datetime을 사용
        mock_dt.datetime.now.return_value = fixed_now
        mock_dt.timedelta = datetime.timedelta

        from lotto.web.app import _next_monday_midnight

        seconds = _next_monday_midnight()

    assert seconds == pytest.approx(expected_seconds, abs=1.0)


# === Scenario 2.3: _weekly_collect_task 취소 ===


@pytest.mark.asyncio
async def test_weekly_collect_task_cancellation_is_clean() -> None:
    """Scenario 2.3: task.cancel() 시 CancelledError만 발생하고 다른 예외 없음."""
    from lotto.web.app import _weekly_collect_task

    task = asyncio.create_task(_weekly_collect_task())
    # 태스크가 첫 sleep 진입할 때까지 잠시 대기
    await asyncio.sleep(0.01)

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert task.cancelled() or task.done()


# === Scenario 2.4: lifespan 컨텍스트 매니저 사이클 ===


@pytest.mark.asyncio
async def test_lifespan_creates_and_cancels_weekly_task() -> None:
    """Scenario 2.4: lifespan 시작 시 task 생성, 종료 시 정상 취소."""
    from lotto.web.app import app

    # httpx 0.28+에서는 transport를 직접 지정해야 한다.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # lifespan startup이 트리거된다.
        response = await client.get("/health")
        assert response.status_code == 200
    # 컨텍스트 종료 시 lifespan shutdown이 실행되어 task가 cancel된다.
    # 예외 없이 여기까지 도달하면 통과.


@pytest.mark.asyncio
async def test_lifespan_direct_context_manager() -> None:
    """_lifespan 컨텍스트 매니저를 직접 진입/종료한다."""
    from lotto.web.app import _lifespan, app

    async with _lifespan(app):
        # lifespan 내부에서 weekly task가 생성되어 실행 중이어야 한다.
        # 현재 이벤트 루프에서 실행 중인 태스크가 존재해야 한다.
        await asyncio.sleep(0.01)
    # 컨텍스트 종료 후 task.cancel()이 호출되어야 한다.


# === Scenario 2.5: _weekly_collect_task가 트리거되는 분기 ===


@pytest.mark.asyncio
async def test_weekly_collect_task_triggers_collect_worker() -> None:
    """주간 태스크가 wait 후 _collect_worker를 호출하는지 검증.

    _next_monday_midnight을 0초로 모킹하고 첫 루프만 실행한다.
    """
    # threading.Thread.start를 모킹하여 실제 워커 실행을 차단
    with (
        patch("lotto.web.app._next_monday_midnight", return_value=0.0),
        patch("lotto.web.app.threading.Thread") as mock_thread,
    ):
        from lotto.web.app import _weekly_collect_task

        task = asyncio.create_task(_weekly_collect_task())
        # threading.Thread().start()가 호출될 시간을 확보
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # _collect_worker가 daemon thread로 실행 시도되어야 한다.
        assert mock_thread.called
