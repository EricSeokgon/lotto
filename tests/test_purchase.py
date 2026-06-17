"""SPEC-LOTTO-014: purchase.py 단위 테스트."""

from __future__ import annotations

import json
from datetime import date

import pytest
from pydantic import ValidationError

from lotto.models import DrawResult
from lotto.purchase import (
    PurchaseCreate,
    PurchaseRecord,
    add_purchase,
    build_responses,
    calc_prize,
    delete_purchase,
    load_purchases,
    save_purchases,
)

# ─── PurchaseCreate 유효성 검사 ───────────────────────────────────────────────

class TestPurchaseCreate:
    def test_valid_numbers_sorted(self):
        pc = PurchaseCreate(drwNo=1, numbers=[45, 1, 23, 10, 5, 30])
        assert pc.numbers == sorted([45, 1, 23, 10, 5, 30])

    def test_wrong_count_raises(self):
        with pytest.raises(ValidationError):
            PurchaseCreate(drwNo=1, numbers=[1, 2, 3, 4, 5])

    def test_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            PurchaseCreate(drwNo=1, numbers=[0, 1, 2, 3, 4, 5])

    def test_out_of_range_high_raises(self):
        with pytest.raises(ValidationError):
            PurchaseCreate(drwNo=1, numbers=[1, 2, 3, 4, 5, 46])

    def test_duplicate_raises(self):
        with pytest.raises(ValidationError):
            PurchaseCreate(drwNo=1, numbers=[1, 1, 2, 3, 4, 5])

    def test_drw_no_ge1(self):
        with pytest.raises(ValidationError):
            PurchaseCreate(drwNo=0, numbers=[1, 2, 3, 4, 5, 6])


# ─── calc_prize ───────────────────────────────────────────────────────────────

@pytest.fixture
def draw_1() -> DrawResult:
    """회차 1: 번호 1,10,20,30,40,45 / 보너스 5."""
    return DrawResult(
        drwNo=1, date=date(2002, 12, 7),
        n1=1, n2=10, n3=20, n4=30, n5=40, n6=45, bonus=5,
    )


class TestCalcPrize:
    def test_pending_when_draw_is_none(self):
        rank, amount, matched, bonus = calc_prize([1, 2, 3, 4, 5, 6], None)
        assert rank == "pending"
        assert amount == 0
        assert matched == 0
        assert bonus is False

    def test_1st_all_six_match(self, draw_1):
        rank, amount, matched, bonus = calc_prize([1, 10, 20, 30, 40, 45], draw_1)
        assert rank == "1st"
        assert amount == 0
        assert matched == 6
        assert bonus is False

    def test_2nd_five_plus_bonus(self, draw_1):
        # 5개 일치(1,10,20,30,40) + 보너스(5) 일치
        rank, amount, matched, bonus = calc_prize([1, 5, 10, 20, 30, 40], draw_1)
        assert rank == "2nd"
        assert amount == 0
        assert matched == 5
        assert bonus is True

    def test_3rd_five_no_bonus(self, draw_1):
        # 5개 일치(1,10,20,30,40), 보너스(5) 불일치
        rank, amount, matched, bonus = calc_prize([1, 2, 10, 20, 30, 40], draw_1)
        assert rank == "3rd"
        assert amount == 1_500_000
        assert matched == 5
        assert bonus is False

    def test_4th_four_match(self, draw_1):
        rank, amount, matched, _ = calc_prize([1, 3, 10, 20, 30, 7], draw_1)
        assert rank == "4th"
        assert amount == 50_000
        assert matched == 4

    def test_5th_three_match(self, draw_1):
        # draw_1: 1,10,20,30,40,45 / 보너스 5 — 1,10,20이 일치 → 3개
        rank, amount, matched, _ = calc_prize([1, 2, 10, 3, 20, 8], draw_1)
        assert rank == "5th"
        assert amount == 5_000
        assert matched == 3

    def test_none_two_or_less(self, draw_1):
        rank, amount, matched, _ = calc_prize([2, 3, 4, 6, 7, 8], draw_1)
        assert rank == "none"
        assert amount == 0
        assert matched <= 2


# ─── load_purchases ───────────────────────────────────────────────────────────

class TestLoadPurchases:
    def test_file_not_exists_returns_empty(self, tmp_path):
        path = tmp_path / "purchases.json"
        assert load_purchases(path) == []

    def test_invalid_json_returns_empty(self, tmp_path):
        path = tmp_path / "purchases.json"
        path.write_text("not json", encoding="utf-8")
        assert load_purchases(path) == []

    def test_not_a_list_returns_empty(self, tmp_path):
        path = tmp_path / "purchases.json"
        path.write_text(json.dumps({"key": "value"}), encoding="utf-8")
        assert load_purchases(path) == []

    def test_validation_error_returns_empty(self, tmp_path):
        path = tmp_path / "purchases.json"
        # id 필드가 없는 잘못된 레코드
        path.write_text(json.dumps([{"drwNo": 1}]), encoding="utf-8")
        assert load_purchases(path) == []

    def test_valid_file_returns_records(self, tmp_path):
        path = tmp_path / "purchases.json"
        records = [
            {
                "id": 1,
                "drwNo": 1,
                "numbers": [1, 2, 3, 4, 5, 6],
                "purchased_at": "2024-01-01T00:00:00",
            },
        ]
        path.write_text(json.dumps(records), encoding="utf-8")
        result = load_purchases(path)
        assert len(result) == 1
        assert result[0].id == 1
        assert result[0].drwNo == 1


