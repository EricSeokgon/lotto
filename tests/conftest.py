"""테스트 공통 픽스처."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from lotto.models import DrawResult


@pytest.fixture
def mini_draws() -> list[DrawResult]:
    """검증용 3회차 mini-dataset 픽스처.

    회차 1: 번호 1,10,20,30,40,45 / 보너스 5
    회차 2: 번호 1,10,15,25,35,44 / 보너스 3
    회차 3: 번호 1,2,3,10,11,12 / 보너스 7
    → 번호 1: 3회, 번호 10: 3회, 번호 7: 0회
    """
    return [
        DrawResult(
            drwNo=1, date=date(2002, 12, 7), n1=1, n2=10, n3=20, n4=30, n5=40, n6=45, bonus=5
        ),
        DrawResult(
            drwNo=2, date=date(2002, 12, 14), n1=1, n2=10, n3=15, n4=25, n5=35, n6=44, bonus=3
        ),
        DrawResult(
            drwNo=3, date=date(2002, 12, 21), n1=1, n2=2, n3=3, n4=10, n5=11, n6=12, bonus=7
        ),
    ]


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """임시 data 디렉토리 픽스처."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def fixtures_dir() -> Path:
    """tests/fixtures 디렉토리 경로."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def api_response_json(fixtures_dir: Path) -> dict[str, object]:
    """동행복권 API 응답 샘플 픽스처."""
    import json
    return json.loads((fixtures_dir / "api_response.json").read_text())
