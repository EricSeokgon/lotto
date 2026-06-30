"""SPEC-LOTTO-132: 연속 번호 패턴 분석 테스트."""

from __future__ import annotations

import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd


def _make_draw(drw_no: int, nums: list[int], bonus: int = 7) -> DrawResult:
    """6개 본번호로 DrawResult를 만든다."""
    n1, n2, n3, n4, n5, n6 = nums
    return DrawResult(
        drwNo=drw_no,
        date=datetime.date(2002, 12, 7) + datetime.timedelta(days=7 * drw_no),
        n1=n1, n2=n2, n3=n3, n4=n4, n5=n5, n6=n6, bonus=bonus,
    )


def _fixture_draws() -> list[DrawResult]:
    """테스트용 픽스처.

    D1 [1,10,20,30,40,45]  → 연속 없음 (pairs=0)
    D2 [1,2,10,15,16,30]   → (1-2), (15-16) → pairs=2
    D3 [5,6,7,20,30,40]    → (5-6-7) → pairs=2, max_run=3
    """
    return [
        _make_draw(1, [1, 10, 20, 30, 40, 45]),
        _make_draw(2, [1, 2, 10, 15, 16, 30]),
        _make_draw(3, [5, 6, 7, 20, 30, 40]),
    ]


def test_returns_none_when_empty() -> None:
    """데이터가 없으면 None 반환."""
    with patch.object(wd, "get_draws", return_value=[]):
        result = wd.get_consecutive_analysis()
    assert result is None


def test_returns_dict() -> None:
    """정상 데이터 → dict 반환."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        result = wd.get_consecutive_analysis()
    assert isinstance(result, dict)


def test_required_keys() -> None:
    """필수 키 포함 여부 확인."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        result = wd.get_consecutive_analysis()
    assert result is not None
    for key in ("total", "no_consec", "has_consec", "best_pair_count",
                "pair_dist_list", "max_run_list", "top_pairs", "recent"):
        assert key in result, f"필수 키 누락: {key}"


def test_no_consec_plus_has_consec_equals_total() -> None:
    """no_consec + has_consec == total."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        result = wd.get_consecutive_analysis()
    assert result is not None
    assert result["no_consec"] + result["has_consec"] == result["total"]


def test_pair_dist_sum_equals_total() -> None:
    """pair_dist_list count 합계 == total."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        result = wd.get_consecutive_analysis()
    assert result is not None
    count_sum = sum(item["count"] for item in result["pair_dist_list"])
    assert count_sum == result["total"]


def test_top_pairs_max_20() -> None:
    """top_pairs는 최대 20개."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        result = wd.get_consecutive_analysis()
    assert result is not None
    assert len(result["top_pairs"]) <= 20


def test_recent_length_lte_20() -> None:
    """recent 항목 수 <= 20."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        result = wd.get_consecutive_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_recent_has_runs_key() -> None:
    """recent 각 항목에 runs 키가 있어야 한다."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        result = wd.get_consecutive_analysis()
    assert result is not None
    for item in result["recent"]:
        assert "runs" in item, "recent 항목에 runs 키 없음"
        assert "pair_count" in item, "recent 항목에 pair_count 키 없음"


def test_consecutive_detected_correctly() -> None:
    """[1,2,10,20,30,40] 회차에서 연속 쌍이 최소 1개 이상 감지되어야 한다."""
    draws = [_make_draw(1, [1, 2, 10, 20, 30, 40])]
    with patch.object(wd, "get_draws", return_value=draws):
        result = wd.get_consecutive_analysis()
    assert result is not None
    assert result["has_consec"] == 1
    assert result["no_consec"] == 0
    # recent의 첫 항목에 runs가 존재해야 함
    item = result["recent"][0]
    assert item["pair_count"] >= 1
    assert len(item["runs"]) >= 1


def test_consecutive_page_200() -> None:
    """GET /stats/consecutive → HTTP 200."""
    from lotto.web.app import app
    client = TestClient(app)
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = client.get("/stats/consecutive")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