# ─── save_purchases ───────────────────────────────────────────────────────────

class TestSavePurchases:
    def test_saves_atomically(self, tmp_path):
        path = tmp_path / "data" / "purchases.json"
        records = [
            PurchaseRecord(
                id=1,
                drwNo=1,
                numbers=[1, 2, 3, 4, 5, 6],
                purchased_at="2024-01-01T00:00:00",
            ),
        ]
        save_purchases(path, records)
        assert path.exists()
        data = json.loads(path.read_text())
        assert len(data) == 1
        assert data[0]["id"] == 1

    def test_no_tmp_file_left(self, tmp_path):
        path = tmp_path / "purchases.json"
        save_purchases(path, [])
        tmp = path.with_suffix(".tmp")
        assert not tmp.exists()


# ─── add_purchase ─────────────────────────────────────────────────────────────

class TestAddPurchase:
    def test_first_purchase_gets_id_1(self, tmp_path):
        path = tmp_path / "purchases.json"
        record = add_purchase(path, drw_no=100, numbers=[1, 2, 3, 4, 5, 6])
        assert record.id == 1
        assert record.drwNo == 100
        assert record.numbers == [1, 2, 3, 4, 5, 6]

    def test_sequential_ids(self, tmp_path):
        path = tmp_path / "purchases.json"
        r1 = add_purchase(path, drw_no=1, numbers=[1, 2, 3, 4, 5, 6])
        r2 = add_purchase(path, drw_no=2, numbers=[7, 8, 9, 10, 11, 12])
        assert r1.id == 1
        assert r2.id == 2

    def test_numbers_sorted(self, tmp_path):
        path = tmp_path / "purchases.json"
        record = add_purchase(path, drw_no=1, numbers=[45, 1, 23, 10, 5, 30])
        assert record.numbers == sorted([45, 1, 23, 10, 5, 30])

    def test_purchased_at_not_empty(self, tmp_path):
        path = tmp_path / "purchases.json"
        record = add_purchase(path, drw_no=1, numbers=[1, 2, 3, 4, 5, 6])
        assert len(record.purchased_at) > 0


# ─── delete_purchase ──────────────────────────────────────────────────────────

class TestDeletePurchase:
    def test_existing_returns_true(self, tmp_path):
        path = tmp_path / "purchases.json"
        add_purchase(path, drw_no=1, numbers=[1, 2, 3, 4, 5, 6])
        assert delete_purchase(path, 1) is True
        assert load_purchases(path) == []

    def test_not_existing_returns_false(self, tmp_path):
        path = tmp_path / "purchases.json"
        assert delete_purchase(path, 999) is False

    def test_only_target_deleted(self, tmp_path):
        path = tmp_path / "purchases.json"
        add_purchase(path, drw_no=1, numbers=[1, 2, 3, 4, 5, 6])
        add_purchase(path, drw_no=2, numbers=[7, 8, 9, 10, 11, 12])
        delete_purchase(path, 1)
        remaining = load_purchases(path)
        assert len(remaining) == 1
        assert remaining[0].id == 2


# ─── build_responses ──────────────────────────────────────────────────────────

_AT = "2024-01-01T00:00:00"
_AT2 = "2024-01-02T00:00:00"


class TestBuildResponses:
    def test_empty_returns_empty(self):
        assert build_responses([], {}) == []

    def test_sorted_by_id_desc(self, draw_1):
        records = [
            PurchaseRecord(id=1, drwNo=1, numbers=[1, 2, 3, 4, 5, 6], purchased_at=_AT),
            PurchaseRecord(id=2, drwNo=1, numbers=[1, 10, 20, 30, 40, 45], purchased_at=_AT2),
        ]
        responses = build_responses(records, {1: draw_1})
        assert responses[0].id == 2
        assert responses[1].id == 1

    def test_pending_when_draw_missing(self):
        records = [
            PurchaseRecord(id=1, drwNo=999, numbers=[1, 2, 3, 4, 5, 6], purchased_at=_AT),
        ]
        responses = build_responses(records, {})
        assert responses[0].prize_rank == "pending"
        assert responses[0].matched_count == 0

    def test_1st_prize_calculated(self, draw_1):
        records = [
            PurchaseRecord(
                id=1, drwNo=1, numbers=[1, 10, 20, 30, 40, 45], purchased_at=_AT,
            ),
        ]
        responses = build_responses(records, {1: draw_1})
        assert responses[0].prize_rank == "1st"
        assert responses[0].matched_count == 6

    def test_3rd_prize_amount(self, draw_1):
        # 5개 일치, 보너스 불일치
        records = [
            PurchaseRecord(
                id=1, drwNo=1, numbers=[1, 2, 10, 20, 30, 40], purchased_at=_AT,
            ),
        ]
        responses = build_responses(records, {1: draw_1})
        assert responses[0].prize_rank == "3rd"
        assert responses[0].prize_amount == 1_500_000
