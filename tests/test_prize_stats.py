"""SPEC-LOTTO-017: 당첨금 분석 대시보드 테스트 (RED phase)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lotto.collector import LottoCollector
from lotto.models import DrawResult

# ──────────────────────────────────────────────
# REQ-PRIZE-D-001: DrawResult 모델 확장 (Optional 필드)
# ──────────────────────────────────────────────


class TestDrawResultPrizeFields:
    """DrawResult 모델의 prize1Amount/prize1Winners 필드 테스트."""

    def test_draw_result_accepts_none_prize_fields(self) -> None:
        """기존 호출 방식 호환 — prize 필드 생략 시 기본 None."""
        draw = DrawResult(
            drwNo=1,
            date=date(2002, 12, 7),
            n1=1, n2=10, n3=20, n4=30, n5=40, n6=45,
            bonus=5,
        )
        assert draw.prize1Amount is None
        assert draw.prize1Winners is None

    def test_draw_result_accepts_large_prize_amount(self) -> None:
        """1등 당첨금은 수십억 단위 — 큰 정수 허용."""
        draw = DrawResult(
            drwNo=1100,
            date=date(2024, 1, 1),
            n1=1, n2=10, n3=20, n4=30, n5=40, n6=45,
            bonus=5,
            prize1Amount=5_000_000_000,
            prize1Winners=3,
        )
        assert draw.prize1Amount == 5_000_000_000
        assert draw.prize1Winners == 3

    def test_draw_result_explicit_none_prize_fields(self) -> None:
        """명시적 None 전달 시도 정상 처리."""
        draw = DrawResult(
            drwNo=1,
            date=date(2002, 12, 7),
            n1=1, n2=10, n3=20, n4=30, n5=40, n6=45,
            bonus=5,
            prize1Amount=None,
            prize1Winners=None,
        )
        assert draw.prize1Amount is None

    def test_draw_result_json_roundtrip_with_prize(self) -> None:
        """JSON 직렬화/역직렬화 시 prize 필드 보존."""
        draw = DrawResult(
            drwNo=1100,
            date=date(2024, 1, 1),
            n1=1, n2=10, n3=20, n4=30, n5=40, n6=45,
            bonus=5,
            prize1Amount=3_000_000_000,
            prize1Winners=10,
        )
        json_str = draw.model_dump_json()
        loaded = DrawResult.model_validate_json(json_str)
        assert loaded.prize1Amount == 3_000_000_000
        assert loaded.prize1Winners == 10

    def test_draw_result_json_roundtrip_without_prize(self) -> None:
        """기존 데이터(prize 없음) JSON 직렬화/역직렬화 보존."""
        draw = DrawResult(
            drwNo=1,
            date=date(2002, 12, 7),
            n1=1, n2=10, n3=20, n4=30, n5=40, n6=45,
            bonus=5,
        )
        json_str = draw.model_dump_json()
        loaded = DrawResult.model_validate_json(json_str)
        assert loaded.prize1Amount is None
        assert loaded.prize1Winners is None


# ──────────────────────────────────────────────
# REQ-PRIZE-D-001: CSV 하위 호환 (기존 컬럼 없는 CSV)
# ──────────────────────────────────────────────


class TestCollectorPrizeCSVCompat:
    """CSV 로드/저장 시 prize 필드 하위 호환 테스트."""

    def test_load_existing_legacy_csv_without_prize_columns(
        self, tmp_data_dir: Path
    ) -> None:
        """기존 컬럼만 있는 CSV 로드 시 prize 필드는 None 으로 채워진다."""
        csv_path = tmp_data_dir / "draws.csv"
        csv_path.write_text(
            "drwNo,date,n1,n2,n3,n4,n5,n6,bonus\n"
            "1,2002-12-07,10,23,29,33,37,40,16\n"
            "2,2002-12-14,9,13,21,25,32,42,2\n",
            encoding="utf-8",
        )

        collector = LottoCollector(data_dir=tmp_data_dir)
        draws = collector.load_existing()

        assert len(draws) == 2
        for d in draws:
            assert d.prize1Amount is None
            assert d.prize1Winners is None

    def test_save_csv_includes_prize_columns(self, tmp_data_dir: Path) -> None:
        """save_csv 가 새 prize 컬럼을 포함하여 저장한다."""
        collector = LottoCollector(data_dir=tmp_data_dir)
        draws = [
            DrawResult(
                drwNo=1,
                date=date(2002, 12, 7),
                n1=10, n2=23, n3=29, n4=33, n5=37, n6=40,
                bonus=16,
                prize1Amount=2_000_000_000,
                prize1Winners=4,
            ),
            DrawResult(
                drwNo=2,
                date=date(2002, 12, 14),
                n1=9, n2=13, n3=21, n4=25, n5=32, n6=42,
                bonus=2,
            ),  # no prize data
        ]
        collector.save_csv(draws)

        csv_text = (tmp_data_dir / "draws.csv").read_text(encoding="utf-8")
        # 헤더에 새 컬럼 포함
        assert "prize1Amount" in csv_text
        assert "prize1Winners" in csv_text

    def test_csv_round_trip_with_mixed_prize_data(self, tmp_data_dir: Path) -> None:
        """prize 데이터가 있는 회차와 없는 회차가 섞여 있어도 round-trip 정상."""
        collector = LottoCollector(data_dir=tmp_data_dir)
        original = [
            DrawResult(
                drwNo=1,
                date=date(2002, 12, 7),
                n1=10, n2=23, n3=29, n4=33, n5=37, n6=40,
                bonus=16,
                prize1Amount=2_000_000_000,
                prize1Winners=4,
            ),
            DrawResult(
                drwNo=2,
                date=date(2002, 12, 14),
                n1=9, n2=13, n3=21, n4=25, n5=32, n6=42,
                bonus=2,
            ),
        ]
        collector.save_csv(original)
        loaded = collector.load_existing()

        assert len(loaded) == 2
        assert loaded[0].prize1Amount == 2_000_000_000
        assert loaded[0].prize1Winners == 4
        assert loaded[1].prize1Amount is None
        assert loaded[1].prize1Winners is None


# ──────────────────────────────────────────────
# REQ-PRIZE-D-002: get_prize_stats() 함수
# ──────────────────────────────────────────────


class TestGetPrizeStats:
    """lotto.web.data.get_prize_stats() 단위 테스트."""

    def test_get_prize_stats_no_draws(self, monkeypatch, tmp_path: Path) -> None:
        """draws 자체가 없으면 total_draws=0, recent=[] 반환."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()
        # 캐시 무효화 후 함수 호출
        from lotto.web import data as wd

        # draws 가 None 인 상황 시뮬레이션
        monkeypatch.setattr(wd, "get_draws", lambda: None)

        result = wd.get_prize_stats()
        assert result["total_draws"] == 0
        assert result["draws_with_prize_data"] == 0
        assert result["avg_prize1"] is None
        assert result["max_prize1"] is None
        assert result["min_prize1"] is None
        assert result["recent"] == []

    def test_get_prize_stats_draws_without_prize_data(self, monkeypatch) -> None:
        """draws 는 있지만 prize 데이터가 모두 None 일 때."""
        from lotto.web import data as wd

        draws = [
            DrawResult(
                drwNo=i,
                date=date(2002, 12, 7),
                n1=1, n2=10, n3=20, n4=30, n5=40, n6=45,
                bonus=5,
            )
            for i in range(1, 4)
        ]
        monkeypatch.setattr(wd, "get_draws", lambda: draws)

        result = wd.get_prize_stats()
        assert result["total_draws"] == 3
        assert result["draws_with_prize_data"] == 0
        assert result["avg_prize1"] is None
        assert result["max_prize1"] is None
        assert result["min_prize1"] is None
        assert result["recent"] == []

    def test_get_prize_stats_with_prize_data(self, monkeypatch) -> None:
        """prize 데이터가 있는 회차들에 대해 avg/max/min 계산."""
        from lotto.web import data as wd

        draws = [
            DrawResult(
                drwNo=1,
                date=date(2024, 1, 1),
                n1=1, n2=10, n3=20, n4=30, n5=40, n6=45,
                bonus=5,
                prize1Amount=1_000_000_000,
                prize1Winners=10,
            ),
            DrawResult(
                drwNo=2,
                date=date(2024, 1, 8),
                n1=1, n2=10, n3=20, n4=30, n5=40, n6=45,
                bonus=5,
                prize1Amount=2_000_000_000,
                prize1Winners=5,
            ),
            DrawResult(
                drwNo=3,
                date=date(2024, 1, 15),
                n1=1, n2=10, n3=20, n4=30, n5=40, n6=45,
                bonus=5,
                prize1Amount=3_000_000_000,
                prize1Winners=2,
            ),
            # prize 데이터 없는 회차 — 통계에서 제외
            DrawResult(
                drwNo=4,
                date=date(2024, 1, 22),
                n1=1, n2=10, n3=20, n4=30, n5=40, n6=45,
                bonus=5,
            ),
        ]
        monkeypatch.setattr(wd, "get_draws", lambda: draws)

        result = wd.get_prize_stats()
        assert result["total_draws"] == 4
        assert result["draws_with_prize_data"] == 3
        assert result["avg_prize1"] == 2_000_000_000
        assert result["max_prize1"] == 3_000_000_000
        assert result["min_prize1"] == 1_000_000_000
        # recent 는 최대 20개 — prize 있는 회차만
        assert len(result["recent"]) == 3
        # 각 entry 키 검증
        for entry in result["recent"]:
            assert "drwNo" in entry
            assert "date" in entry
            assert "prize1Amount" in entry
            assert "prize1Winners" in entry
            assert entry["prize1Amount"] is not None

    def test_get_prize_stats_recent_limit_20(self, monkeypatch) -> None:
        """recent 는 prize 데이터 있는 회차 중 최근 20개로 제한."""
        from lotto.web import data as wd

        draws = [
            DrawResult(
                drwNo=i,
                date=date(2024, 1, 1),
                n1=1, n2=10, n3=20, n4=30, n5=40, n6=45,
                bonus=5,
                prize1Amount=1_000_000_000 + i * 1000,
                prize1Winners=i,
            )
            for i in range(1, 31)  # 30개 모두 prize 데이터 있음
        ]
        monkeypatch.setattr(wd, "get_draws", lambda: draws)

        result = wd.get_prize_stats()
        assert result["total_draws"] == 30
        assert result["draws_with_prize_data"] == 30
        assert len(result["recent"]) == 20


