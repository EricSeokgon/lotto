# SPEC-LOTTO-107 인수 기준 (Acceptance Criteria)

기간별 번호 빈도 추이 분석의 검증 기준. 모든 수치는 아래 9회차 손계산 픽스처에서
직접 산출·검증되었다.

## 손계산 픽스처 (Fixture)

| 회차 | 본번호(sorted) |
|------|----------------|
| D1 | 1, 2, 3, 4, 5, 6 |
| D2 | 1, 7, 8, 9, 10, 11 |
| D3 | 2, 12, 13, 14, 15, 16 |
| D4 | 3, 17, 18, 19, 20, 21 |
| D5 | 4, 22, 23, 24, 25, 26 |
| D6 | 5, 27, 28, 29, 30, 31 |
| D7 | 6, 32, 33, 34, 35, 36 |
| D8 | 7, 37, 38, 39, 40, 41 |
| D9 | 1, 8, 42, 43, 44, 45 |

n=9, n//3=3, 2*n//3=6:
- early = draws[0:3] = D1,D2,D3 → period_sizes.early = 3
- middle = draws[3:6] = D4,D5,D6 → period_sizes.middle = 3
- recent = draws[6:9] = D7,D8,D9 → period_sizes.recent = 3

### 검증된 번호별 값 (verified)

| 번호 | count_early | count_middle | count_recent | pct_early | pct_middle | pct_recent | delta | trend |
|------|-------------|--------------|--------------|-----------|------------|------------|-------|-------|
| 1 | 2 (D1,D2) | 0 | 1 (D9) | 66.67 | 0.0 | 33.33 | -1 | falling |
| 2 | 2 (D1,D3) | 0 | 0 | 66.67 | 0.0 | 0.0 | -2 | falling |
| 6 | 1 (D1) | 0 | 1 (D7) | 33.33 | 0.0 | 33.33 | 0 | stable |
| 7 | 1 (D2) | 0 | 1 (D8) | 33.33 | 0.0 | 33.33 | 0 | stable |
| 8 | 1 (D2) | 0 | 1 (D9) | 33.33 | 0.0 | 33.33 | 0 | stable |
| 45 | 0 | 0 | 1 (D9) | 0.0 | 0.0 | 33.33 | 1 | rising |

> 주의: 번호 8은 D2에 포함되어 count_early=1 이며 delta=0(stable)이다.
> 번호 6·7도 동일하게 early/recent 각 1회로 delta=0(stable)이다.

### top_rising / top_falling (검증)

- top_rising (delta desc, number asc), top_n=10:
  32,33,34,35,36,37,38,39,40,41 (모두 delta=+1, recent 구간 D7·D8에서 처음 등장)
- top_falling (delta asc, number desc), top_n=10:
  2(delta=-2), 16,15,14,13,12,11,10,9,5 (delta=-1, number desc 정렬)

### trend 분포 (검증)

stable=18, rising=14, falling=13 (합계 45)

---

## 인수 기준 목록

### 핵심 계산 (Core Calculation)

- **AC-PT-001**: `get_period_trend(fixture_9())["total_draws"] == 9`.
- **AC-PT-002**: 반환 dict가 `{total_draws, top_n, period_sizes, numbers,
  top_rising, top_falling, disclaimer}` 키를 모두 포함한다.
- **AC-PT-003**: `period_sizes == {"early": 3, "middle": 3, "recent": 3}`.
- **AC-PT-004**: `numbers` 리스트 길이가 정확히 45이고, index 0의 `number == 1`,
  index 44의 `number == 45`.
- **AC-PT-005**: 번호 1 항목: count_early=2, count_middle=0, count_recent=1,
  pct_early=66.67, pct_middle=0.0, pct_recent=33.33, delta=-1, trend="falling".
- **AC-PT-006**: 번호 2 항목: count_early=2, count_recent=0, delta=-2,
  trend="falling".
- **AC-PT-007**: 번호 8 항목: count_early=1, count_recent=1, delta=0,
  trend="stable" (D2에 8 포함 검증).
- **AC-PT-008**: 번호 45 항목: count_early=0, count_recent=1, delta=1,
  trend="rising".
- **AC-PT-009**: 번호 6·7 항목: delta=0, trend="stable".
- **AC-PT-010**: trend 분포가 stable=18, rising=14, falling=13.

### 정렬 (Sorting)

- **AC-PT-011**: `top_rising` 길이 == top_n(기본 10); 모든 항목 delta >= top_rising
  마지막 항목 delta. 첫 5개 번호 == [32,33,34,35,36] (delta desc, number asc).
- **AC-PT-012**: `top_falling` 첫 항목 number==2, delta==-2; 이어지는 항목들은
  delta=-1 이며 number 내림차순([16,15,14,13,12,...]).
- **AC-PT-013**: `top_rising`/`top_falling` 각 항목이
  `{number, count_early, count_middle, count_recent, delta, trend}` 키를 가진다.
- **AC-PT-014**: top_n=5 호출 시 top_rising·top_falling 길이가 각각 5.

### 엣지 케이스 (Edge Cases)

- **AC-PT-015**: `get_period_trend(None)` → total_draws=0, period_sizes 모두 0,
  numbers 45개 전부 count 0·pct 0.0·delta 0·trend "stable", top_rising=[],
  top_falling=[].
- **AC-PT-016**: `get_period_trend([])` → AC-PT-015와 동일한 0 채움 구조.
- **AC-PT-017**: 1회차 입력(n=1, 본번호 포함) → period_sizes={early:0,middle:0,
  recent:1}; 해당 본번호의 count_recent=1, count_early=0, delta=1,
  trend="rising"; pct_early=0.0(빈 구간), pct_recent=100.0.
- **AC-PT-018**: 2회차 입력(n=2) → period_sizes={early:0, middle:1, recent:1}.

### API / 페이지

- **AC-PT-019**: `GET /api/stats/period-trend` → 200, 핵심 키 포함, top_n 기본 10.
  `top_n=0` 및 `top_n=46` → 422; `top_n=1`, `top_n=45` → 200.
- **AC-PT-020**: `GET /stats/period-trend` → 200, 본문에 "추이" 문자열 포함;
  데이터 부재(None) 시에도 200.
