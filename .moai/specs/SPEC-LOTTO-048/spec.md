---
id: SPEC-LOTTO-048
version: 0.1.0
status: completed
created: 2026-06-02
updated: 2026-06-02
author: ircp
priority: medium
---

# SPEC-LOTTO-048: 시뮬레이션 결과 저장/비교

## 개요

사용자가 백테스팅 시뮬레이션 실행 결과(전략, 번호, 결과 통계)를 라벨과 함께
저장하고, 저장된 결과 목록을 조회/삭제하며, 여러 결과를 나란히 비교할 수 있게 한다.

기존 읽기 전용 분석 기능들과 달리 이 기능은 **사용자 데이터를 디스크에 영속**한다.
즐겨찾기(SPEC-LOTTO-016)/예약(SPEC-LOTTO-035)과 동일한 저장 규약을 따른다.

## 배경 (Why)

- 시뮬레이션 결과는 회차/전략에 따라 달라지지만, 화면을 벗어나면 사라진다.
- 사용자는 서로 다른 전략의 백테스트 결과를 보관하고 비교하고 싶어 한다.
- 별도 DB 없이 기존 JSON 파일 저장 규약(`settings.data_dir`)을 재사용하여 단순하게 구현한다.

## 요구사항 (EARS)

### Ubiquitous (상시)

- **REQ-SIM-001**: 시스템은 저장된 시뮬레이션 결과를 `settings.data_dir / "sim_history.json"`
  에 JSON 배열로 보관해야 한다 (즐겨찾기/예약과 동일 규약).
- **REQ-SIM-002**: 각 저장 엔트리는 `id`(8자리 hex), `label`, `strategy`, `numbers`,
  `iterations`, `rank_counts`, `total_spent`, `total_won`, `roi`, `created_at`
  (UTC ISO-8601) 필드를 가진다.
- **REQ-SIM-003**: 시스템은 최대 50건만 보관하며, 초과 시 가장 오래된 항목부터 제거한다.

### Event-driven (이벤트)

- **REQ-SIM-010**: 사용자가 `POST /api/simulation-history`로 결과를 저장하면,
  시스템은 `id`/`created_at`을 부여하여 저장하고 200과 저장 엔트리를 반환한다.
- **REQ-SIM-011**: 사용자가 `GET /api/simulation-history`를 요청하면,
  시스템은 저장된 결과를 최신순(newest-first) 배열로 200 반환한다.
- **REQ-SIM-012**: 사용자가 `DELETE /api/simulation-history/{result_id}`를 요청하면,
  시스템은 해당 결과를 삭제하고 200 `{"deleted": true}`를 반환한다.
- **REQ-SIM-013**: 사용자가 `GET /simulation-history` 페이지를 요청하면,
  시스템은 저장 결과를 카드로 표시(등수 분포 + ROI)하고, 삭제·비교 UI를 제공한다.

### Unwanted (금지/오류)

- **REQ-SIM-020**: 라벨이 비어 있으면(공백 trim 후 빈 문자열) 시스템은 422를 반환해야 한다.
- **REQ-SIM-021**: 존재하지 않는 `result_id` 삭제 요청에 대해 시스템은 404를 반환해야 한다.
- **REQ-SIM-022**: `sim_history.json`이 손상되었거나 최상위가 list가 아니면,
  시스템은 예외를 전파하지 않고 빈 목록으로 처리해야 한다.

### State-driven (상태)

- **REQ-SIM-030**: 저장된 결과가 없는 동안 `GET /simulation-history` 페이지는
  빈 상태 안내("저장된 시뮬레이션 결과가 없습니다")를 표시해야 한다.

## 제외 범위 (Out of Scope)

- 데이터베이스(RDB/NoSQL) 사용 — JSON 파일 저장만 사용한다.
- 실시간 동기화/멀티 유저 동시성 — 단일 서버 프로세스를 가정한다.
- 시뮬레이션 자체 실행 로직 변경 — 기존 `lotto/simulator.py` 출력을 그대로 저장한다.

## 영속화/격리 요구사항

- 저장은 tempfile + `os.replace` 원자적 쓰기 패턴을 사용한다 (쓰기 중단 시 기존 파일 보존).
- 테스트는 `lotto.web.data._SIM_HISTORY_PATH`를 `tmp_path`로 monkeypatch하여
  실제 사용자 데이터 파일을 오염시키지 않고 결정론적으로 동작해야 한다.

## 관련

- 저장 규약 참조: SPEC-LOTTO-016(favorites), SPEC-LOTTO-035(reservations), SPEC-LOTTO-033(gen_history)
- 시뮬레이션 출력: SPEC-LOTTO-002(simulator), SPEC-LOTTO-032(strategy compare)
