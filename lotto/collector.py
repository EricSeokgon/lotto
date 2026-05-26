"""LottoCollector — 동행복권 API 데이터 수집."""

from __future__ import annotations

import contextlib
import datetime
import json
import os
import tempfile
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path

import pandas as pd
import requests

from lotto.config import settings
from lotto.models import DrawResult

# SPEC-LOTTO-002: 설정 외부화 — LOTTO_API_URL / LOTTO_DATA_DIR 환경 변수로 오버라이드 가능
API_URL = settings.api_url
DEFAULT_DATA_DIR = settings.data_dir
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
        """기존 데이터 이후 신규 회차를 수집합니다.

        SPEC-LOTTO-007: 신규 회차만 append 모드로 추가하여 O(N) 재작성을 회피하고,
        수집 완료(또는 abort)로 디스크에 데이터가 남는 경우 last_sync.json을 기록합니다.
        """
        existing = self.load_existing()
        start = max(d.drwNo for d in existing) + 1 if existing else 1

        collected = list(existing)
        new_only: list[DrawResult] = []  # 이번 호출에서 새로 수집된 회차만
        consecutive_failures = 0

        drw_no = start
        while drw_no <= latest_drw_no:
            draw = self.fetch_draw(drw_no)
            time.sleep(0.2)
            if draw is None:
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    # 부분 수집분을 append로만 기록 (기존 행 재작성 방지)
                    self.append_draws(new_only)
                    self._write_last_sync(collected)
                    raise CollectAbortError(
                        f"{MAX_CONSECUTIVE_FAILURES}회 연속 실패로 수집을 중단합니다."
                    )
            else:
                consecutive_failures = 0
                collected.append(draw)
                new_only.append(draw)
            drw_no += 1

        self.append_draws(new_only)
        self._write_last_sync(collected)
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

    # @MX:NOTE: [AUTO] SPEC-LOTTO-007 REQ-SYNC-004 — 데이터 갭(누락 회차) 감지
    def detect_gaps(self, draws: list[DrawResult] | None = None) -> list[int]:
        """회차 데이터에서 누락된 회차 번호를 오름차순으로 반환합니다.

        Args:
            draws: 검사할 회차 목록. None이면 load_existing() 결과를 사용합니다.

        Returns:
            min~max 구간에서 누락된 회차 번호 리스트. 0~1개 회차이거나 갭이 없으면 빈 리스트.
        """
        if draws is None:
            draws = self.load_existing()
        if len(draws) < 2:
            return []
        nos = sorted(d.drwNo for d in draws)
        existing = set(nos)
        return [n for n in range(nos[0] + 1, nos[-1]) if n not in existing]

    # @MX:NOTE: [AUTO] SPEC-LOTTO-007 REQ-SYNC-003 — last_sync.json 메타데이터 기록
    def _write_last_sync(self, draws: list[DrawResult]) -> None:
        """수집 메타데이터(last_sync.json)를 기록합니다.

        디스크에 데이터가 한 건도 없으면 메타파일을 생성하지 않습니다.
        """
        if not draws:
            return
        meta = {
            "last_round": max(d.drwNo for d in draws),
            "synced_at": datetime.datetime.now().isoformat(),
            "total_rounds": len(draws),
        }
        self._data_dir.mkdir(parents=True, exist_ok=True)
        meta_path = self._data_dir / "last_sync.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False))

    # @MX:ANCHOR: [AUTO] SPEC-LOTTO-007 REQ-SYNC-002 — 신규 회차 append (전체 재작성 회피)
    # @MX:REASON: collect_new 경로에서 O(N) 재작성을 막아 누적 회차가 많을 때 I/O 비용을 줄임
    def append_draws(self, new_draws: list[DrawResult]) -> None:
        """신규 DrawResult를 append 모드로 CSV에 추가합니다.

        - 빈 입력이면 파일을 건드리지 않습니다.
        - 이미 존재하는 drwNo는 중복 추가하지 않습니다.
        - CSV가 없으면 헤더 포함하여 새로 생성합니다.
        """
        if not new_draws:
            return

        # 중복 제거: 기존 회차 번호 집합과 비교
        existing_nos: set[int] = set()
        if self._csv_path.exists():
            existing_nos = {d.drwNo for d in self.load_existing()}

        to_add = [d for d in new_draws if d.drwNo not in existing_nos]
        if not to_add:
            return

        self._data_dir.mkdir(parents=True, exist_ok=True)
        df = self._to_dataframe(to_add)
        write_header = not self._csv_path.exists()
        df.to_csv(self._csv_path, mode="a", header=write_header, index=False)

    # @MX:ANCHOR: [AUTO] DrawResult → DataFrame 변환 헬퍼 (save_csv/append_draws 공용)
    # @MX:REASON: 두 저장 경로가 동일한 컬럼 순서를 유지해야 데이터 무결성이 보장됨
    def _to_dataframe(self, draws: list[DrawResult]) -> pd.DataFrame:
        """DrawResult 목록을 DataFrame으로 변환합니다."""
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
        return pd.DataFrame(rows)

    # @MX:ANCHOR: [AUTO] SPEC-LOTTO-007 REQ-SYNC-001 — 원자적 CSV 저장
    # @MX:REASON: 부분 쓰기로 인한 CSV 손상을 방지하고 기존 데이터 유실을 막아야 함
    def save_csv(self, draws: list[DrawResult]) -> None:
        """DrawResult 목록을 CSV로 원자적으로 저장합니다.

        임시 파일에 먼저 기록한 뒤 os.replace로 최종 경로에 교체합니다.
        도중 실패 시 임시 파일을 정리하고 원본 CSV(존재한다면)를 보존합니다.
        """
        self._data_dir.mkdir(parents=True, exist_ok=True)
        df = self._to_dataframe(draws)

        # 임시 파일은 동일 디렉토리에 생성해야 os.replace가 원자적으로 동작
        fd, tmp_path = tempfile.mkstemp(
            dir=self._data_dir, prefix="draws_", suffix=".tmp"
        )
        try:
            os.close(fd)
            df.to_csv(tmp_path, index=False)
            os.replace(tmp_path, self._csv_path)
        except Exception:
            # 임시 파일을 정리하고 원본 CSV는 그대로 둔다
            if os.path.exists(tmp_path):  # pragma: no branch
                with contextlib.suppress(OSError):
                    os.unlink(tmp_path)
            raise
