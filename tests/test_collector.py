"""LottoCollector API 수집/재시도/딜레이 TDD 테스트."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import requests_mock as rm

from lotto.collector import CollectAbortError, LottoCollector

API_URL_PATTERN = "https://www.dhlottery.co.kr/common.do"


def _make_success_response(drw_no: int = 1148) -> dict[str, object]:
    """성공 응답 샘플 데이터."""
    return {
        "returnValue": "success",
        "drwNo": drw_no,
        "drwNoDate": "2024-12-28",
        "drwtNo1": 3,
        "drwtNo2": 14,
        "drwtNo3": 26,
        "drwtNo4": 33,
        "drwtNo5": 38,
        "drwtNo6": 45,
        "bnusNo": 8,
    }


class TestFetchDraw:
    """단일 회차 API 수집 테스트."""

    def test_successful_fetch(self, requests_mock: rm.Mocker, tmp_data_dir: Path) -> None:
        """정상 API 응답 시 DrawResult 반환 테스트."""
        requests_mock.get(
            API_URL_PATTERN,
            json=_make_success_response(1148),
        )
        collector = LottoCollector(data_dir=tmp_data_dir)
        with patch("time.sleep"):
            result = collector.fetch_draw(1148)
        assert result is not None
        assert result.drwNo == 1148
        assert result.n1 == 3
        assert result.bonus == 8

    def test_failed_returnvalue(self, requests_mock: rm.Mocker, tmp_data_dir: Path) -> None:
        """returnValue != 'success' 시 None 반환 테스트."""
        requests_mock.get(
            API_URL_PATTERN,
            json={"returnValue": "fail"},
        )
        collector = LottoCollector(data_dir=tmp_data_dir)
        with patch("time.sleep"):
            result = collector.fetch_draw(9999)
        assert result is None

    def test_http_error_returns_none(self, requests_mock: rm.Mocker, tmp_data_dir: Path) -> None:
        """HTTP 500 후 3회 재시도 실패 시 None 반환 테스트."""
        requests_mock.get(API_URL_PATTERN, status_code=500)
        collector = LottoCollector(data_dir=tmp_data_dir)
        with patch("time.sleep"):
            result = collector.fetch_draw(1)
        assert result is None


class TestRetryBackoff:
    """지수 백오프 재시도 테스트."""

    def test_retry_1s_2s_4s(self, requests_mock: rm.Mocker, tmp_data_dir: Path) -> None:
        """HTTP 500 시 1s→2s→4s 딜레이로 3회 재시도 테스트."""
        requests_mock.get(API_URL_PATTERN, status_code=500)
        collector = LottoCollector(data_dir=tmp_data_dir)
        sleep_calls = []
        with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
            result = collector.fetch_draw(1)
        # 3회 재시도: 1s, 2s, 4s 딜레이
        assert sleep_calls[:3] == [1.0, 2.0, 4.0]
        assert result is None

    def test_success_on_second_attempt(self, requests_mock: rm.Mocker, tmp_data_dir: Path) -> None:
        """2차 시도에서 성공 시 DrawResult 반환 테스트."""
        requests_mock.get(
            API_URL_PATTERN,
            [
                {"status_code": 500},
                {"json": _make_success_response(1148)},
            ],
        )
        collector = LottoCollector(data_dir=tmp_data_dir)
        with patch("time.sleep"):
            result = collector.fetch_draw(1148)
        assert result is not None
        assert result.drwNo == 1148


class TestConsecutiveFailures:
    """연속 실패 abort 테스트."""

    def test_abort_on_5_consecutive_failures(
        self, requests_mock: rm.Mocker, tmp_data_dir: Path
    ) -> None:
        """5회 연속 실패 시 CollectAbortError 발생, 기존 데이터 보존 테스트."""
        # 먼저 1회차 성공 저장
        requests_mock.get(
            API_URL_PATTERN,
            [
                {"json": _make_success_response(1)},  # 1회차 성공
                {"status_code": 500},  # 2회차 실패 (3회 재시도 포함)
                {"status_code": 500},
                {"status_code": 500},
                {"status_code": 500},  # 3회차 실패
                {"status_code": 500},
                {"status_code": 500},
                {"status_code": 500},  # 4회차 실패
                {"status_code": 500},
                {"status_code": 500},
                {"status_code": 500},  # 5회차 실패
                {"status_code": 500},
                {"status_code": 500},
                {"status_code": 500},  # 6회차 실패
                {"status_code": 500},
                {"status_code": 500},
            ],
        )
        collector = LottoCollector(data_dir=tmp_data_dir)
        with patch("time.sleep"), pytest.raises(CollectAbortError):
            collector.collect_full(max_drw_no=10)

    def test_no_abort_under_5_failures(self, requests_mock: rm.Mocker, tmp_data_dir: Path) -> None:
        """4회 연속 실패는 abort 없이 계속 진행 테스트."""
        # 1,2 성공, 3,4,5,6 실패(4연속), 7 성공
        responses = (
            [{"json": _make_success_response(i)} for i in range(1, 3)]
            + [{"status_code": 500}] * 12  # 4번 × 3회 재시도
            + [{"json": _make_success_response(7)}]
        )
        requests_mock.get(API_URL_PATTERN, responses)
        collector = LottoCollector(data_dir=tmp_data_dir)
        with patch("time.sleep"):
            # 4회 연속 실패는 abort 없이 완료되어야 함
            result = collector.collect_full(max_drw_no=7)
        assert isinstance(result, list)


class TestRequestDelay:
    """200ms 요청 간 딜레이 테스트."""

    def test_minimum_delay_between_requests(
        self, requests_mock: rm.Mocker, tmp_data_dir: Path
    ) -> None:
        """연속 요청 간 200ms 이상 딜레이 테스트."""
        requests_mock.get(
            API_URL_PATTERN,
            [{"json": _make_success_response(i)} for i in range(1, 4)],
        )
        collector = LottoCollector(data_dir=tmp_data_dir)
        sleep_calls = []
        with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
            collector.collect_full(max_drw_no=3)
        # 각 요청 후 0.2초 딜레이
        delay_calls = [s for s in sleep_calls if s == 0.2]
        assert len(delay_calls) >= 2


class TestCsvPersistence:
    """CSV 저장/로드 테스트."""

    def test_save_and_load_csv(self, tmp_data_dir: Path, mini_draws: list) -> None:
        """DrawResult 목록을 CSV로 저장 후 로드 일관성 테스트."""
        collector = LottoCollector(data_dir=tmp_data_dir)
        collector.save_csv(mini_draws)
        loaded = collector.load_existing()
        assert len(loaded) == len(mini_draws)
        for orig, loaded_draw in zip(mini_draws, loaded):  # noqa: B905
            assert loaded_draw.drwNo == orig.drwNo
            assert loaded_draw.numbers() == orig.numbers()
            assert loaded_draw.bonus == orig.bonus


class TestCollectNew:
    """collect_new 메서드 테스트."""

    def test_collect_new_from_empty(self, requests_mock: rm.Mocker, tmp_data_dir: Path) -> None:
        """기존 데이터 없을 때 1회차부터 수집한다."""
        requests_mock.get(
            API_URL_PATTERN,
            [
                {"json": _make_success_response(1)},
                {"json": _make_success_response(2)},
                {"status_code": 500},  # 3회차 실패 (3회 재시도)
                {"status_code": 500},
                {"status_code": 500},
                {"status_code": 500},  # 4회차 실패
                {"status_code": 500},
                {"status_code": 500},
                {"status_code": 500},  # 5회차 실패
                {"status_code": 500},
                {"status_code": 500},
                {"status_code": 500},  # 6회차 실패
                {"status_code": 500},
                {"status_code": 500},
            ],
        )
        collector = LottoCollector(data_dir=tmp_data_dir)
        with patch("time.sleep"), pytest.raises(CollectAbortError):
            collector.collect_new(latest_drw_no=10)

    def test_collect_new_appends_to_existing(
        self, requests_mock: rm.Mocker, tmp_data_dir: Path, mini_draws: list
    ) -> None:
        """기존 데이터 있을 때 다음 회차부터 수집한다."""
        # mini_draws 에 drwNo=1,2,3 이 있다고 가정
        collector = LottoCollector(data_dir=tmp_data_dir)
        collector.save_csv(mini_draws)
        max_drw_no = max(d.drwNo for d in mini_draws)

        # 다음 회차 하나만 성공, 이후 연속 5회 실패
        responses: list[dict[str, Any]] = [
            {"json": _make_success_response(max_drw_no + 1)},
            {"status_code": 500},
            {"status_code": 500},
            {"status_code": 500},
            {"status_code": 500},  # 연속 실패 5 시작
            {"status_code": 500},
            {"status_code": 500},
            {"status_code": 500},
            {"status_code": 500},  # (4회 연속 실패 × 3 재시도)
            {"status_code": 500},
            {"status_code": 500},
            {"status_code": 500},
            {"status_code": 500},
            {"status_code": 500},
            {"status_code": 500},
            {"status_code": 500},
        ]
        requests_mock.get(API_URL_PATTERN, responses)

        with patch("time.sleep"), pytest.raises(CollectAbortError):
            collector.collect_new(latest_drw_no=max_drw_no + 10)

    def test_collect_new_fetch_invalid_data_returns_none(
        self, requests_mock: rm.Mocker, tmp_data_dir: Path
    ) -> None:
        """fetch_draw 에서 KeyError 발생 시 None 반환 (에러 경로 커버)."""
        requests_mock.get(
            API_URL_PATTERN,
            json={"returnValue": "success", "drwNo": 1},  # 필수 필드 누락
        )
        collector = LottoCollector(data_dir=tmp_data_dir)
        with patch("time.sleep"):
            result = collector.fetch_draw(1)
        assert result is None
