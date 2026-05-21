"""SPEC-LOTTO-007 REQ-SYNC-003: last_sync.json 메타데이터 기록 테스트."""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from unittest.mock import patch

import requests_mock as rm

from lotto.collector import LottoCollector

API_URL_PATTERN = "https://www.dhlottery.co.kr/common.do"


def _make_success_response(drw_no: int) -> dict[str, object]:
    """드로우 회차에 대한 성공 응답 페이로드."""
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


class TestLastSyncMetadata:
    """수집 후 last_sync.json 파일 기록을 검증한다."""

    def test_last_sync_written_after_collect(
        self, requests_mock: rm.Mocker, tmp_data_dir: Path
    ) -> None:
        """정상 수집 완료 시 last_sync.json이 생성된다."""
        requests_mock.get(
            API_URL_PATTERN,
            [
                {"json": _make_success_response(1)},
                {"json": _make_success_response(2)},
            ],
        )
        collector = LottoCollector(data_dir=tmp_data_dir)
        with patch("time.sleep"):
            collector.collect_new(latest_drw_no=2)

        meta_path = tmp_data_dir / "last_sync.json"
        assert meta_path.exists()

    def test_last_sync_json_structure(
        self, requests_mock: rm.Mocker, tmp_data_dir: Path
    ) -> None:
        """메타파일에 last_round, synced_at, total_rounds 필드가 존재한다."""
        requests_mock.get(
            API_URL_PATTERN,
            [
                {"json": _make_success_response(1)},
                {"json": _make_success_response(2)},
            ],
        )
        collector = LottoCollector(data_dir=tmp_data_dir)
        with patch("time.sleep"):
            collector.collect_new(latest_drw_no=2)

        meta = json.loads((tmp_data_dir / "last_sync.json").read_text())
        assert "last_round" in meta
        assert "synced_at" in meta
        assert "total_rounds" in meta
        assert isinstance(meta["last_round"], int)
        assert isinstance(meta["synced_at"], str)
        assert isinstance(meta["total_rounds"], int)
        # ISO 8601 파싱 가능해야 한다
        datetime.datetime.fromisoformat(meta["synced_at"])
        assert meta["last_round"] == 2
        assert meta["total_rounds"] == 2

    def test_last_sync_updated_on_subsequent_collect(
        self, requests_mock: rm.Mocker, tmp_data_dir: Path
    ) -> None:
        """후속 수집 시 last_round가 갱신된다."""
        # 1차: 회차 1,2 수집
        requests_mock.get(
            API_URL_PATTERN,
            [
                {"json": _make_success_response(1)},
                {"json": _make_success_response(2)},
            ],
        )
        collector = LottoCollector(data_dir=tmp_data_dir)
        with patch("time.sleep"):
            collector.collect_new(latest_drw_no=2)

        meta1 = json.loads((tmp_data_dir / "last_sync.json").read_text())
        assert meta1["last_round"] == 2

        # 2차: 회차 3 수집 (mock 리셋 후 재구성)
        requests_mock.reset()
        requests_mock.get(
            API_URL_PATTERN,
            [{"json": _make_success_response(3)}],
        )
        with patch("time.sleep"):
            collector.collect_new(latest_drw_no=3)

        meta2 = json.loads((tmp_data_dir / "last_sync.json").read_text())
        assert meta2["last_round"] == 3
        assert meta2["total_rounds"] == 3

    def test_no_meta_when_no_data(
        self, requests_mock: rm.Mocker, tmp_data_dir: Path
    ) -> None:
        """수집된 회차가 0건이면 메타파일을 생성하지 않는다 (디스크에 데이터가 없는 경우)."""
        # latest_drw_no를 기존보다 작게 호출하여 새 회차 0건이 되도록 한다.
        # existing이 비어 있고 latest=0이면 while 루프가 한 번도 실행되지 않음.
        collector = LottoCollector(data_dir=tmp_data_dir)
        with patch("time.sleep"):
            result = collector.collect_new(latest_drw_no=0)

        assert result == []
        assert not (tmp_data_dir / "last_sync.json").exists()
