---
id: SPEC-LOTTO-069
version: 1.0.0
status: completed
created: 2026-06-11
updated: 2026-06-11
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-069: 연속번호 패턴 분석 (Consecutive Number Pattern Analysis)

## HISTORY

- 2026-06-11 (v0.1.0 → v1.0.0): 구현 완료. +31 tests (1598→1629). GET /api/stats/consecutive-pairs, GET /stats/consecutive-pairs 구현. base.html 연속 쌍 nav 추가.
- 2026-06-11 (v0.1.0): 최초 작성 (Planned). 회차별 본번호 6개(보너스 제외)에서
  연속 쌍 `(n, n+1)`의 개수를 세고, 전체 회차에 대해 4개 고정 버킷
  (`"0"`, `"1"`, `"2"`, `"3+"`) 분포를 산출하는 읽기 전용 통계 기능으로 정의.
  SPEC-058·065·066·067·068의 `data.py` 확장 패턴을 그대로 따른다.

## 개요

각 회차의 당첨번호 6개(보너스 제외)에서 **연속 쌍(consecutive pair)** —
즉 같은 회차 안에 `n` 과 `n+1` 이 모두 존재하는 쌍 — 의 개수를 회차별로 센 뒤,
전체 이력에 대해 4개 고정 버킷의 분포를 분석한다. 연속 쌍 개수는 한국 로또
전략에서 가장 널리 쓰이는 지표 중 하나다.

### 연속 쌍(consecutive pair) 정의와 예시

"연속 쌍"은 같은 회차에 `n` 과 `n+1` 이 모두 등장하는 임의의 쌍이다.

| 회차 번호 (6개)            | 연속 쌍                         | 개수 |
|----------------------------|---------------------------------|------|
| `[3, 4, 14, 15, 16, 30]`   | (3,4), (14,15), (15,16)         | 3    |
| `[3, 5, 14, 20, 31, 42]`   | 없음                            | 0    |
| `[7, 8, 19, 27, 33, 45]`   | (7,8)                           | 1    |

세 개의 연속수가 한 줄로 이어지면(`14,15,16`) 인접 쌍 두 개 (14,15),(15,16) 로
계산된다. 즉 길이 `k` 의 연속 런은 `k-1` 개의 연속 쌍을 만든다.

### 4개 고정 버킷 (fixed)

| 버킷 키 (bucket) | 설명 |
|------------------|------|
| `"0"`            | 연속 쌍 없음 |
| `"1"`            | 연속 쌍 정확히 1개 |
| `"2"`            | 연속 쌍 정확히 2개 |
| `"3+"`           | 연속 쌍 3개 이상 (오버플로 버킷) |

`"3+"` 는 3,4,5… 를 모두 합치는 **오버플로 버킷**이다(`"3"`,`"4"` 를 따로 두지 않음).

### 응답 구조

```python
{
    "total_draws": int,
    "avg_consecutive_pairs": float,       # 회차당 평균 연속 쌍 개수, 2자리 반올림
    "most_common_bucket": str,            # "0", "1", "2", "3+" 중 하나
    "no_consecutive_pct": float,          # 연속 쌍 0개 회차 비율(%), 2자리 반올림
    "has_consecutive_pct": float,         # 연속 쌍 1개 이상 회차 비율(%), 2자리 반올림
    "consecutive_distribution": {
        "0":  {"count": int, "pct": float},
        "1":  {"count": int, "pct": float},
        "2":  {"count": int, "pct": float},
        "3+": {"count": int, "pct": float},
    },
}
```

빈 draws → 모든 값 0, 4개 버킷 모두 존재, `most_common_bucket=""`.

본 기능은 **읽기 전용 분석 기능**이다. 추천 로직·통계 분석 로직을 변경하지 않고
`data.py`의 확장 패턴(SPEC-058·065·066·067·068)을 그대로 따른다. 결과는 메모리에
캐시하며 DB에 영속화하지 않는다.

### 기존 연속 분석과의 구분 (중요)

lotto 프로젝트에는 이미 "연속" 도메인 분석이 두 개 존재한다. 본 SPEC-069는
**세 번째 독립 기능**이며, 둘 중 어느 것도 수정·병합하지 않는다.

| 기능 | 산출 | 라우트 | 캐시/함수 |
|------|------|--------|-----------|
| SPEC-043 | 런 길이(2~6) 분포, 윈도 지원 | `/patterns/consecutive` | `consecutive_pattern()` |
| SPEC-062 | 회차당 연속 쌍 개수(0..5) 분포 + 트리플 회차 수 | `/stats/consecutive-pattern` | `_consecutive_cache`, `get_consecutive_pattern_stats()` |
| **SPEC-069 (본 SPEC)** | **연속 쌍 개수 4버킷("0"/"1"/"2"/"3+") 분포** | `/stats/consecutive-pairs` | `_consecutive_pairs_cache`, `get_consecutive_pairs_stats()` |

[HARD] 네이밍 충돌 회피: `_consecutive_cache`, `get_consecutive_pattern_stats`,
`/stats/consecutive-pattern`, `consecutive_pattern.html` 는 **SPEC-062가 이미 사용 중**이다.
따라서 SPEC-069는 `consecutive_pairs` 네임스페이스를 사용한다(아래 구현 범위 표 참조).
SPEC-043·062 코드는 절대 수정/병합하지 않고 신규 함수만 추가한다.

