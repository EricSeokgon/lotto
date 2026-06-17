---
id: SPEC-LOTTO-072
version: 0.1.0
status: Planned
created: 2026-06-12
updated: 2026-06-12
author: ircp
priority: medium
---

# SPEC-LOTTO-072 인수 기준: 끝자리 유니크 수 분포 분석

본 문서는 `get_last_digit_unique_stats` 와 관련 라우트의 인수 기준을 정의한다.
모든 인수 항목은 손계산으로 검증 가능한 결정적 픽스처를 사용한다.

## 검증용 픽스처 (손계산)

아래 4개 회차로 경계값 1·6 및 중간값을 모두 커버한다. 각 회차는 본번호 6개만
표기(보너스 제외). `unique = len(set(n % 10))`.

| 회차 | 본번호 | 끝자리(set) | unique |
|------|--------|-------------|--------|
| D1 | `[3, 7, 12, 25, 38, 44]` | `{3,7,2,5,8,4}` | **6** (모두 다름) |
| D2 | `[3, 13, 23, 31, 42, 5]` | `{3,1,2,5}`     | **4** |
| D3 | `[1, 11, 21, 31, 41, 45]`| `{1,5}`         | **2** |
| D4 | `[2, 12, 22, 32, 42, 5]` | `{2,5}`         | **2** |

손계산 집계 (4개 회차):
- 분포: `{"1":0, "2":2, "3":0, "4":1, "5":0, "6":1}`
- `avg_unique_count = (6 + 4 + 2 + 2) / 4 = 14 / 4 = 3.5`
- `most_common_count`: 최대 count 는 키 `"2"`(2회) → **2**
- `all_different_pct`: unique==6 은 D1 1건 → `1/4 * 100 = 25.0`
- 각 pct: `"2"`=50.0, `"4"`=25.0, `"6"`=25.0, 나머지=0.0

## 인수 기준 목록

### 계산 정확성

**AC-072-001** (REQ-LDU-001)
D1 `[3,7,12,25,38,44]` 의 유니크 끝자리 개수는 **6** 이다 (`{2,3,4,5,7,8}`).

**AC-072-002** (REQ-LDU-001)
D2 `[3,13,23,31,42,5]` 의 유니크 끝자리 개수는 **4** 이다 (`{1,2,3,5}`).

**AC-072-003** (REQ-LDU-001)
D3 `[1,11,21,31,41,45]` 의 유니크 끝자리 개수는 **2** 이다 (`{1,5}`).

**AC-072-004** (REQ-LDU-001)
단일 회차에서 6개 번호의 끝자리가 모두 동일한 경우
(예: `[5, 15, 25, 35, 45, ...]` 형태) 유니크 개수는 **1** 이다 (경계 최솟값).

**AC-072-005** (REQ-LDU-008)
4개 픽스처(D1~D4)에 대해 `avg_unique_count == 3.5` 이다.

### 응답 구조 및 분포

**AC-072-006** (REQ-LDU-002)
`get_last_digit_unique_stats` 반환 dict 는 `total_draws`, `avg_unique_count`,
`most_common_count`, `all_different_pct`, `unique_distribution` 키를 모두 포함한다.

**AC-072-007** (REQ-LDU-004)
`unique_distribution` 은 항상 `"1","2","3","4","5","6"` 6개 키를 모두 포함한다
(미관측 구간 포함).

**AC-072-008** (REQ-LDU-004)
각 분포 항목은 `count` 와 `pct` 두 키를 가진다.

**AC-072-009** (REQ-LDU-004)
D1~D4 픽스처에 대해 분포 count 는
`{"1":0,"2":2,"3":0,"4":1,"5":0,"6":1}` 이다.

**AC-072-010** (REQ-LDU-004)
모든 버킷 count 의 합은 `total_draws` 와 같다 (4개 픽스처 → 합 4).

### 파생 지표

**AC-072-011** (REQ-LDU-006)
D1~D4 픽스처에서 `most_common_count == 2` 이다 (키 `"2"` 가 2회로 최다).

**AC-072-012** (REQ-LDU-006)
동률 상황(예: count `"2"` 와 `"6"` 가 각각 동수)에서는 **더 작은 유니크 값**이
선택된다 (고정 키 순서 선두 우선).

**AC-072-013** (REQ-LDU-007)
D1~D4 픽스처에서 `all_different_pct == 25.0` 이다 (unique==6 인 D1 1건 / 4건).

**AC-072-014** (REQ-LDU-007)
모든 회차의 유니크 개수가 6 미만이면 `all_different_pct == 0.0` 이다.

**AC-072-015** (REQ-LDU-NF-004)
`avg_unique_count`, `all_different_pct`, 각 버킷 `pct` 는 소수 2자리로 반올림된다.

### 경계 및 예외

**AC-072-016** (REQ-LDU-NF-001)
빈 draws 입력 시 예외 없이 반환되며, `total_draws == 0`,
`avg_unique_count == 0.0`, `most_common_count == 1`,
`all_different_pct == 0.0`, 6개 키 모두 `count=0`·`pct=0.0` 이다.

**AC-072-017** (REQ-LDU-NF-002)
유니크 끝자리 계산에 보너스 번호는 포함되지 않는다 (`draw.numbers()` 6개만 사용).

### 라우트 및 캐시

**AC-072-018** (REQ-LDU-002)
`GET /api/stats/last_digit_unique` 는 HTTP 200 과 JSON 응답을 반환하며,
응답에 `unique_distribution`(6키)·`avg_unique_count`·`most_common_count`·
`all_different_pct` 가 포함된다.

**AC-072-019** (REQ-LDU-003)
`GET /stats/last-digit-unique` 는 HTTP 200 과 HTML 을 반환하며, 페이지에
한국어 텍스트 "끝자리유니크" 가 포함되고 네비게이션에서 해당 탭이 활성화된다.

**AC-072-020** (REQ-LDU-005)
`invalidate_cache()` 호출 후 `_last_digit_unique_cache` 가 비워지며, 다음 호출이
재계산된다. 또한 동일 draws 길이에 대한 반복 호출은 동일 결과를 반환한다(결정성).

## Definition of Done

- [ ] AC-072-001 ~ AC-072-020 전부 통과
- [ ] `tests/test_last_digit_unique_analysis.py` ~25개 테스트 통과
- [ ] 기존 SPEC-055/063 끝자리 테스트 회귀 없음
- [ ] `get_last_digit_unique_stats` 신규 추가, 기존 끝자리 함수 미수정
- [ ] 코어 모듈(`analyzer.py`/`models.py`/`recommender.py`/`simulator.py`) 미수정
- [ ] Python 3.9 호환(walrus·zip(strict=)·match-case 미사용), 서버 렌더 전용
- [ ] mypy 신규 모듈 클린, `mypy.ini` override 등록
- [ ] `/api/stats/last_digit_unique` JSON·`/stats/last-digit-unique` 페이지 정상 동작
- [ ] `base.html` 네비 링크 2곳 추가 및 헤딩 분기 반영
