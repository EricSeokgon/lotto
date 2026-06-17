---
id: SPEC-LOTTO-044
version: 0.1.0
status: Planned
created: 2026-06-02
updated: 2026-06-02
author: ircp
priority: medium
---

# SPEC-LOTTO-044 인수 기준 (Acceptance Criteria)

## 데이터 레이어 (number_affinity)

- AC-1: 알려진 픽스처에서 대상과 특정 파트너의 동반 횟수가 정확하다.
- AC-2: partners는 count desc, number asc 정렬되고 길이 <= top_k.
- AC-3: 대상 번호는 자신의 partners 목록에서 제외된다.
- AC-4: rate = count / target_appearances 값이 정확하다 (소수 4자리).
- AC-5: recommended_combination = sorted([target] + 상위 5 파트너), 충분하면 6개.
- AC-6: 대상 미출현 → target_appearances=0, partners=[], recommended_combination=[target].
- AC-7: 빈 리스트 → 일관된 빈 구조, 예외 없음.
- AC-8: None draws → 일관된 빈 구조, 예외 없음.
- AC-9: 결정론 — 동일 입력 2회 호출 시 동일 출력.

## API 레이어 (GET /api/numbers/affinity)

- AC-10: `?target=7` → 200 + 필수 키 (target, total_draws, target_appearances, partners, recommended_combination).
- AC-11: `?target=0` → 422.
- AC-12: `?target=46` → 422.
- AC-13: target 누락 → 422.
- AC-14: get_draws=None → 200 + 빈 구조.

## 페이지 레이어 (GET /numbers/affinity)

- AC-15: `/numbers/affinity` → 200 HTML (폼).
- AC-16: `/numbers/affinity?target=7` → 200 HTML (결과).
- AC-17: get_draws=None → 200 (크래시 없음).
- AC-18: `GET /` 응답에 `href="/numbers/affinity"` 포함.

## 품질

- 신규 코드 ruff clean, mypy clean.
- 외부 의존성 추가 없음.
- 전체 테스트 스위트 통과 (기존 1066 + 신규 18).
