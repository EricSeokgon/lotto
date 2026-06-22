# SPEC-LOTTO-106 인수 기준 (Acceptance Criteria)

## 테스트 픽스처 (Fixture A — 3회차 손계산)

| 회차 | 본번호 | odd_count | high_count | 비고 |
|------|--------|-----------|------------|------|
| 1 | 1, 3, 5, 7, 9, 11 | 6 | 0 | 전부 홀수, 전부 저번호(≤23) |
| 2 | 2, 24, 25, 26, 28, 30 | 1 | 5 | 홀수 1개(25), 고번호 5개(24,25,26,28,30) |
| 3 | 1, 3, 24, 26, 28, 30 | 2 | 4 | 홀수 2개(1,3), 고번호 4개(24,26,28,30) |

- 고번호 정의: 번호 > 23 (즉 24~45). 회차 1은 1·3·5·7·9·11 모두 ≤ 23 → high_count=0.

> **SPEC 발주서 정정 사항**: 원 발주서의 회차 2 번호 `[2,24,26,28,30,32]`는 6개 모두 짝수이므로
> 실제 odd_count는 0이며, 발주서가 명시한 손계산값(odd_count=1, high_count=5) 및 매트릭스
> `odd_1_high_5`와 모순된다. 권위 있는 손계산값(avg_odd=(6+1+2)/3=3.0 → 회차2 odd_count=1)을
> 우선하여, 회차 2 픽스처를 `[2, 24, 25, 26, 28, 30]`(홀수 1개=25, 고번호 5개)로 정정한다.
> 이로써 matrix/marginal/avg 손계산값이 모두 정합한다.

## 손계산 결과 (top_n=3 기준)

- matrix["odd_6_high_0"] = 1
- matrix["odd_1_high_5"] = 1
- matrix["odd_2_high_4"] = 1
- 그 외 46개 키 = 0
- top_combinations (top_n=3): count 모두 1로 동률 → odd_count 오름차순, high_count 오름차순 정렬
  - [{odd_count:1, high_count:5, count:1, pct:33.33},
     {odd_count:2, high_count:4, count:1, pct:33.33},
     {odd_count:6, high_count:0, count:1, pct:33.33}]
- marginal_odd: {"0":0, "1":1, "2":1, "3":0, "4":0, "5":0, "6":1}
- marginal_high: {"0":1, "1":0, "2":0, "3":0, "4":1, "5":1, "6":0}
- avg_odd = round((6+1+2)/3, 2) = 3.0
- avg_high = round((0+5+4)/3, 2) = 3.0

## 인수 항목 (Acceptance Criteria)

### 핵심 계산 (data layer)

- **AC-CROSS-001**: `get_cross_pattern_stats(fixture_a())` 호출 시 `total_draws == 3`.
- **AC-CROSS-002**: 반환 dict는 키 `total_draws, top_n, matrix, top_combinations, marginal_odd, marginal_high, avg_odd, avg_high, disclaimer`를 모두 포함한다.
- **AC-CROSS-003**: `matrix`는 정확히 49개 키를 가지며, 각 키는 `"odd_{i}_high_{j}"` (i,j in 0..6) 형식이다.
- **AC-CROSS-004**: `matrix["odd_6_high_0"] == 1`.
- **AC-CROSS-005**: `matrix["odd_1_high_5"] == 1`.
- **AC-CROSS-006**: `matrix["odd_2_high_4"] == 1`.
- **AC-CROSS-007**: 위 3개 키를 제외한 나머지 46개 matrix 값의 합은 0이다.
- **AC-CROSS-008**: `marginal_odd == {"0":0,"1":1,"2":1,"3":0,"4":0,"5":0,"6":1}`.
- **AC-CROSS-009**: `marginal_high == {"0":1,"1":0,"2":0,"3":0,"4":1,"5":1,"6":0}`.
- **AC-CROSS-010**: `avg_odd == 3.0`.
- **AC-CROSS-011**: `avg_high == 3.0`.

### top_combinations 정렬 / 형식

- **AC-CROSS-012**: `top_n=3`일 때 `len(top_combinations) == 3`.
- **AC-CROSS-013**: 동률 정렬 — top_combinations 순서는 `[(1,5),(2,4),(6,0)]` (odd_count 오름차순, 그다음 high_count 오름차순).
- **AC-CROSS-014**: 각 top_combinations 항목은 `odd_count, high_count, count, pct` 키를 가진다.
- **AC-CROSS-015**: top_combinations 첫 항목의 `pct == 33.33`.
- **AC-CROSS-016**: `top_n` 기본값은 10이며, 조합 종류(3개)가 top_n보다 적으면 실제 조합 수만큼만 반환한다.

### 경계 / 빈 입력

- **AC-CROSS-017**: `get_cross_pattern_stats(None)` → `total_draws == 0`, matrix 49개 키 모두 0, top_combinations 빈 리스트, avg_odd==0.0, avg_high==0.0 (예외 없음).
- **AC-CROSS-018**: `get_cross_pattern_stats([])` → 빈 입력과 동일하게 0 채움 구조 반환.

### API

- **AC-CROSS-019**: `GET /api/stats/cross-pattern` → 200, 본문에 핵심 키 포함, top_n 기본 10.
- **AC-CROSS-020**: `GET /api/stats/cross-pattern?top_n=0` → 422, `?top_n=50` → 422; `?top_n=1`, `?top_n=49` → 200.

### Page

- **AC-CROSS-021**: `GET /stats/cross-pattern` → 200, HTML에 '조합 매트릭스' 문자열 포함, `active_tab=cross_pattern`.
- **AC-CROSS-022**: 데이터 부재(get_draws=None) 시에도 `/stats/cross-pattern` 200 응답 (빈 상태 렌더링).
