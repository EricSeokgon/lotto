---
id: SPEC-LOTTO-079
title: 끝자리 합계 분포 분석 — 구현 계획
version: 0.1.0
created: 2026-06-15
---

# SPEC-LOTTO-079 구현 계획

## 충돌 사전 점검 결과

`get_last_digit_sum_stats`(SPEC-063)가 이미 존재하나 출력 구조가 다르다:
- SPEC-063: low/mid/high 3카테고리 + 관측값 only `sum_distribution`.
- SPEC-079: 6개 고정 구간 버킷 + zero-fill `digit_sum_distribution`.

→ 별도 함수 `get_digit_sum_dist_stats`로 신규 구현. SPEC-063 함수 미수정.

## 변경 파일

1. `lotto/web/data.py`
   - 상수 `_DIGIT_SUM_KEYS`, 캐시 `_digit_sum_dist_cache` 추가
   - 헬퍼 `_digit_sum_bucket(s)` 추가
   - 함수 `get_digit_sum_dist_stats(draws)` 추가 (파일 끝, triple_run 다음)
   - `invalidate_cache()`에 `_digit_sum_dist_cache.clear()` 추가
2. `lotto/web/routes/api.py`
   - `GET /stats/digit_sum_dist` 엔드포인트
3. `lotto/web/routes/pages.py`
   - `GET /stats/digit-sum-dist` 페이지 라우트
4. `lotto/web/templates/digit_sum_dist.html` (신규)
5. `lotto/web/templates/base.html`
   - 데스크톱/모바일 nav에 "끝자리합" 링크, active_tab 제목 추가
6. `tests/test_digit_sum_dist_analysis.py` (신규, ~27 tests)
7. `tests/conftest.py`는 `invalidate_cache()` 위임으로 자동 격리(별도 수정 불필요)

## TDD 절차

1. RED: `tests/test_digit_sum_dist_analysis.py` 작성 → 실패 확인
2. GREEN: data.py + routes + template + base.html 구현 → 통과
3. REFACTOR: 패턴 정합성 점검, ruff 통과

## 손계산 픽스처 (4 회차)

| 회차 | 본번호 | 끝자리 | 합 | 버킷 |
|------|--------|--------|----|----|
| D1 | [1,2,3,4,5,6]        | [1,2,3,4,5,6] | 21 | 20-24 |
| D2 | [10,20,30,40,41,42]  | [0,0,0,0,1,2] | 3  | 0-9   |
| D3 | [5,15,25,35,6,7]     | [5,5,5,5,6,7] | 33 | 30+   |
| D4 | [3,13,23,33,4,14]    | [3,3,3,3,4,4] | 20 | 20-24 |

- avg_digit_sum = (21+3+33+20)/4 = 19.25
- most_common_range = "20-24" (count=2)
- high_digit_sum_pct = 1/4*100 = 25.0 (D3만 합>=25)
