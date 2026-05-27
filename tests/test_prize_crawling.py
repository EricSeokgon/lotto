"""SPEC-LOTTO-022: 1등 당첨금 크롤링 TDD 테스트.

REQ-PRIZE-C-001: API 응답 파싱 확장 (firstWinamnt / firstPrzwnerCo)
REQ-PRIZE-C-002: 기존 데이터 소급 업데이트 (update_prizes)
REQ-PRIZE-C-003: 수집 현황 UI 1등 당첨금 컬럼
"""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import requests_mock as rm
from fastapi.testclient import TestClient

from lotto.collector import LottoCollector
from lotto.models import DrawResult

API_URL_PATTERN = "https://www.dhlottery.co.kr/common.do"


def _make_response_with_prize(
    drw_no: int = 1148,
    prize_amount: int = 2_500_000_000,
    winners: int = 7,
) -> dict[str, object]:
    """1등 당첨금 필드 포함 응답."""
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
        "firstWinamnt": prize_amount,
        "firstPrzwnerCo": winners,
    }


def _make_response_without_prize(drw_no: int = 1148) -> dict[str, object]:
    """1등 당첨금 필드 없는 응답 (방어 코드 검증용)."""
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


# ─── REQ-PRIZE-C-001: API 응답 파싱 확장 ─────────────────────────────


class TestFetchDrawParsesPrize:
    """fetch_draw가 1등 당첨금 / 당첨자 수 필드를 파싱하는지 검증."""

    def test_fetch_draw_parses_prize_amount_and_winners(
        self,
        requests_mock: rm.Mocker,
        tmp_data_dir: Path,
    ) -> None:
        """firstWinamnt / firstPrzwnerCo 가 DrawResult에 저장되는지."""
        requests_mock.get(
            API_URL_PATTERN,
            json=_make_response_with_prize(1148, 2_500_000_000, 7),
        )
        collector = LottoCollector(data_dir=tmp_data_dir)
        with patch("time.sleep"):
            result = collector.fetch_draw(1148)

        assert result is not None
        assert result.prize1Amount == 2_500_000_000
        assert result.prize1Winners == 7

    def test_fetch_draw_missing_prize_fields_returns_none(
        self,
        requests_mock: rm.Mocker,
        tmp_data_dir: Path,
    ) -> None:
        """API 응답에 prize 필드가 없으면 None으로 처리."""
        requests_mock.get(
            API_URL_PATTERN,
            json=_make_response_without_prize(1148),
        )
        collector = LottoCollector(data_dir=tmp_data_dir)
        with patch("time.sleep"):
            result = collector.fetch_draw(1148)

        assert result is not None
        # 기존 필드는 정상 파싱
        assert result.drwNo == 1148
        assert result.bonus == 8
        # 누락된 prize 필드는 None
        assert result.prize1Amount is None
        assert result.prize1Winners is None

    def test_fetch_draw_partial_prize_field(
        self,
        requests_mock: rm.Mocker,
        tmp_data_dir: Path,
    ) -> None:
        """firstWinamnt만 있고 firstPrzwnerCo 가 누락된 경우 → 각각 독립 처리."""
        payload = _make_response_with_prize(1148, 100, 1)
        del payload["firstPrzwnerCo"]
        requests_mock.get(API_URL_PATTERN, json=payload)
        collector = LottoCollector(data_dir=tmp_data_dir)
        with patch("time.sleep"):
            result = collector.fetch_draw(1148)

        assert result is not None
        assert result.prize1Amount == 100
        assert result.prize1Winners is None


# ─── REQ-PRIZE-C-002: 기존 데이터 소급 업데이트 ──────────────────────


