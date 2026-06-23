---
id: SPEC-LOTTO-117
version: 1.0.0
status: completed
created: 2026-06-24
updated: 2026-06-24
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-117: 번호별 통합 점수 히트맵

## 개요 (Overview)

각 번호(1~45)에 대해 빈도·최근출현·간격역수·동반쌍 4가지 통계 지표를 min-max 정규화 후
평균하여 [0,1] 범위의 통합 점수를 산출하고, 색상 그라디언트 히트맵으로 시각화한다.

사용자는 `/stats/heatmap` 페이지에서 어떤 번호가 현재 통계적으로 "유망"한지
한눈에 파악하고, 상세 점수 테이블을 통해 각 지표별 수치를 확인할 수 있다.

## EARS 요구사항 (Requirements)

### REQ-HM-001 — 4지표 수집 및 정규화

**WHEN** 사용자가 `/stats/heatmap` 페이지에 접근하면
**THE SYSTEM SHALL** 각 번호(1~45)에 대해 다음 4가지 지표를 계산한다:

- `freq_score`: 전체 회차 출현 빈도 (절대 빈도 → min-max 정규화)
- `recent_score`: 최근 20회차 출현 빈도 → min-max 정규화
- `gap_score`: 회차 대비 출현율(빈도/회차수) → min-max 정규화
- `pair_score`: 상위 동반쌍에서 해당 번호가 등장한 count 합산 → min-max 정규화

### REQ-HM-002 — 통합 점수 산출

**THE SYSTEM SHALL** 4가지 정규화 점수의 산술 평균을 `composite` 점수로 반환하며,
모든 점수는 [0.0, 1.0] 범위를 보장한다.

### REQ-HM-003 — 히트맵 시각화

**THE SYSTEM SHALL** `/stats/heatmap` 페이지에서 1~45 번호를 색상 코딩된 셀로 표시한다:
- 낮은 점수: 파란색(hsl(240))
- 높은 점수: 빨간색(hsl(0))
- 각 셀에 번호와 통합 점수를 표시

### REQ-HM-004 — 상세 점수 테이블

**THE SYSTEM SHALL** 히트맵 하단에 통합 점수 내림차순으로 상세 점수 테이블을 제공한다.

### REQ-HM-005 — 빈 데이터 처리

**WHEN** 당첨 데이터가 없으면
**THE SYSTEM SHALL** `get_number_heatmap()`이 `None`을 반환하고 페이지에 경고 메시지를 표시한다.

## 구현 파일 (Implementation Files)

| 파일 | 역할 |
|------|------|
| `lotto/web/data.py` | `get_number_heatmap()` 함수 추가 |
| `lotto/web/routes/pages.py` | `/stats/heatmap` 라우트 추가 |
| `lotto/web/templates/heatmap.html` | 히트맵 템플릿 |
| `lotto/web/templates/base.html` | 네비게이션 링크 추가 |
| `tests/test_heatmap.py` | 8개 테스트 |

## 테스트 결과 (Test Results)

- 추가 테스트: +8개
- 누적 테스트: 3122 → 3130개
- 커밋: `524fc0f`
