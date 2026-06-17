# SPEC-LOTTO-006: API 페이지네이션 및 필터링

## 개요

웹 대시보드의 핵심 데이터 조회 API(`/api/draws`, `/api/recommendations`)에 페이지네이션과 필터링 기능을 추가하여, 대용량 데이터 처리 효율성을 개선하고 클라이언트가 필요한 데이터만 선택적으로 조회할 수 있도록 한다.

## 배경

기존 `/api/draws` 엔드포인트는 수집된 모든 회차 데이터를 단일 응답으로 반환하여, 회차가 누적될수록 응답 크기가 증가하고 클라이언트 측 필터링이 비효율적이다. 또한 `/api/recommendations`는 8개 전략을 순환 반환하지만 특정 전략만 조회할 수 있는 방법이 없어, UI에서 전략별 비교를 위해서는 전체 응답을 받아 필터링해야 한다.

이번 SPEC은 (1) `/api/draws`에 limit/offset 기반 페이지네이션과 회차 범위 필터를, (2) `/api/recommendations`에 전략 필터를 도입하여 API 효율성과 UX를 동시에 개선한다.

## 요구사항 (EARS 형식)

### Ubiquitous (시스템 전역)

- **REQ-PAGE-001**: `GET /api/draws`는 `limit`(기본 50, 최대 200)과 `offset`(기본 0) 쿼리 파라미터를 지원해야 한다. 잘못된 값(범위 초과)에 대해서는 FastAPI의 표준 검증 동작(422)을 따른다.
- **REQ-PAGE-002**: `GET /api/draws` 응답은 `total`, `limit`, `offset`, `items` 필드를 포함한 페이지네이션 래퍼 객체를 반환해야 한다. `total`은 필터 적용 후 전체 회차 수, `items`는 페이지에 해당하는 회차 목록이다.
- **REQ-PAGE-003**: `GET /api/draws`는 `from_round`, `to_round` 쿼리 파라미터로 회차 범위 필터링을 지원해야 한다. 두 파라미터는 독립적으로 사용 가능하며, 모두 미지정 시 전체 데이터를 대상으로 한다.

### Event-driven (이벤트 기반)

- **REQ-FILTER-001**: `GET /api/recommendations`에 `strategy` 쿼리 파라미터가 제공될 때, 시스템은 해당 전략 라벨과 일치하는 추천 세트만 반환해야 한다.
- **REQ-FILTER-002**: `GET /api/recommendations`에 `strategy` 파라미터가 제공되지 않으면, 시스템은 기존 동작(`count` 개수만큼 전략 순환 반환)을 유지해야 한다.

### Unwanted (회피)

- **REQ-PAGE-004**: `from_round`가 데이터의 최대 회차보다 큰 경우에도, 시스템은 500 에러를 발생시키지 말고 `total=0`, `items=[]`인 정상 응답을 반환해야 한다.
- **REQ-FILTER-003**: 존재하지 않는 전략명이 `strategy` 파라미터로 전달되어도, 시스템은 500 에러를 발생시키지 말고 200과 빈 리스트를 반환해야 한다.

## 비기능 요구사항 (NFR)

- **NFR-PAGE-001**: `/api/draws` 응답 구조 변경(flat list → 페이지네이션 래퍼)에 따라 기존 테스트(`tests/test_web_api.py`)를 적응시켜야 한다. 외부에 노출된 클라이언트(브라우저 JS, 자동화 도구)는 본 프로젝트 내 `/api/draws/manual` 외에 없으므로 호환성 영향은 테스트 수정으로 한정된다.
- **NFR-PAGE-002**: `limit`이 200을 초과하더라도 FastAPI Query 검증으로 422가 반환되며, 응답 크기 폭주를 방지한다.
- **NFR-FILTER-001**: 전략 필터링은 추천 결과 후처리 방식으로 구현하여, 기존 `LottoRecommender.recommend()` API와 결합도를 최소화한다.

## 범위

### In Scope
- `lotto/web/routes/api.py` 내 `/api/draws` 엔드포인트에 `limit`, `offset`, `from_round`, `to_round` 쿼리 파라미터 추가 및 페이지네이션 래퍼 응답 변경
- `lotto/web/routes/api.py` 내 `/api/recommendations` 엔드포인트에 `strategy` 쿼리 파라미터 추가 및 후처리 필터링
- 신규 테스트 파일: `tests/test_api_pagination.py`, `tests/test_api_strategy_filter.py`
- 기존 테스트 파일 `tests/test_web_api.py`의 `/api/draws` 관련 assertion 업데이트

### Out of Scope
- `/api/stats`, `/api/simulation`, `/api/history` 페이지네이션 — 별도 SPEC에서 검토
- 정렬(sort) 파라미터 — 본 SPEC은 기본 회차 오름차순만 지원
- 커서 기반 페이지네이션 — 본 SPEC은 offset 기반만 지원
- UI(템플릿) 변경 — 본 SPEC은 API 계약만 변경

## 의존성

- 기존 모듈: `lotto.web.data.get_draws`, `lotto.web.data.get_recommendations`
- 기존 모델: `lotto.models.DrawResult`, `lotto.models.Recommendation`
- 기존 상수: `lotto.recommender.STRATEGY_LABELS` (8개 전략 라벨)
- FastAPI `Query` 검증 (`ge`, `le`)

## 참고

- SPEC-WEB-001: 웹 대시보드 API 인프라
- SPEC-LOTTO-005: PDF 리포트 (동일 라우터 파일 수정)

---

Version: 1.0.0
Status: completed
Created: 2026-05-21
