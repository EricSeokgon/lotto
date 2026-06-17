---
id: SPEC-LOTTO-022
version: 0.1.0
status: completed
created: 2026-05-27
updated: 2026-05-27
author: ircp
priority: high
issue_number: null
---

# SPEC-LOTTO-022: 1등 당첨금 크롤링

## HISTORY

- 2026-05-27 v0.1.0: 최초 작성

## 메타데이터

| 항목 | 값 |
|------|-----|
| 도메인 | 데이터 수집 |
| 영향 범위 | collector, API, 웹 UI |
| 의존 SPEC | SPEC-LOTTO-017 |

## 배경 및 목적

SPEC-LOTTO-017에서 `prize1Amount`, `prize1Winners` 필드를 모델에 추가했지만
실제 데이터는 모두 None이다.
동행복권 공식 API 응답(`getLottoNumber`)에는 `firstWinamnt`(1등 당첨금),
`firstPrzwnerCo`(1등 당첨자 수) 필드가 이미 포함되어 있다.
수집 시 해당 필드를 파싱하여 저장하면 당첨금 차트를 실제 데이터로 표시할 수 있다.

## 요구사항

### REQ-PRIZE-C-001: API 응답 파싱 확장

- `LottoCollector._fetch_draw()` 에서 `firstWinamnt`, `firstPrzwnerCo` 파싱
- `DrawResult.prize1Amount`, `prize1Winners` 필드에 저장
- API 응답에 필드가 없으면 `None` 처리 (방어 코드)

### REQ-PRIZE-C-002: 기존 데이터 소급 업데이트

- CLI 커맨드 `python main.py collect --update-prizes` 옵션 추가
- 이미 수집된 회차 중 `prize1Amount`가 `None`인 행만 API 재요청하여 업데이트
- 처리 진행률 표시 (rich progress bar)
- 웹 API `POST /api/collect` 파라미터 `update_prizes: bool = False` 추가

### REQ-PRIZE-C-003: 수집 현황 UI 갱신

- 수집 현황 페이지 테이블에 "1등 당첨금" 컬럼 추가 (없으면 "-" 표시)

## 인수 조건

- 신규 수집 시 prize1Amount가 자동으로 채워짐
- 기존 데이터 소급 업데이트 시 누락된 행만 갱신 (전체 재수집 불필요)
- prize1Amount가 없는 행도 정상 로드 (하위 호환 유지)
- 테스트: 신규 수집 파싱 + 소급 업데이트 로직 단위 테스트
