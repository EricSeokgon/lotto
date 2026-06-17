---
id: SPEC-LOTTO-021
version: 0.1.0
status: completed
created: 2026-05-26
updated: 2026-05-26
author: ircp
priority: low
issue_number: null
---

# SPEC-LOTTO-021: 다크모드 & 반응형 UI 개선

## HISTORY

- 2026-05-26 v0.1.0: 최초 작성

## 메타데이터

| 항목 | 값 |
|------|-----|
| 도메인 | UI/UX |
| 영향 범위 | 웹 UI 전체 |
| 의존 SPEC | SPEC-WEB-001 |

## 배경 및 목적

모바일 사용자 비율이 높아지면서 반응형 레이아웃이 필요하다.
다크모드 선호 사용자를 위해 테마 토글을 제공한다.

## 요구사항

### REQ-DARK-001: 다크모드 토글

- base.html 헤더에 다크/라이트 토글 버튼
- `localStorage.theme` 에 설정 저장 (`'dark'` | `'light'`)
- Tailwind `dark:` 클래스 적용 (모든 페이지)
- 시스템 테마 자동 감지 (`prefers-color-scheme`)

### REQ-DARK-002: 반응형 네비게이션

- 모바일(md 미만)에서 햄버거 메뉴 토글
- 현재 페이지 활성화 표시

### REQ-DARK-003: 모바일 테이블 최적화

- 좁은 화면에서 테이블을 카드 레이아웃으로 전환
- 숫자 뱃지 크기 모바일 대응

## 인수 조건

- CDN 전용 유지 (빌드 스텝 없음)
- Tailwind CDN의 `darkMode: 'class'` 설정 활용
- 기존 데스크톱 레이아웃 변경 없음
