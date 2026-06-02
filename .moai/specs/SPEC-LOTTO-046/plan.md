---
id: SPEC-LOTTO-046
version: 0.1.0
status: Planned
created: 2026-06-02
updated: 2026-06-02
author: ircp
priority: medium
---

# SPEC-LOTTO-046 구현 계획

## 방법론

TDD (RED → GREEN → REFACTOR). 기존 SPEC-LOTTO-038/044 패턴을 재사용한다.

## 변경 대상 파일

| 파일 | 변경 내용 |
|------|-----------|
| `lotto/web/data.py` | `yearly_prize_comparison()` 신규 함수 (단일 O(N) 패스, `_UNSET` 센티넬 패턴) |
| `lotto/web/routes/api.py` | GET `/api/stats/yearly-prize` 라우트 (wd. 동적 디스패치) |
| `lotto/web/routes/pages.py` | GET `/stats/yearly-prize` 페이지 라우트 (`active_tab="yearly_prize"`) |
| `lotto/web/templates/yearly_prize.html` | 신규 템플릿 (막대 차트 + 테이블 + 빈 상태) |
| `lotto/web/templates/base.html` | 네비게이션 링크 3개소 추가 |
| `mypy.ini` | 신규 테스트 모듈 3개 오버라이드 목록에 추가 |

## TDD 순서

1. `tests/test_yearly_prize.py` (단위 8+) → RED → `yearly_prize_comparison()` 구현 → GREEN
2. `tests/test_api_yearly_prize.py` (API 4) → RED → API 라우트 추가 → GREEN
3. `tests/test_yearly_prize_page.py` (페이지 4) → RED → 페이지/템플릿/네비 추가 → GREEN
4. mypy.ini 갱신 → `mypy .` Success
5. 전체 테스트 + ruff 검증

## 설계 결정

- **집계 방식**: SPEC-LOTTO-038 `dashboard_overview`의 연도 버킷 누적 패턴을 확장하여
  연도별 sum/max/min/winners/회차 수를 단일 패스로 누적한다.
- **highest/lowest**: prize 보유 연도만 대상, 동률 시 낮은 연도 우선 (결정론 보장).
- **데이터 부재**: 다른 분석 함수와 동일하게 일관된 빈 구조 반환.

## Python 3.9 / 품질

- FastAPI Query 미사용 (파라미터 없음) — runtime 타입 이슈 없음.
- ruff clean, mypy `.` = Success (SPEC-045가 정리한 0 errors 유지).
- 신규 외부 의존성 없음.
