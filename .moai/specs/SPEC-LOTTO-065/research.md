---
id: SPEC-LOTTO-065
version: 0.1.0
status: Planned
created: 2026-06-10
updated: 2026-06-10
author: ircp
---

# SPEC-LOTTO-065 리서치 (Codebase Analysis)

표준편차 분석 기능을 추가하기 위한 코드베이스 분석. 가장 최근 동일 패턴인
SPEC-LOTTO-064(최대최소)를 1:1 참조 구현으로 사용한다.

## 1. 중복/충돌 확인

- grep 결과 `std`/`표준편차`/`stddev` 관련 함수·라우트·네비·템플릿 없음 → 신규 추가 안전.
- 최신 stats 함수는 `get_min_max_stats`(data.py:4489), 그 직전이
  `get_last_digit_sum_stats`(data.py:4352). 본 SPEC `get_std_stats`는 이 뒤에 추가.

## 2. 참조 구현 (SPEC-064 최대최소) 앵커

### data.py — 함수 + 캐시

- `get_min_max_stats(draws)` 정의: `lotto/web/data.py:4489`
  (캐시 조회 4522, 저장 4528/4576). 동일 구조로 `get_std_stats` 작성.
- 캐시 변수 선언부: 기존 `_min_max_cache`, `_last_digit_sum_cache`,
  `_high_low_cache` 등과 같은 위치에 `_std_cache: dict[str, Any] = {}` 추가.
- `invalidate_cache()` 본문(data.py:~160-169): 마지막 줄 `_min_max_cache.clear()`
  바로 뒤에 `_std_cache.clear()` 추가 (global 선언 불필요 — 모듈 전역 dict의
  `.clear()`는 재바인딩이 아님).
- 반환은 `dict[str, Any]`, 캐시 키 `str(len(draws))`.

### routes/pages.py — 페이지 라우트

- 참조: `lotto/web/routes/pages.py:852` `@router.get("/stats/min-max")` →
  `stats_min_max_page`. `wd.get_min_max_stats(wd.get_draws())` 호출 후
  `_render(request, "min_max.html", {"active_tab": "min_max", ...})`.
- 신규: `@router.get("/stats/std")` → `stats_std_page`,
  `wd.get_std_stats(wd.get_draws())`, `_render(request, "std_analysis.html",
  {"active_tab": "std", ...})`.

### routes/api.py — JSON 라우트

- 참조: `lotto/web/routes/api.py:774` `@router.get("/stats/min-max")` →
  `get_min_max_stats_route` → `return wd.get_min_max_stats(wd.get_draws())`
  (api router는 `/api` prefix이므로 실제 경로 `/api/stats/min-max`).
- 신규: `@router.get("/stats/std")` → `get_std_stats_route` →
  `return wd.get_std_stats(wd.get_draws())` (실제 경로 `/api/stats/std`).

### templates/base.html — 네비게이션 (양쪽)

- 데스크톱 nav 리스트: `lotto/web/templates/base.html:74`
  `desktop_nav_items`에 `('/stats/min-max', 'min_max', '최대최소')` 뒤
  `('/stats/std', 'std', '표준편차')` 추가.
- active_tab 라벨 블록: base.html:103 `{% elif active_tab == 'min_max' %}최대최소`
  패턴과 동일하게 `{% elif active_tab == 'std' %}표준편차` 추가.
- 모바일 nav 리스트: base.html:130 `nav_items`에도 동일 튜플 추가.

### templates/min_max.html — 페이지 템플릿 참조

- 신규 `std_analysis.html`은 `min_max.html`을 모델로:
  요약 카드(avg/min/max std + low/mid/high count·pct) + bucket bar-like 표.
- 서버 사이드 렌더링 전용, JS 없음. `{% extends "base.html" %}`.

## 3. std 계산 핵심 (손계산 검증)

```
mean = sum(nums) / 6
variance = sum((n - mean) ** 2 for n in nums) / 6   # 모분산 (n=6)
std = variance ** 0.5
std = round(std, 2)                                  # 회차당 2 decimals
```

검증값: [1,2,3,4,5,6]→1.71, [10,15,20,25,30,35]→8.54,
[5,10,15,20,25,40]→11.33, [1,2,3,4,5,45]→15.71 (acceptance.md 픽스처와 일치).

### 카테고리/bucket 경계 주의

- 카테고리: low `std < 10.0`, mid `10.0 <= std < 14.0`, high `std >= 14.0`.
  std는 회차당 round(_,2) 이후 값으로 비교.
- bucket 6키 고정 순서: `["0-4","4-8","8-12","12-16","16-20","20+"]`.
  배정 규칙 `a <= v < b`, v ≥ 20 → "20+". std_distribution은 항상 6키 전부 포함
  (출현 없는 키도 0). **이 부분이 SPEC-064와의 차이점** — SPEC-064 분포는
  출현 값만 포함했으나 본 SPEC은 0-채움 고정 키.
- most_common_bucket 동률 → 정의 순서 우선. 빈 데이터 → "0-4".

## 4. 테스트/품질 게이트

- 테스트 파일: `tests/test_std_analysis.py` (최소 20개).
  데이터 레이어(계산·경계·캐시·불변성) + API 200 + 페이지 렌더 + 빈 데이터 커버.
- `mypy.ini`: line 31의 `[mypy-...]` override 목록 끝
  (`...,test_min_max_analysis]`)에 `,test_std_analysis` 추가.
- Python 3.9 호환: `**` 거듭제곱·`sum`·`min`·`max`만 사용 → match/case,
  `zip(strict=)` 불필요. [[feedback-python39]] 참고.
- 기존 1480 테스트 무회귀. 코어 `lotto/*.py`(web 외) 미변경.

## 5. 변경 파일 요약 (run 단계)

| 파일 | 변경 |
|------|------|
| `lotto/web/data.py` | `_std_cache` 선언, `get_std_stats` 추가, `invalidate_cache`에 `.clear()` 1줄 |
| `lotto/web/routes/pages.py` | `/stats/std` 페이지 라우트 추가 |
| `lotto/web/routes/api.py` | `/stats/std`(→`/api/stats/std`) JSON 라우트 추가 |
| `lotto/web/templates/base.html` | 데스크톱/모바일 nav + active_tab 라벨에 "표준편차" 추가 |
| `lotto/web/templates/std_analysis.html` | 신규 템플릿 |
| `tests/test_std_analysis.py` | 신규 테스트 (≥20) |
| `mypy.ini` | override 목록에 `test_std_analysis` 추가 |
