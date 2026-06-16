---
id: SPEC-LOTTO-074
version: 0.1.0
status: Planned
created: 2026-06-12
updated: 2026-06-12
author: ircp
priority: medium
---

# SPEC-LOTTO-074 인수 기준: 짝수 포함 개수 분포 분석

본 문서는 `get_even_count_stats` 와 관련 라우트의 인수 기준을 정의한다.
모든 인수 항목은 손계산으로 검증 가능한 결정적 픽스처를 사용한다.

## 검증용 픽스처 (손계산)

아래 4개 회차로 경계값 0·6 및 중간값을 모두 커버한다. 각 회차는 본번호 6개만
표기(보너스 제외). `even = sum(1 for n in numbers if n % 2 == 0)`.

| 회차 | 본번호 | 짝수 | even |
|------|--------|------|------|
| D1 | `[3, 7, 12, 20, 33, 44]` | `{12, 20, 44}` | **3** |
| D2 | `[2, 4, 6, 8, 10, 12]`   | `{2,4,6,8,10,12}` | **6** (모두) |
| D3 | `[1, 3, 5, 7, 9, 11]`    | `{}` | **0** (없음) |
| D4 | `[2, 3, 5, 6, 7, 11]`    | `{2, 6}` | **2** |

손계산 집계 (4개 회차):
- 분포: `{"0":1, "1":0, "2":1, "3":1, "4":0, "5":0, "6":1}`
- `avg_even_count = (3 + 6 + 0 + 2) / 4 = 11 / 4 = 2.75`
- `most_common_count`: 키 `"0","2","3","6"` 가 각 1회로 동률 → 가장 작은 값 **0**
- `high_even_pct`: even>=3 은 D1(3)·D2(6) 2건 → `2/4 * 100 = 50.0`
- 각 pct: `"0"`=25.0, `"2"`=25.0, `"3"`=25.0, `"6"`=25.0, 나머지=0.0

## 인수 기준 목록

### 계산 정확성

**AC-074-001** (REQ-EC-001)
D1 `[3,7,12,20,33,44]` 의 짝수 개수는 **3** 이다 (`{12,20,44}`).

**AC-074-002** (REQ-EC-001)
D2 `[2,4,6,8,10,12]` 의 짝수 개수는 **6** 이다 (여섯 번호 모두 짝수, 경계 최댓값).

**AC-074-003** (REQ-EC-001)
D3 `[1,3,5,7,9,11]` 의 짝수 개수는 **0** 이다 (짝수 없음, 경계 최솟값).

**AC-074-004** (REQ-EC-001)
D4 `[2,3,5,6,7,11]` 의 짝수 개수는 **2** 이다 (`{2,6}`).

**AC-074-005** (REQ-EC-008)
4개 픽스처(D1~D4)에 대해 `avg_even_count == 2.75` 이다.

### 응답 구조 및 분포

**AC-074-006** (REQ-EC-002)
`get_even_count_stats` 반환 dict 는 `total_draws`, `avg_even_count`,
`most_common_count`, `high_even_pct`, `even_count_distribution` 키를 모두 포함한다.

**AC-074-007** (REQ-EC-004)
`even_count_distribution` 은 항상 `"0","1","2","3","4","5","6"` 7개 키를 모두
포함한다 (미관측 구간 포함).

**AC-074-008** (REQ-EC-004)
각 분포 항목은 `count` 와 `pct` 두 키를 가진다.

**AC-074-009** (REQ-EC-004)
D1~D4 픽스처에 대해 분포 count 는
`{"0":1,"1":0,"2":1,"3":1,"4":0,"5":0,"6":1}` 이다.

**AC-074-010** (REQ-EC-004)
모든 버킷 count 의 합은 `total_draws` 와 같다 (4개 픽스처 → 합 4).

### 파생 지표

**AC-074-011** (REQ-EC-006)
D1~D4 픽스처에서 `most_common_count == 0` 이다 (동률 시 가장 작은 키 `"0"` 선택).

**AC-074-012** (REQ-EC-006)
동률 상황(여러 개수가 동수)에서는 **더 작은 even 값**이 선택된다
(고정 키 순서 `"0"`..`"6"` 선두 우선).

**AC-074-013** (REQ-EC-007)
D1~D4 픽스처에서 `high_even_pct == 50.0` 이다 (even>=3 인 D1·D2 2건 / 4건).

**AC-074-014** (REQ-EC-007)
모든 회차의 짝수 개수가 3 미만이면 `high_even_pct == 0.0` 이다.

**AC-074-015** (REQ-EC-NF-005)
`avg_even_count`, `high_even_pct`, 각 버킷 `pct` 는 소수 2자리로 반올림된다.

### 경계 및 예외

**AC-074-016** (REQ-EC-NF-001)
빈 draws 입력 시 예외 없이 반환되며, `total_draws == 0`,
`avg_even_count == 0.0`, `most_common_count == 0`,
`high_even_pct == 0.0`, 7개 키 모두 `count=0`·`pct=0.0` 이다.

**AC-074-017** (REQ-EC-NF-002)
짝수 개수 계산에 보너스 번호는 포함되지 않는다 (`draw.numbers()` 6개만 사용).

### 독립성 (SPEC-061 비간섭)

**AC-074-018** (REQ-EC-NF-004)
`get_even_count_stats` 호출은 SPEC-061 `get_odd_even_stats` 의 동작·반환값을
변경하지 않으며, `_odd_even_cache` 와 `_even_count_cache` 는 서로 독립적이다
(두 함수를 같은 draws 로 호출해도 상호 간섭이 없다).

### 라우트 및 캐시

**AC-074-019** (REQ-EC-002, REQ-EC-003)
`GET /api/stats/even_count` 는 HTTP 200 과 JSON 응답을 반환하며, 응답에
`even_count_distribution`(7키)·`avg_even_count`·`most_common_count`·
`high_even_pct` 가 포함된다. `GET /stats/even-count` 는 HTTP 200 과 HTML 을
반환하며, 페이지에 한국어 텍스트 "짝수개수" 가 포함되고 네비게이션에서 해당 탭이
활성화된다.

**AC-074-020** (REQ-EC-005)
`invalidate_cache()` 호출 후 `_even_count_cache` 가 비워지며, 다음 호출이
재계산된다. 또한 동일 draws 길이에 대한 반복 호출은 동일 결과를 반환한다(결정성).

## Definition of Done

- [ ] AC-074-001 ~ AC-074-020 전부 통과
- [ ] `tests/test_even_count_analysis.py` ~25개 테스트 통과
- [ ] 기존 통계 테스트 회귀 없음 (SPEC-061 홀짝 테스트 포함)
- [ ] `get_even_count_stats` 신규 추가, SPEC-061 `get_odd_even_stats` 미변경
- [ ] 코어 모듈(`analyzer.py`/`models.py`/`recommender.py`/`simulator.py`) 미수정
- [ ] Python 3.9 호환(walrus·zip(strict=)·match-case 미사용), 서버 렌더 전용
- [ ] mypy 신규 모듈 클린, `mypy.ini` override 등록
- [ ] `/api/stats/even_count` JSON·`/stats/even-count` 페이지 정상 동작
- [ ] `base.html` 네비 링크 2곳 추가 및 헤딩 분기 반영
