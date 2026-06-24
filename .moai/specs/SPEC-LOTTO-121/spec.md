---
id: SPEC-LOTTO-121
version: 1.0.0
status: completed
created: 2026-06-24
updated: 2026-06-24
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-121: AC값(산술 복잡도) 분석

## 개요 (Overview)

로또 커뮤니티에서 즐겨 사용하는 AC값(Arithmetic Complexity)을 전체 당첨 회차에 적용하여
분포·평균·최빈값과 최근 20회차 상세 이력을 `/stats/ac-value` 페이지로 제공한다.

AC값 = 당첨 번호 6개 간 모든 차이값의 고유 개수 - 5 (범위: 0~10)
높을수록 번호 조합이 분산되어 있으며, 중간값(4~7) 범위가 역대 최빈 범위.

## EARS 요구사항 (Requirements)

### REQ-AC-001 — AC값 계산

**THE SYSTEM SHALL** 6개 번호의 모든 쌍(C(6,2)=15쌍)에 대해 차이값을 계산하고
고유 차이값 수에서 5를 뺀 AC값을 반환한다.

### REQ-AC-002 — 전체 분포

**THE SYSTEM SHALL** 0~10 각 AC값별 출현 회차 수와 비율을 분포 딕셔너리로 반환한다.

### REQ-AC-003 — 요약 통계

**THE SYSTEM SHALL** 평균 AC값(`avg_ac`), 최빈 AC값(`best_ac`), 최빈 비율(`best_ac_pct`)을 반환한다.

### REQ-AC-004 — 최근 20회차 상세

**THE SYSTEM SHALL** 가장 최근 20회차의 회차번호·당첨 번호·AC값을 반환한다.

### REQ-AC-005 — 빈 데이터 처리

**WHEN** 당첨 데이터가 없으면 **THE SYSTEM SHALL** `None`을 반환하고 페이지에 경고를 표시한다.

## 구현 파일 (Implementation Files)

| 파일 | 역할 |
|------|------|
| `lotto/web/data.py` | `_calc_ac()` 헬퍼 + `get_ac_analysis()` 함수 추가 |
| `lotto/web/routes/pages.py` | `/stats/ac-value` 라우트 업데이트 |
| `lotto/web/templates/ac_value.html` | 요약 카드 + 분포 표 + 최근 20회차 + 활용 가이드 |
| `tests/test_ac_value.py` | 11개 테스트 |

## 참고

기존 SPEC-LOTTO-070의 `get_ac_value_stats`는 유지되며,
새 `get_ac_analysis`가 `/stats/ac-value` 라우트에서 사용된다.

## 테스트 결과 (Test Results)

- 추가 테스트: +11개
- 누적 테스트: 3162 → 3173개
- 커밋: `ba1d192`
