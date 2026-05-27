---
id: SPEC-LOTTO-016
version: 0.1.0
status: completed
created: 2026-05-26
updated: 2026-05-26
author: ircp
priority: high
issue_number: null
---

# SPEC-LOTTO-016: 번호 즐겨찾기 관리

## HISTORY

- 2026-05-26 v0.1.0: 최초 작성

## 메타데이터

| 항목 | 값 |
|------|-----|
| 도메인 | 즐겨찾기 |
| 영향 범위 | API, 웹 UI |
| 의존 SPEC | SPEC-WEB-001 |

## 배경 및 목적

자주 사용하는 번호 조합을 저장하고 재사용할 수 있어야 한다.
추천 번호를 즐겨찾기에 저장하거나, 직접 입력한 조합을 관리할 수 있다.
시뮬레이션 실행 시 즐겨찾기 번호를 바로 사용할 수 있다.

## 요구사항

### REQ-FAV-001: 즐겨찾기 저장

- POST `/api/favorites` — 번호 조합(6개) + 이름(선택)을 즐겨찾기에 추가
- `data/favorites.json`에 저장
- 중복 번호 조합이면 409 반환

### REQ-FAV-002: 즐겨찾기 조회

- GET `/api/favorites` — 전체 목록 반환 (저장 순)

### REQ-FAV-003: 즐겨찾기 삭제

- DELETE `/api/favorites/{fav_id}` — 지정 항목 삭제, 없으면 404

### REQ-FAV-004: 웹 UI — 즐겨찾기 관리 탭

- 추천 페이지(`/recommend`)에 즐겨찾기 섹션 추가
- 번호 조합 직접 입력 + 이름 저장 폼
- 저장된 즐겨찾기 목록 표시 (삭제 버튼 포함)

### REQ-FAV-005: 웹 UI — 시뮬레이션 연동

- 시뮬레이션 페이지(`/simulate`)에서 즐겨찾기 번호를 선택하여 시뮬레이션 실행

## 인수 조건

- 번호는 1~45, 중복 없는 6개
- 이름은 최대 20자, 없으면 "번호조합 N"으로 자동 부여
- favorites.json은 원자적 쓰기(tempfile + os.replace) 사용
