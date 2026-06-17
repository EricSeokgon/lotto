---
id: SPEC-LOTTO-100
version: 0.1.0
status: draft
created: 2026-06-17
updated: 2026-06-17
author: ircp
priority: high
issue_number: 0
---

# SPEC-LOTTO-100: 통계 기반 번호 조합 적합도 점수 (Fitness Score)

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 0.1.0 | 2026-06-17 | 최초 작성 | ircp |

---

## 개요

임의의 6개 번호 조합이 역대 로또 당첨 패턴에 얼마나 부합하는지를 0~100 점수로 평가하는 기능이다.
SPEC-LOTTO-050~099에서 구현된 50개 분포 통계 데이터를 활용하여, 각 통계 항목별 해당 버킷의 역사적 빈도 비율을 가중 평균하여 종합 점수(Fitness Score)를 산출한다.

---

## 배경

SPEC-LOTTO-050~099에서 로또 6/45 회차별 번호 패턴의 다양한 통계적 특성(홀짝 비율, 고저 비율, 번호 합계, 스팬, 연속 번호, 끝자리 분포, AC값, 사분위 분포, 구간 커버리지 등)을 분석하는 함수들이 구현되었다.

각 통계 함수는 해당 특성의 버킷별 역사적 빈도(count, pct)를 반환한다. 예를 들어 `get_odd_even_stats`는 홀수 개수별(0~6개) 분포를 반환하며, 특정 조합의 홀수 개수가 해당하는 버킷의 역사적 빈도 비율이 높을수록 그 조합은 통계적으로 더 "일반적인" 패턴에 부합한다고 볼 수 있다.

Fitness Score는 이 개념을 모든 주요 통계 항목에 걸쳐 통합하여, 사용자가 자신의 번호 조합이 역대 당첨 패턴과 얼마나 유사한지를 직관적인 0~100 점수로 확인할 수 있게 한다. 이 점수는 당첨 가능성을 예측하는 것이 아니라, 번호 조합이 과거 패턴에 얼마나 부합하는지를 나타내는 참고 지표이다.

---

## 요구사항 (EARS 형식)

### U (Ubiquitous — 항상 적용)

- **REQ-FS-U01**: 시스템은 본번호 6개(보너스 번호 제외)만을 사용하여 적합도 점수를 계산해야 한다.
- **REQ-FS-U02**: Fitness Score는 0.0 이상 100.0 이하의 실수(소수 2자리)여야 한다.
- **REQ-FS-U03**: 점수 산출에 사용되는 각 통계 항목의 가중치는 동일하게 1.0으로 설정한다.
- **REQ-FS-U04**: 적합도 점수는 `(각 항목 버킷 pct 합산 / 항목 수) * (100 / 100)` 공식으로 산출한다. 즉, 각 항목에서 해당 버킷의 역사적 빈도 비율(pct, 0~100%)을 수집하여 산술 평균한 값이 곧 Fitness Score이다.
- **REQ-FS-U05**: 캐시 키는 통계 캐시와 독립적으로 관리하며, 적합도 계산 자체는 캐시하지 않는다(매 요청마다 통계 캐시를 활용하여 계산).
- **REQ-FS-U06**: 점수 세부 내역(breakdown)은 사용된 각 통계 항목별 기여 점수를 포함해야 한다.

### E (Event-driven — 이벤트 발생 시)

- **REQ-FS-E01**: When `GET /api/stats/fitness?numbers=1,2,3,4,5,6` is called with a valid 6-number list, the system shall return JSON with `numbers`, `fitness_score`, `grade`, and `breakdown` fields.
- **REQ-FS-E02**: When `GET /stats/fitness` page is requested, the system shall render `fitness.html` template with a number input form and (if numbers are provided via query params) the fitness score result.
- **REQ-FS-E03**: When the user submits 6 numbers on the web page form, the system shall call the fitness API and display the score and breakdown without page reload (via JavaScript fetch).
- **REQ-FS-E04**: When `invalidate_cache()` is called, the system shall clear any fitness-related caches (현재 버전에서는 Fitness Score 자체를 캐시하지 않으므로 no-op이지만, 향후 캐시 추가에 대비해 hook을 유지한다).

### S (State-driven — 상태 조건)

