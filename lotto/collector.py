"""LottoCollector — 동행복권 API 데이터 수집."""

from __future__ import annotations

import datetime
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from lotto.models import DrawResult

API_URL = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={drw_no}"
DEFAULT_DATA_DIR = Path("data")
DEFAULT_CSV_PATH = DEFAULT_DATA_DIR / "draws.csv"
REQUEST_DELAY_MS = 200
MAX_CONSECUTIVE_FAILURES = 5
RETRY_DELAYS = [1.0, 2.0, 4.0]


class CollectAbortError(Exception):
    """5회 연속 API 실패로 수집을 중단합니다."""


class LottoCollector:
    """동행복권 API에서 당첨 번호를 수집합니다."""

    def __init__(
        self,
        data_dir: Path = DEFAULT_DATA_DIR,
        session: requests.Session | None = None,
    ) -> None:
        self._data_dir = data_dir
        self._csv_path = data_dir / "draws.csv"
        self._session = session or requests.Session()

    # @MX:WARN: [AUTO] HTTP 재시도 로직 — 외부 API 의존성 및 sleep 사용
    # @MX:REASON: 지수 백오프로 과부하 방지. time.sleep은 테스트에서 반드시 mock 필요.
    def _fetch_with_retry(self, drw_no: int) -> dict[str, Any] | None:
        """지수 백오프(1s/2s/4s)로 최대 3회 재시도합니다."""
        url = API_URL.format(drw_no=drw_no)
        for delay in RETRY_DELAYS:
            try:
                resp = self._session.get(url, timeout=10)
                resp.raise_for_status()
                return resp.json()  # type: ignore[no-any-return]
            except (requests.RequestException, ValueError):
                time.sleep(delay)
        return None

    def fetch_draw(self, drw_no: int) -> DrawResult | None:
        """단일 회차 데이터를 API에서 가져옵니다. 실패 시 None 반환."""
        data = self._fetch_with_retry(drw_no)
        if data is None:
            return None
        if data.get("returnValue") != "success":
            return None
        try:
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
            )
        except (KeyError, ValueError):
            return None

    def load_existing(self) -> list[DrawResult]:
        """기존 CSV에서 DrawResult 목록을 로드합니다."""
        if not self._csv_path.exists():
            return []
        df = pd.read_csv(self._csv_path)
        results = []
        for _, row in df.iterrows():
            results.append(
                DrawResult(
                    drwNo=int(row["drwNo"]),
                    date=datetime.date.fromisoformat(str(row["date"])),
                    n1=int(row["n1"]),
                    n2=int(row["n2"]),
                    n3=int(row["n3"]),
                    n4=int(row["n4"]),
                    n5=int(row["n5"]),
                    n6=int(row["n6"]),
                    bonus=int(row["bonus"]),
                )
            )
        return results

    def collect_new(self, latest_drw_no: int) -> list[DrawResult]:
        """기존 데이터 이후 신규 회차를 수집합니다."""
        existing = self.load_existing()
        start = max(d.drwNo for d in existing) + 1 if existing else 1

        collected = list(existing)
        consecutive_failures = 0

        drw_no = start
        while drw_no <= latest_drw_no:
            draw = self.fetch_draw(drw_no)
            time.sleep(0.2)
            if draw is None:
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    self.save_csv(collected)
                    raise CollectAbortError(
                        f"{MAX_CONSECUTIVE_FAILURES}회 연속 실패로 수집을 중단합니다."
                    )
            else:
                consecutive_failures = 0
                collected.append(draw)
            drw_no += 1

        self.save_csv(collected)
        return collected

    def collect_full(self, max_drw_no: int = 1200) -> list[DrawResult]:
        """전체 히스토리를 재수집합니다 (사용자 확인 후 호출)."""
        collected: list[DrawResult] = []
        consecutive_failures = 0

        for drw_no in range(1, max_drw_no + 1):
            draw = self.fetch_draw(drw_no)
            time.sleep(0.2)
            if draw is None:
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    self.save_csv(collected)
                    raise CollectAbortError(
                        f"{MAX_CONSECUTIVE_FAILURES}회 연속 실패로 수집을 중단합니다."
                    )
            else:
                consecutive_failures = 0
                collected.append(draw)

        self.save_csv(collected)
        return collected

    def save_csv(self, draws: list[DrawResult]) -> None:
        """DrawResult 목록을 CSV로 저장합니다."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        rows = [
            {
                "drwNo": d.drwNo,
                "date": d.date.isoformat(),
                "n1": d.n1,
                "n2": d.n2,
                "n3": d.n3,
                "n4": d.n4,
                "n5": d.n5,
                "n6": d.n6,
                "bonus": d.bonus,
            }
            for d in draws
        ]
        df = pd.DataFrame(rows)
        df.to_csv(self._csv_path, index=False)