## 요구사항 (EARS)

### 기능 요구사항

**REQ-069-F-001** [Ubiquitous]
The system SHALL count, for each historical draw, the number of consecutive pairs
`(n, n+1)` present among the 6 main numbers (the bonus number excluded).

**REQ-069-F-002** [Event-Driven]
WHEN the `/api/stats/consecutive-pairs` endpoint is called THEN the system SHALL
return a JSON response containing `total_draws`, `avg_consecutive_pairs`,
`most_common_bucket`, `no_consecutive_pct`, `has_consecutive_pct`, and
`consecutive_distribution` — where `consecutive_distribution` is a nested dict keyed
by the 4 bucket keys (`"0"`, `"1"`, `"2"`, `"3+"`), each mapping to `count` and `pct`.

**REQ-069-F-003** [Event-Driven]
WHEN the `/stats/consecutive-pairs` page is requested THEN the system SHALL render an
HTML page whose title and heading contain the text "연속", using the same stats dict.

**REQ-069-F-004** [Ubiquitous]
The system SHALL always include all 4 bucket keys (`"0"`, `"1"`, `"2"`, `"3+"`) in
`consecutive_distribution` (zero-filled when a bucket is absent from the data).

**REQ-069-F-005** [Event-Driven]
WHEN `invalidate_cache()` is called THEN `_consecutive_pairs_cache` SHALL be cleared.

**REQ-069-F-006** [Ubiquitous]
The system SHALL determine `most_common_bucket` as the bucket with the highest `count`;
on a tie, the bucket appearing earlier in `_CONSECUTIVE_BUCKETS`
(`["0", "1", "2", "3+"]`) SHALL win.

### 비기능 요구사항

**REQ-069-NF-001** [State-Driven]
IF the draws list is empty THEN the system SHALL return all-zero stats with all 4
buckets present (each `count=0`, `pct=0.0`) and `most_common_bucket=""` without
raising an exception.

**REQ-069-NF-002** [Unwanted]
The system SHALL NOT include the bonus number in consecutive-pair computation.

**REQ-069-NF-003** [Unwanted]
The system SHALL NOT modify `analyzer.py`, `models.py`, or `recommender.py`.
The system SHALL NOT modify SPEC-043 (`consecutive_pattern`) or SPEC-062
(`get_consecutive_pattern_stats`, `_consecutive_cache`) code.

**REQ-069-NF-004** [Ubiquitous]
Numeric ratio fields (`avg_consecutive_pairs`, `no_consecutive_pct`,
`has_consecutive_pct`, and each bucket `pct`) SHALL be rounded to 2 decimal places.

## 구현 범위

### 변경 파일

| 파일 | 변경 내용 | 델타 |
|------|-----------|------|
| `lotto/web/data.py` | `_consecutive_pairs_cache`, `_CONSECUTIVE_BUCKETS`, `_consecutive_bucket()`, `count_consecutive_pairs()`, `get_consecutive_pairs_stats()`, `invalidate_cache()` 수정 추가 | +~50 LOC |
| `lotto/web/routes/api.py` | `/api/stats/consecutive-pairs` API 핸들러 추가 | +~15 LOC |
| `lotto/web/routes/pages.py` | `/stats/consecutive-pairs` 페이지 핸들러 추가 | +~15 LOC |
| `lotto/web/templates/consecutive_pairs.html` | 통계 페이지 템플릿 생성 | NEW (~80 LOC) |
| `lotto/web/templates/base.html` | 네비게이션 링크 추가 (데스크탑+모바일) | +3 LOC |
| `tests/test_consecutive_pairs_analysis.py` | 테스트 파일 생성 (22+ 케이스) | NEW (~120 LOC) |

### 불변 파일

`lotto/analyzer.py`, `lotto/models.py`, `lotto/recommender.py`, `lotto/simulator.py`,
그리고 SPEC-043 `consecutive_pattern` / SPEC-062 `get_consecutive_pattern_stats` 관련 코드.

## 비목표 (Non-Goals)

- 추천 엔진 연동 (연속 쌍 분포 기반 가중치·필터 추가 금지)
- SPEC-043(런 길이 분포)·SPEC-062(0..5 개수 분포 + 트리플)와의 병합 또는 재작성
- 버킷 경계의 사용자 정의 (커스텀 버킷)
- DB 영속화
- 연속 쌍 개수 예측 모델
- 윈도(recent_n) 기반 부분 집계

## 전제조건

- Python 3.9+ 환경 (walrus `:=`, `zip(strict=True)`, `match-case` 사용 금지)
- SPEC-058, SPEC-065, SPEC-066, SPEC-067, SPEC-068 패턴이 `data.py`에 존재함
- 연속 쌍 산출에 `draw.numbers()` (6개 메인 번호) 사용
- SPEC-062가 `_consecutive_cache`/`get_consecutive_pattern_stats`를 이미 점유하므로
  SPEC-069는 `consecutive_pairs` 네임스페이스를 사용한다 (REQ-069-NF-003)