- **REQ-FS-S01**: While draws list is None or empty, the system shall return `fitness_score=0.0`, `grade="데이터 없음"`, and `breakdown={}`.
- **REQ-FS-S02**: While the statistics cache is populated, the system shall use the cached statistics without recomputing base stats from draws.

### N (Negative — 금지 사항)

- **REQ-FS-N01**: The system shall NOT accept fewer or more than exactly 6 numbers; invalid count shall return HTTP 400 with `detail` message.
- **REQ-FS-N02**: The system shall NOT accept numbers outside the range 1–45; out-of-range numbers shall return HTTP 400.
- **REQ-FS-N03**: The system shall NOT accept duplicate numbers in the input; duplicates shall return HTTP 400.
- **REQ-FS-N04**: The system shall NOT claim the fitness score predicts winning probability; the API response and UI must include a disclaimer.
- **REQ-FS-N05**: The system shall NOT use `zip(strict=True)` — Python 3.9 호환을 위해 `# noqa: B905` 주석을 사용한다.
- **REQ-FS-N06**: The system shall NOT use `match`/`case` syntax — Python 3.9 호환을 위해 `if/elif/else` 체인을 사용한다.

### O (Optional — 선택 사항)

- **REQ-FS-O01**: Where the fitness score is in the top 20% (score >= 80), the grade should be "매우 높음"; 60~79 is "높음"; 40~59 is "보통"; 20~39 is "낮음"; 0~19 is "매우 낮음".
- **REQ-FS-O02**: The breakdown should display items sorted by descending contribution score for readability.

---

## 기술적 접근 방법

### 적합도 계산에 사용할 통계 항목 (15개)

각 항목은 6개 번호로부터 특성값을 계산한 뒤, 해당 특성값이 속하는 버킷의 역사적 빈도 비율(pct)을 가져온다.

| # | 항목 키 | 통계 함수 | 버킷 결정 방법 | 설명 |
|---|---------|----------|---------------|------|
| 1 | `odd_even` | `get_odd_even_stats` | 홀수 개수(0~6) → distribution 키 | 홀짝 비율 |
| 2 | `high_low` | `get_high_low_stats` | 저번호(1~22) 개수(0~6) → distribution 키 | 고저 비율 |
| 3 | `total_sum` | `get_total_sum_stats` | 번호 합계 → sum_distribution 키(구간) | 번호 합계 구간 |
| 4 | `span` | `get_span_stats` | max-min 값 → span_distribution 키(구간) | 스팬(최대-최소) |
| 5 | `consecutive` | `get_consecutive_pattern_stats` | 연속 쌍 개수(0~5) → pair_distribution 키 | 연속 번호 패턴 |
| 6 | `ac_value` | `get_ac_value_stats` | AC값(0~10) → ac_distribution 키 | AC값 분포 |
| 7 | `last_digit` | `get_last_digit_stats` | 각 번호의 끝자리별 분포 → 가장 높은 빈도 끝자리 조합의 pct 평균 | 끝자리 분포 |
| 8 | `quartile` | `get_quartile_dist_stats` | Q1~Q4 개수 조합 키("q1-q2-q3-q4") → quartile_distribution 키 | 사분위 분포 |
| 9 | `zone_coverage` | `get_zone_coverage_stats` | 커버 구간 수(1~6) → zone_coverage_distribution 키 | 구간 커버리지 |
| 10 | `min_gap` | `get_min_gap_dist_stats` | 최소 간격 값 → min_gap_distribution 키(구간) | 최소 간격 |
| 11 | `gap_median` | `get_gap_median_dist_stats` | 간격 중앙값 → gap_median_distribution 키(구간) | 간격 중앙값 |
| 12 | `decade` | `get_decade_stats` | 10단위별 번호 수 조합 패턴 → 해당 버킷 pct | 10단위 분포 |
| 13 | `prime` | `get_prime_stats` | 소수 개수 → prime_distribution 키 | 소수 개수 |
| 14 | `last_digit_sum` | `get_last_digit_sum_stats_route` 함수가 아닌 `get_last_digit_sum_stats` | 끝자리 합계 → sum_distribution 키(구간) | 끝자리 합계 구간 |
| 15 | `sum_last_digit` | `get_sum_last_digit_stats` | 번호 합계의 일의 자리(0~9) → distribution 키 | 합계 일의 자리 |

### 점수 계산 공식

