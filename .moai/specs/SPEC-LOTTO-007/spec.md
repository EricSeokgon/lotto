# SPEC-LOTTO-007: 데이터 동기화 안정성 개선

## 개요

LottoCollector의 데이터 동기화 흐름(저장/적재/메타데이터)을 안정화하여, 부분 쓰기로 인한 CSV 손상을 방지하고, 신규 회차 적재 시 전체 재작성에 따른 I/O 비용을 줄이며, 수집 상태와 데이터 갭(누락 회차)을 운영자가 추적할 수 있도록 한다.

## 배경

현재 `LottoCollector.save_csv()`는 매번 전체 CSV를 덮어쓰는 방식이라 다음 문제가 있다.

1. **부분 쓰기 위험**: `df.to_csv(self._csv_path, ...)` 도중 프로세스가 중단되면 원본 CSV가 손상되어 이전까지의 누적 데이터가 유실될 수 있다.
2. **O(N) 재작성 비용**: `collect_new()`에서 새 회차 1~2개만 추가하는 경우에도 기존 1,200+ 회차를 포함한 전체 CSV를 다시 쓴다.
3. **운영 가시성 부재**: 마지막 수집 시각/회차를 별도로 기록하지 않아, 데이터의 최신성 판단이 어렵다.
4. **데이터 갭 감지 부재**: 5회 연속 실패로 중간이 비어도 후속 호출에서 갭을 인지할 수단이 없다.

이번 SPEC은 (1) 원자적 저장, (2) append 모드 신규 회차 추가, (3) `last_sync.json` 메타데이터 기록, (4) 갭 감지 메서드 네 가지를 도입하여 데이터 동기화 신뢰성을 한 단계 끌어올린다.

## 요구사항 (EARS 형식)

### Ubiquitous (시스템 전역)

- **REQ-SYNC-001**: `LottoCollector.save_csv()`는 원자적으로 저장해야 한다. 임시 파일에 먼저 기록한 뒤 `os.replace()`로 최종 경로에 교체하며, 도중 실패 시 임시 파일을 정리하고 원본 CSV(존재한다면)를 그대로 보존해야 한다.
- **REQ-SYNC-002**: 신규 회차만 추가하는 경로(`collect_new`)에서는 전체 CSV를 재작성하지 않고 append 모드(`mode="a"`)로 신규 행만 기록해야 한다. 신규 행이 없으면 파일을 건드리지 않는다.

### Event-driven (이벤트 기반)

- **REQ-SYNC-003**: `collect_new()`가 정상 종료되거나 abort로 종료되더라도 디스크에 데이터가 남는 경우, 시스템은 `last_sync.json` 메타데이터 파일을 `data_dir`에 기록해야 한다. 파일에는 `last_round`(int), `synced_at`(ISO 8601 datetime), `total_rounds`(int) 필드가 포함된다.

### Optional / 확장

- **REQ-SYNC-004**: `LottoCollector.detect_gaps(draws=None)` 메서드가 존재해야 한다. 인자가 `None`이면 `load_existing()`을 사용하며, 회차 번호의 최소~최대 구간에서 누락된 회차 번호 리스트를 오름차순으로 반환한다. 회차가 0~1개이거나 갭이 없으면 빈 리스트를 반환한다.

### 비기능 요구사항 (NFR)

- **NFR-SYNC-001**: `collect_new()`의 외부 인터페이스(시그니처, 반환 타입, 예외 동작)는 변경하지 않는다. 호출 측 코드(CLI, 웹 라우터)와 기존 테스트는 수정 없이 동작해야 한다.
- **NFR-SYNC-002**: 본 SPEC의 모든 신규 동작은 Python 3.9 호환이어야 한다(`zip(strict=True)` 금지, `match` 문 금지). 코드 주석은 한국어를 유지한다.
- **NFR-SYNC-003**: 기존 360개 테스트가 모두 통과해야 하며, 전체 커버리지는 95% 이상을 유지한다.

## 범위

### In Scope
- `lotto/collector.py`
  - `save_csv()` 원자적 저장으로 변경
  - 신규 메서드 `append_draws()` 추가 (중복 제거 포함)
  - `collect_new()` 내부에서 신규 회차 적재 시 `append_draws()` 사용
  - 신규 메서드 `detect_gaps()` 추가
  - 정상/실패 종료 후 `last_sync.json` 기록 로직
- 신규 테스트 파일
  - `tests/test_collector_atomic.py`
  - `tests/test_collector_append.py`
  - `tests/test_collector_sync_meta.py`
  - `tests/test_collector_gaps.py`

### Out of Scope
- 파일 시스템 잠금(파일 락) — 단일 프로세스 가정
- 분산/병렬 수집 — 별도 SPEC에서 검토
- 갭 자동 보충 수집 — `detect_gaps()`는 조회 기능만 제공
- CSV 외 저장 포맷(Parquet 등) — 별도 SPEC

## 의존성

- 기존 모듈: `lotto.collector.LottoCollector`, `lotto.models.DrawResult`
- 표준 라이브러리: `tempfile`, `os`, `json`, `datetime`
- 기존 테스트 픽스처: `tmp_data_dir`, `mini_draws`, `requests_mock`

## 참고

- SPEC-LOTTO-001: 로또 번호 추천 CLI (collector.py 최초 도입)
- SPEC-LOTTO-002: 설정 외부화 (data_dir 환경변수)

---

Version: 1.0.0
Status: completed
Created: 2026-05-21
