---
id: SPEC-LOTTO-126
version: 1.0.0
status: completed
created: 2026-06-24
updated: 2026-06-24
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-126: 번호 구간 조합(저/중/고) 분석

## 개요 (Overview)

1~15(저), 16~30(중), 31~45(고) 세 구간에서 각 회차에 나온 번호 수의
조합 분포를 `/stats/range-combo` 페이지로 제공한다.

## EARS 요구사항 (Requirements)

### REQ-RC-001 — 조합 집계

**THE SYSTEM SHALL** 각 회차에서 저/중/고 구간별 번호 수를 집계하고
`저-중-고` 형식의 조합 키로 분포를 반환한다.

### REQ-RC-002 — 상위 조합

**THE SYSTEM SHALL** 빈도 상위 15개 조합을 반환한다.

### REQ-RC-003 — 구간별 번호 수 분포

**THE SYSTEM SHALL** 각 구간(저/중/고)에서 0~6개 나올 확률 분포를 반환한다.

### REQ-RC-004 — 요약 통계

**THE SYSTEM SHALL** 최빈 조합, 최빈 조합 출현 수, 전체 조합 종류 수를 반환한다.

### REQ-RC-005 — 빈 데이터 처리

**WHEN** 당첨 데이터가 없으면 **THE SYSTEM SHALL** `None`을 반환하고 페이지에 경고를 표시한다.

## 구현 파일 (Implementation Files)

| 파일 | 역할 |
|------|------|
| `lotto/web/data.py` | `get_range_combo_analysis()` 함수 추가 |
| `lotto/web/routes/pages.py` | `/stats/range-combo` 라우트 추가 |
| `lotto/web/templates/range_combo.html` | 요약 카드 + 상위 조합 표 + 구간별 분포 표 |
| `lotto/web/templates/base.html` | 네비게이션 '구간 조합' 링크 추가 |
| `tests/test_range_combo.py` | 10개 테스트 |

## 테스트 결과 (Test Results)

- 추가 테스트: +10개
- 누적 테스트: 3213 → 3223개
- 커밋: `9c14c86`