class TestUpdatePrizes:
    """update_prizes 메서드 — prize1Amount=None 행만 재요청."""

    def test_update_prizes_only_fetches_missing_rows(
        self,
        requests_mock: rm.Mocker,
        tmp_data_dir: Path,
    ) -> None:
        """이미 prize1Amount가 있는 행은 건너뛰고, None 인 행만 재요청한다."""
        # 기존 데이터: 1회는 prize 있음, 2회/3회는 None
        existing = [
            DrawResult(
                drwNo=1, date=datetime.date(2002, 12, 7),
                n1=10, n2=23, n3=29, n4=33, n5=37, n6=40, bonus=16,
                prize1Amount=863_604_600, prize1Winners=1,
            ),
            DrawResult(
                drwNo=2, date=datetime.date(2002, 12, 14),
                n1=9, n2=13, n3=21, n4=25, n5=32, n6=42, bonus=2,
                prize1Amount=None, prize1Winners=None,
            ),
            DrawResult(
                drwNo=3, date=datetime.date(2002, 12, 21),
                n1=11, n2=16, n3=19, n4=21, n5=27, n6=31, bonus=30,
                prize1Amount=None, prize1Winners=None,
            ),
        ]
        collector = LottoCollector(data_dir=tmp_data_dir)
        collector.save_csv(existing)

        # 2회/3회만 fetch 결과 mock
        fetch_calls: list[int] = []

        def _fake_fetch(drw_no: int) -> DrawResult | None:
            fetch_calls.append(drw_no)
            return DrawResult(
                drwNo=drw_no,
                date=datetime.date(2002, 12, 14),
                n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, bonus=7,
                prize1Amount=2_000_000_000 + drw_no,
                prize1Winners=drw_no,
            )

        with patch.object(collector, "fetch_draw", side_effect=_fake_fetch), \
             patch("time.sleep"):
            updated = collector.update_prizes()

        # 2회/3회만 호출됨 (1회는 이미 데이터 있음)
        assert sorted(fetch_calls) == [2, 3]
        # 반환: 업데이트된 회차 수
        assert updated == 2

    def test_update_prizes_saves_to_csv(
        self,
        requests_mock: rm.Mocker,
        tmp_data_dir: Path,
    ) -> None:
        """업데이트 후 CSV에서 prize 데이터가 정상 읽힘."""
        existing = [
            DrawResult(
                drwNo=1, date=datetime.date(2002, 12, 7),
                n1=10, n2=23, n3=29, n4=33, n5=37, n6=40, bonus=16,
                prize1Amount=None, prize1Winners=None,
            ),
        ]
        collector = LottoCollector(data_dir=tmp_data_dir)
        collector.save_csv(existing)

        def _fake_fetch(drw_no: int) -> DrawResult | None:
            return DrawResult(
                drwNo=1, date=datetime.date(2002, 12, 7),
                n1=10, n2=23, n3=29, n4=33, n5=37, n6=40, bonus=16,
                prize1Amount=863_604_600, prize1Winners=1,
            )

        with patch.object(collector, "fetch_draw", side_effect=_fake_fetch), \
             patch("time.sleep"):
            collector.update_prizes()

        # CSV 재로드 후 확인
        reloaded = LottoCollector(data_dir=tmp_data_dir).load_existing()
        assert len(reloaded) == 1
        assert reloaded[0].prize1Amount == 863_604_600
        assert reloaded[0].prize1Winners == 1

    def test_update_prizes_no_missing_rows_returns_zero(
        self,
        tmp_data_dir: Path,
    ) -> None:
        """모든 행에 prize 데이터가 있으면 0 반환 + API 호출 없음."""
        existing = [
            DrawResult(
                drwNo=1, date=datetime.date(2002, 12, 7),
                n1=10, n2=23, n3=29, n4=33, n5=37, n6=40, bonus=16,
                prize1Amount=863_604_600, prize1Winners=1,
            ),
        ]
        collector = LottoCollector(data_dir=tmp_data_dir)
        collector.save_csv(existing)

        fetch_calls: list[int] = []

        def _fake_fetch(drw_no: int) -> DrawResult | None:
            fetch_calls.append(drw_no)
            return None

        with patch.object(collector, "fetch_draw", side_effect=_fake_fetch), \
             patch("time.sleep"):
            updated = collector.update_prizes()

        assert updated == 0
        assert fetch_calls == []

    def test_update_prizes_empty_csv_returns_zero(self, tmp_data_dir: Path) -> None:
        """기존 CSV가 없을 때도 안전하게 0 반환."""
        collector = LottoCollector(data_dir=tmp_data_dir)
        with patch("time.sleep"):
            updated = collector.update_prizes()
        assert updated == 0

    def test_update_prizes_skips_failed_fetch(self, tmp_data_dir: Path) -> None:
        """API 재요청이 실패(None)한 행은 prize=None 으로 유지하고 카운트하지 않는다."""
        existing = [
            DrawResult(
                drwNo=1, date=datetime.date(2002, 12, 7),
                n1=10, n2=23, n3=29, n4=33, n5=37, n6=40, bonus=16,
                prize1Amount=None, prize1Winners=None,
            ),
        ]
        collector = LottoCollector(data_dir=tmp_data_dir)
        collector.save_csv(existing)

        with patch.object(collector, "fetch_draw", return_value=None), \
             patch("time.sleep"):
            updated = collector.update_prizes()

        assert updated == 0
        reloaded = LottoCollector(data_dir=tmp_data_dir).load_existing()
        assert reloaded[0].prize1Amount is None


