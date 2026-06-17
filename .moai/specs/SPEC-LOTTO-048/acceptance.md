---
id: SPEC-LOTTO-048
version: 0.1.0
status: Planned
created: 2026-06-02
updated: 2026-06-02
author: ircp
priority: medium
---

# SPEC-LOTTO-048 인수 기준

## 영속화 (tests/test_sim_history.py)

- **AC-01**: `save_simulation_result(entry)`는 8자리 `id`와 `created_at`(ISO, "T" 포함)을
  부여한 엔트리를 반환한다. → REQ-SIM-002, REQ-SIM-010
- **AC-02**: `list_simulation_results()`는 최신 저장이 맨 앞에 오는 순서로 반환한다. → REQ-SIM-011
- **AC-03**: 저장이 없을 때 `list_simulation_results()`는 빈 리스트를 반환한다. → REQ-SIM-030
- **AC-04**: `delete_simulation_result(id)`는 존재 시 True를 반환하고 목록에서 제거한다. → REQ-SIM-012
- **AC-05**: 존재하지 않는 id 삭제 시 False를 반환한다. → REQ-SIM-021
- **AC-06**: `get_simulation_result(id)`는 단건을 반환하고, 없으면 None을 반환한다. → REQ-SIM-002
- **AC-07**: 디스크 왕복(write → read) 후에도 `rank_counts`/`roi`가 보존된다. → REQ-SIM-001

## API (tests/test_api_sim_history.py)

- **AC-10**: `POST /api/simulation-history` 유효 본문 → 200 + id/created_at 포함 엔트리. → REQ-SIM-010
- **AC-11**: 빈 라벨 `POST` → 422. → REQ-SIM-020
- **AC-12**: `GET /api/simulation-history` → 200 + 최신순 배열. → REQ-SIM-011
- **AC-13**: 존재하는 id `DELETE` → 200 `{"deleted": true}`. → REQ-SIM-012
- **AC-14**: 존재하지 않는 id `DELETE` → 404. → REQ-SIM-021

## 페이지 (tests/test_sim_history_page.py)

- **AC-15**: `GET /simulation-history` → 200 HTML, "시뮬레이션 기록" 제목 포함. → REQ-SIM-013
- **AC-16**: 저장된 결과가 있으면 라벨이 페이지에 노출된다. → REQ-SIM-013
- **AC-17**: 저장된 결과가 없으면 "저장된 시뮬레이션 결과가 없습니다" 빈 상태가 노출된다. → REQ-SIM-030
- **AC-18**: `GET /` 응답 HTML에 `href="/simulation-history"` 네비 링크가 포함된다. → REQ-SIM-013

## 품질

- **AC-Q1**: 전체 테스트 통과 (기존 1126 + 신규 17 = 1143).
- **AC-Q2**: `mypy .` → Success (0 오류).
- **AC-Q3**: ruff clean, 신규 외부 의존성 없음.
- **AC-Q4**: 테스트는 `_SIM_HISTORY_PATH`를 tmp_path로 격리하여 실제 데이터 파일 미오염.
