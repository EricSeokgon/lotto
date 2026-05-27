---
id: SPEC-LOTTO-020
version: 0.1.0
status: completed
created: 2026-05-26
updated: 2026-05-26
author: ircp
priority: medium
issue_number: null
---

# SPEC-LOTTO-020: 데이터 내보내기 (Export)

## HISTORY

- 2026-05-26 v0.1.0: 최초 작성

## 메타데이터

| 항목 | 값 |
|------|-----|
| 도메인 | 데이터 관리 |
| 영향 범위 | API, 웹 UI |
| 의존 SPEC | SPEC-WEB-001, SPEC-LOTTO-014 |

## 배경 및 목적

수집된 추첨 데이터와 구매 이력을 외부 도구(Excel, Google Sheets 등)에서
활용하거나 백업할 수 있어야 한다.

## 요구사항

### REQ-EXP-001: 추첨 데이터 CSV 내보내기

- GET `/api/export/draws` → `draws.csv` 파일 다운로드 응답
  - Content-Disposition: attachment; filename="lotto_draws_YYYYMMDD.csv"
- 선택 파라미터: `from_drw`, `to_drw` (회차 범위 필터)

### REQ-EXP-002: 구매 이력 CSV 내보내기

- GET `/api/export/history` → CSV 파일 다운로드
  - 컬럼: 구매일, 번호, 회차, 등수, 당첨금
  - Content-Disposition: attachment; filename="lotto_history_YYYYMMDD.csv"

### REQ-EXP-003: 구매 이력 JSON 내보내기

- GET `/api/export/history?format=json` → JSON 파일 다운로드

### REQ-EXP-004: 웹 UI 내보내기 버튼

- collect 페이지: "추첨 데이터 내보내기 (CSV)" 버튼
- history 페이지: "구매 이력 내보내기 (CSV / JSON)" 버튼

## 인수 조건

- 데이터가 없어도 빈 CSV (헤더만) 반환 (404 아닌 200)
- 파일명에 현재 날짜(YYYYMMDD) 포함
