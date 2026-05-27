---
id: SPEC-LOTTO-017
version: 0.1.0
status: completed
created: 2026-05-26
updated: 2026-05-26
author: ircp
priority: medium
issue_number: null
---

# SPEC-LOTTO-017: 당첨금 분석 대시보드

## HISTORY

- 2026-05-26 v0.1.0: 최초 작성

## 메타데이터

| 항목 | 값 |
|------|-----|
| 도메인 | 분석 |
| 영향 범위 | API, 웹 UI |
| 의존 SPEC | SPEC-WEB-001, SPEC-LOTTO-003 |

## 배경 및 목적

현재 추첨 데이터에는 당첨금 정보가 포함되어 있지 않다.
1등 당첨금 추이를 보면 구매 타이밍을 판단하는 데 도움이 된다.
API 크롤링 시 당첨금 데이터를 함께 수집하고, 홈 페이지에 트렌드 차트를 제공한다.

## 요구사항

### REQ-PRIZE-D-001: DrawResult 모델 확장

- `DrawResult`에 `prize1Amount: int | None` (1등 당첨금, 원) 필드 추가
- `prize1Winners: int | None` (1등 당첨자 수) 필드 추가
- draws.csv에 새 컬럼 추가 (기존 데이터는 None 처리)

### REQ-PRIZE-D-002: 당첨금 통계 API

- GET `/api/prize-stats` — 최근 N회차 당첨금 데이터 반환
  - `avg_prize1`: 평균 1등 당첨금
  - `max_prize1`: 최대 1등 당첨금
  - `recent`: 최근 20회차 [{drwNo, date, prize1Amount, prize1Winners}]

### REQ-PRIZE-D-003: 홈 페이지 당첨금 차트

- 인덱스 페이지에 최근 20회차 1등 당첨금 트렌드 라인 차트
- 평균·최대·최소 당첨금 통계 카드

## 인수 조건

- 기존 CSV 데이터 하위 호환 유지 (새 컬럼 없어도 오류 없음)
- 당첨금 데이터 없으면 차트 숨김 처리
