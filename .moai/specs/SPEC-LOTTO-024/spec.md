---
id: SPEC-LOTTO-024
version: 0.1.0
status: approved
created: 2026-05-27
updated: 2026-05-27
author: ircp
priority: medium
issue_number: null
---

# SPEC-LOTTO-024: 번호 즉시 검증 도구

## HISTORY

- 2026-05-27 v0.1.0: 최초 작성

## 메타데이터

| 항목 | 값 |
|------|-----|
| 도메인 | UI/UX |
| 영향 범위 | API, 웹 UI |
| 의존 SPEC | SPEC-WEB-001, SPEC-LOTTO-014 |

## 배경 및 목적

구매한 로또 번호가 특정 회차에서 몇 등인지 빠르게 확인하려면
현재는 구매 내역 탭에 등록 후 조회해야 한다.
별도 등록 없이 번호와 회차만 입력하면 즉시 등수·당첨금을 알려주는
간단한 체커 UI가 있으면 편리하다.

## 요구사항

### REQ-CHECK-001: 번호 검증 API

- `GET /api/check?drw_no={N}&numbers={1,2,3,4,5,6}` 엔드포인트
- 해당 회차 당첨 번호와 비교하여 등수 반환
- 응답: `{ drwNo, rank, matched, bonus_matched, prize_amount, draw_date }`
- 회차 미존재 시 404, 번호 형식 오류 시 422

### REQ-CHECK-002: 웹 UI — 번호 체커 페이지

- 신규 경로 `/check` 페이지 추가
- 회차 번호 입력 필드 + 6개 번호 입력 필드
- "확인" 버튼 클릭 시 결과 표시 (등수 뱃지·당첨금·일치 번호 하이라이트)
- 미당첨 시 "아쉽네요" 메시지 + 추천 번호 페이지 링크
- 즐겨찾기 번호 원클릭 불러오기 버튼

### REQ-CHECK-003: 네비게이션 연동

- base.html 네비게이션에 "번호 확인" 탭 추가

## 인수 조건

- 회차 번호 자동완성: 최신 회차를 기본값으로 채움
- 번호 1~45 범위 검증, 중복 불허
- 다크모드 대응 (dark: 클래스 적용)
- 테스트: API 등수 계산 로직 (1~5등 + 미당첨) 단위 테스트