```
# 각 항목에 대해:
# 1. 6개 번호에서 특성값(버킷 키) 계산
# 2. 해당 버킷의 pct 조회
# 3. 모든 항목 pct 합산 후 항목 수로 나눔

fitness_score = round(sum(item_pcts) / len(item_pcts), 2)
```

단, 버킷을 찾지 못하는 경우(미관측 패턴) 해당 항목 pct는 0.0으로 처리한다.

### 등급(Grade) 분류

| fitness_score | 등급 |
|--------------|------|
| 80.0 이상 | 매우 높음 |
| 60.0 이상 80.0 미만 | 높음 |
| 40.0 이상 60.0 미만 | 보통 |
| 20.0 이상 40.0 미만 | 낮음 |
| 20.0 미만 | 매우 낮음 |

### API 응답 구조 예시

```json
{
  "numbers": [1, 7, 14, 23, 35, 44],
  "fitness_score": 62.35,
  "grade": "높음",
  "disclaimer": "이 점수는 과거 통계와의 유사도를 나타내며 당첨 가능성을 예측하지 않습니다.",
  "breakdown": {
    "odd_even": {"label": "홀짝 비율", "bucket": "4", "pct": 28.52},
    "high_low": {"label": "고저 비율", "bucket": "3", "pct": 33.14},
    "total_sum": {"label": "번호 합계", "bucket": "121-130", "pct": 8.73},
    "span": {"label": "스팬", "bucket": "36-40", "pct": 15.42},
    "consecutive": {"label": "연속 번호", "bucket": "1", "pct": 41.23},
    "ac_value": {"label": "AC값", "bucket": "7", "pct": 12.88},
    "last_digit": {"label": "끝자리 분포", "bucket": "mixed", "pct": 9.30},
    "quartile": {"label": "사분위 분포", "bucket": "1-2-1-2", "pct": 6.45},
    "zone_coverage": {"label": "구간 커버리지", "bucket": "5", "pct": 52.80},
    "min_gap": {"label": "최소 간격", "bucket": "1", "pct": 48.20},
    "gap_median": {"label": "간격 중앙값", "bucket": "7-8", "pct": 22.10},
    "decade": {"label": "10단위 분포", "bucket": "1-1-1-1-1-1", "pct": 5.20},
    "prime": {"label": "소수 개수", "bucket": "2", "pct": 31.60},
    "last_digit_sum": {"label": "끝자리 합계", "bucket": "mid", "pct": 58.90},
    "sum_last_digit": {"label": "합계 일의 자리", "bucket": "5", "pct": 10.80}
  }
}
```

---

## 수정 대상 파일

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `lotto/web/data.py` | 수정 | `get_fitness_score(numbers: list[int], draws: list[DrawResult] \| None) -> dict[str, Any]` 함수 추가; `invalidate_cache()` 내 no-op hook 주석 추가 |
| `lotto/web/routes/api.py` | 수정 | `GET /api/stats/fitness` 엔드포인트 추가 (쿼리 파라미터: `numbers=1,2,3,4,5,6`) |
| `lotto/web/routes/pages.py` | 수정 | `GET /stats/fitness` 페이지 라우트 추가 |
| `lotto/web/templates/fitness.html` | 신규 | 적합도 점수 페이지 템플릿 (번호 입력 폼 + 점수 표시) |
| `lotto/web/templates/base.html` | 수정 | 사이드바 내비게이션에 "적합도 점수" 링크 추가 |
| `tests/web/test_fitness_score.py` | 신규 | TDD 테스트 파일 (최소 40개 AC 검증) |

---

## 제외 항목 (Exclusions)

- 번호 자동 추천 기능(점수 최적화 자동화)은 이 SPEC의 범위 밖이다
- 특정 회차와의 비교 기능은 포함하지 않는다
- 가중치 커스터마이징(사용자별 가중치 설정)은 포함하지 않는다
- 과거 회차 전체에 대한 배치 점수 계산은 포함하지 않는다
- Fitness Score의 캐시는 현재 버전에서 구현하지 않는다 (통계 캐시 재활용으로 충분)

---

## 제약사항

- Python 3.9 호환 (`match`/`case` 미사용, `zip(strict=True)` 미사용)
- 기존 SPEC 패턴 (SPEC-095~099) 일관성 유지
- 한국어 UI 라벨 사용
- ruff 린트 통과 필수
- 면책 고지(disclaimer) 필수 포함
