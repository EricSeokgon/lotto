---
id: SPEC-LOTTO-019
version: 0.1.0
status: completed
created: 2026-05-26
updated: 2026-05-26
author: ircp
priority: medium
issue_number: null
---

# SPEC-LOTTO-019: 번호 패턴 분석 강화

## HISTORY

- 2026-05-26 v0.1.0: 최초 작성

## 메타데이터

| 항목 | 값 |
|------|-----|
| 도메인 | 분석 |
| 영향 범위 | API, 웹 UI |
| 의존 SPEC | SPEC-WEB-001 |

## 배경 및 목적

단순 출현 빈도 이외에 패턴 기반 분석이 필요하다.
홀짝 비율, 번호대(1~10, 11~20 등) 분포, 연속 번호 존재 여부, 합계 범위를
분석하면 더 전략적인 번호 선택이 가능하다.

## 요구사항

### REQ-PAT-001: 패턴 분석 API

GET `/api/pattern-analysis` 반환값:
- `odd_even`: 홀짝 비율 히스토그램 (홀N:짝M 별 당첨 비율)
- `range_dist`: 번호대 분포 (1~9, 10~19, 20~29, 30~39, 40~45)
- `consecutive`: 연속 번호 포함 비율
- `sum_range`: 당첨 번호 합계 분포 (구간별)
- `last_digit`: 끝자리 분포

### REQ-PAT-002: 분석 페이지 패턴 탭

- 분석 페이지(`/analyze`)에 "패턴 분석" 탭 추가
- 홀짝 비율 도넛 차트
- 번호대 분포 바 차트
- 합계 범위 히스토그램

### REQ-PAT-003: 추천 시 패턴 필터

- GET `/api/recommendations` 파라미터에 `odd_count`, `sum_min`, `sum_max` 추가 (선택)
- 필터 조건에 맞는 번호 조합만 추천

## 인수 조건

- 전체 회차 데이터 기준으로 계산
- 계산 결과는 캐시 적용 (데이터 변경 시 무효화)
