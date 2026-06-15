---
id: SPEC-LOTTO-082
title: 10단위 다양성 분포 분석 - 구현 계획
version: 0.1.0
created: 2026-06-15
---

# 구현 계획

## 데이터 계층 (lotto/web/data.py)

1. 상수 `_DECADE_DIV_KEYS = ["1", "2", "3", "4", "5"]` 및 캐시 `_decade_div_cache` 추가.
2. 헬퍼 `_decade_of(n)` — 번호를 1~5 구간으로 매핑.
3. `get_decade_diversity_stats(draws)` — 회차별 커버 구간 수를 집계.
   - 캐시 키: `str(len(draws))`.
   - 빈 입력: 모든 값 0, `most_common_count=1`.
   - 동률 `most_common_count`: 작은 키 우선.
   - `full_coverage_pct`: `decade_count==5` 비율.
4. `invalidate_cache()`에 `_decade_div_cache.clear()` 추가.

## API 계층 (lotto/web/routes/api.py)

- `GET /api/stats/decade_diversity` → `wd.get_decade_diversity_stats(wd.get_draws())`.

## 페이지 계층 (lotto/web/routes/pages.py)

- `GET /stats/decade-diversity` → `decade_diversity.html` 렌더링.

## 템플릿 (lotto/web/templates/decade_diversity.html)

- 다크 모드 Tailwind, single_digit.html 패턴(5키 분포).
- 요약 카드 4개 + 분포 테이블 5행.

## 내비게이션 (lotto/web/templates/base.html)

- 데스크톱/모바일 nav에 "10단다양" → `/stats/decade-diversity` 추가.

## 테스트 (tests/test_decade_diversity_analysis.py)

- 약 27개 — 헬퍼, 빈 입력, 손계산 픽스처, 분포/합/비율/동률, 캐시, 라우트.

## 기존 코드 보호

- `get_decade_stats`(SPEC-059) 및 `_decade_cache`는 절대 수정하지 않는다.