# ──────────────────────────────────────────────
# REQ-PRIZE-D-002: GET /api/prize-stats 엔드포인트
# ──────────────────────────────────────────────


@pytest.fixture
def api_client():
    """매 테스트 새 TestClient — 라우터는 모듈 공유."""
    from lotto.web.app import app

    return TestClient(app)


class TestPrizeStatsEndpoint:
    """GET /api/prize-stats 통합 테스트."""

    def test_prize_stats_endpoint_returns_200(
        self, api_client, monkeypatch
    ) -> None:
        """엔드포인트는 항상 200 반환 (데이터 부재 시에도)."""
        from lotto.web import data as wd

        monkeypatch.setattr(wd, "get_draws", lambda: None)

        response = api_client.get("/api/prize-stats")
        assert response.status_code == 200

    def test_prize_stats_endpoint_response_schema(
        self, api_client, monkeypatch
    ) -> None:
        """응답 스키마: total_draws/draws_with_prize_data/avg/max/min/recent."""
        from lotto.web import data as wd

        monkeypatch.setattr(wd, "get_draws", lambda: None)

        response = api_client.get("/api/prize-stats")
        body = response.json()
        assert "total_draws" in body
        assert "draws_with_prize_data" in body
        assert "avg_prize1" in body
        assert "max_prize1" in body
        assert "min_prize1" in body
        assert "recent" in body
        assert isinstance(body["recent"], list)

    def test_prize_stats_endpoint_with_data(
        self, api_client, monkeypatch
    ) -> None:
        """데이터가 있을 때 통계 값이 응답에 포함된다."""
        from lotto.web import data as wd

        draws = [
            DrawResult(
                drwNo=1,
                date=date(2024, 1, 1),
                n1=1, n2=10, n3=20, n4=30, n5=40, n6=45,
                bonus=5,
                prize1Amount=1_500_000_000,
                prize1Winners=8,
            ),
        ]
        monkeypatch.setattr(wd, "get_draws", lambda: draws)

        response = api_client.get("/api/prize-stats")
        body = response.json()
        assert body["total_draws"] == 1
        assert body["draws_with_prize_data"] == 1
        assert body["avg_prize1"] == 1_500_000_000
        assert body["max_prize1"] == 1_500_000_000
        assert body["min_prize1"] == 1_500_000_000
        assert len(body["recent"]) == 1
        assert body["recent"][0]["drwNo"] == 1


# ──────────────────────────────────────────────
# REQ-PRIZE-D-003: 홈 페이지 당첨금 카드
# ──────────────────────────────────────────────


class TestHomePageHasPrizeSection:
    """GET / 응답 HTML 에 prize 섹션이 포함된다."""

    def test_index_page_returns_200(self, api_client) -> None:
        response = api_client.get("/")
        assert response.status_code == 200

    def test_index_page_contains_prize_stats_section(self, api_client) -> None:
        """인덱스 HTML 에 '당첨금 통계' 또는 'prize-stats' 마커가 있어야 한다."""
        response = api_client.get("/")
        text = response.text
        # 한국어 라벨 또는 영문 식별자 중 하나는 포함되어야 한다
        assert ("당첨금 통계" in text) or ("prize-stats" in text)
