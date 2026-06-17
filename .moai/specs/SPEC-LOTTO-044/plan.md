---
id: SPEC-LOTTO-044
version: 0.1.0
status: Planned
created: 2026-06-02
updated: 2026-06-02
author: ircp
priority: medium
---

# SPEC-LOTTO-044 구현 계획 (Plan)

## 아키텍처 개요

기존 SPEC-LOTTO-030/042/043 패턴을 그대로 따른다.

- 데이터 레이어: `lotto/web/data.py` — `number_affinity()` 추가 (`_UNSET` 센티넬 패턴)
- API 레이어: `lotto/web/routes/api.py` — `GET /api/numbers/affinity` (동적 `wd.` 디스패치)
- 페이지 레이어: `lotto/web/routes/pages.py` — `GET /numbers/affinity`
- 템플릿: `lotto/web/templates/numbers_affinity.html` (base.html 확장)
- 네비게이션: `base.html` 3개 위치

## 핵심 알고리즘 (number_affinity)

1. `draws is _UNSET` → `get_draws()` 로드. 빈/None → 빈 구조 반환.
2. 대상이 포함된 회차만 순회하며 동반 번호 카운트 (`dict[int,int]`).
3. `target_appearances` = 대상이 등장한 회차 수.
4. 파트너 = count desc, number asc 정렬 후 top_k 절단.
5. rate = round(count / target_appearances, 4).
6. recommended_combination = sorted([target] + 상위 5 파트너 번호).

복잡도: O(D) (D = 회차 수, 각 회차 본번호 6개 고정).

## 라우트 등록 순서 (중요)

`/numbers/affinity` 는 `/numbers/{number}` 동적 라우트보다 **먼저** 등록해야
"affinity"가 `{number}`로 캡처되지 않는다 (SPEC-LOTTO-042 trend와 동일 패턴).

## Python 3.9 호환

- API Query: `Optional[int]` 사용 (런타임 위치).
- `from __future__ import annotations` 존재 → data.py 시그니처는 `list[X] | None` 가능.

## 작업 순서 (TDD)

1. RED: `tests/test_number_affinity.py` (~9) → 실패 확인
2. GREEN: `number_affinity()` 구현 → 통과
3. RED: `tests/test_api_affinity.py` (~5) → 실패 확인
4. GREEN: API 라우트 추가 → 통과
5. RED: `tests/test_affinity_page.py` (~4) → 실패 확인
6. GREEN: 페이지 라우트 + 템플릿 + nav → 통과
7. 전체 스위트 실행 (1066 + 18 신규)
8. REFACTOR (필요 시)

## MX 태그

- `# @MX:NOTE: [AUTO] SPEC-LOTTO-044` + `# @MX:SPEC: SPEC-LOTTO-044` (number_affinity)
- API/페이지 라우트에도 동일 패턴.