# ─── REQ-PRIZE-C-002: 웹 API 통합 ─────────────────────────────────────


class TestCollectApiUpdatePrizes:
    """POST /api/collect?update_prizes=true 통합 테스트."""

    def test_collect_api_accepts_update_prizes_param(self, tmp_data_dir: Path) -> None:
        """update_prizes=true 파라미터가 라우터에서 수락되고 백그라운드 작업이 시작된다."""
        # 라우터 모듈을 직접 import하여 동기 호출
        from lotto.web import app as app_module
        from lotto.web.routes import api as api_module

        # 이전 상태 초기화
        with api_module._collect_lock:
            api_module._collect_state.update({
                "status": "idle", "current": 0, "total": 0,
                "collected": 0, "message": "",
            })

        client = TestClient(app_module.app)
        # update_prizes=true 호출은 정상 응답 (202)
        with patch.object(api_module, "_update_prizes_worker") as worker:
            res = client.post("/api/collect?update_prizes=true")
            assert res.status_code == 202
            body = res.json()
            assert body.get("status") == "started"
            # 백그라운드 작업이 update_prizes_worker로 라우팅됨
            assert worker.called


# ─── REQ-PRIZE-C-001: CSV 라운드트립 ──────────────────────────────────


class TestPrizeCsvRoundtrip:
    """prize 필드가 CSV 저장/로드 라운드트립을 통과한다."""

    def test_prize_amount_in_csv_roundtrip(self, tmp_data_dir: Path) -> None:
        """save_csv → load_existing 라운드트립 후 prize 값 일치."""
        draws = [
            DrawResult(
                drwNo=1, date=datetime.date(2002, 12, 7),
                n1=10, n2=23, n3=29, n4=33, n5=37, n6=40, bonus=16,
                prize1Amount=863_604_600, prize1Winners=1,
            ),
            DrawResult(
                drwNo=2, date=datetime.date(2002, 12, 14),
                n1=9, n2=13, n3=21, n4=25, n5=32, n6=42, bonus=2,
                prize1Amount=2_002_006_800, prize1Winners=1,
            ),
        ]
        collector = LottoCollector(data_dir=tmp_data_dir)
        collector.save_csv(draws)

        reloaded = LottoCollector(data_dir=tmp_data_dir).load_existing()
        assert len(reloaded) == 2
        assert reloaded[0].prize1Amount == 863_604_600
        assert reloaded[0].prize1Winners == 1
        assert reloaded[1].prize1Amount == 2_002_006_800
        assert reloaded[1].prize1Winners == 1


# ─── REQ-PRIZE-C-003: collect.html UI ─────────────────────────────────


class TestCollectPageRendersPrizeColumn:
    """수집 현황 페이지 템플릿이 prize1Amount 컬럼을 렌더링하는지."""

    def test_collect_page_has_prize_column_header(self, tmp_data_dir: Path) -> None:
        """렌더링된 HTML에 '1등 당첨금' 헤더가 포함된다."""
        from lotto.web import app as app_module

        client = TestClient(app_module.app)
        res = client.get("/collect")
        assert res.status_code == 200
        assert "1등 당첨금" in res.text

    def test_collect_page_renders_amount_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """prize1Amount가 있는 회차는 천 단위 콤마 포맷으로 표시된다."""
        from lotto.web import app as app_module
        from lotto.web.routes import pages as pages_module

        sample = [
            DrawResult(
                drwNo=1, date=datetime.date(2002, 12, 7),
                n1=10, n2=23, n3=29, n4=33, n5=37, n6=40, bonus=16,
                prize1Amount=863_604_600, prize1Winners=1,
            ),
        ]
        # pages.py가 모듈 수준에서 get_draws를 import하므로 해당 심볼을 패치
        monkeypatch.setattr(pages_module, "get_draws", lambda: sample)

        client = TestClient(app_module.app)
        res = client.get("/collect")
        assert res.status_code == 200
        # 콤마 포맷 (863,604,600) 이 화면에 노출되어야 함
        assert "863,604,600" in res.text
