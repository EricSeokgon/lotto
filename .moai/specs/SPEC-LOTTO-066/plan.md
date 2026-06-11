---
id: SPEC-LOTTO-066
version: 0.1.0
status: Planned
created: 2026-06-11
updated: 2026-06-11
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-066 구현 계획

## 방법론

TDD (RED → GREEN → REFACTOR), 브라운필드 보강. 기존 동작을 보존하며 읽기 전용
통계 분석 계층만 추가한다. 데이터 계층(`get_prime_sum_stats`) → API 계층
(`/api/stats/prime_sum`) → 페이지/템플릿 계층(`/stats/prime_sum`) 순으로
각 계층마다 실패 테스트 작성 후 최소 구현.

핵심 재사용: `data.py`의 `_PRIMES_1_45` 상수 및 캐시/분포 패턴
(SPEC-058: `get_prime_stats`, SPEC-065: `get_std_stats`).

## 변경 파일

| 파일 | 변경 내용 | 델타 |
|------|-----------|------|
| `lotto/web/data.py` | `_prime_sum_cache`, `_PRIME_SUM_BUCKET_BOUNDS`, `get_prime_sum_stats()`, `invalidate_cache()` 수정 | +60 LOC |
| `lotto/web/routes/pages.py` | `stats_prime_sum_page()` 핸들러 | +10 LOC |
| `lotto/web/routes/api.py` | `get_prime_sum()` 핸들러 | +8 LOC |
| `lotto/web/templates/prime_sum.html` | 통계 페이지 템플릿 | +90 LOC |
| `lotto/web/templates/base.html` | nav 링크 추가 (데스크탑+모바일) | +2 LOC |
| `tests/test_prime_sum_analysis.py` | 테스트 파일 (20+ 케이스) | +200 LOC |

## 구현 단계

### 단계 1: data.py — 통계 계산 함수 (REQ-066-F-001, F-004, F-005, F-006, NF-001~004)

```
1-1. _prime_sum_cache 딕셔너리 변수 선언
1-2. _PRIME_SUM_BUCKET_BOUNDS 상수 및 버킷 레이블 정의
     버킷: "0-30", "30-60", "60-90", "90-120", "120-150", "150+"
1-3. _PRIME_SUM_LOW_MAX = 40, _PRIME_SUM_HIGH_MIN = 81 상수 정의
1-4. get_prime_sum_stats(draws) 구현
     - 캐시 히트 체크 (key: str(len(draws)))
     - draws 빈 경우 → 0-값 딕셔너리 반환 (6 버킷 zero-fill)
     - 각 draw.numbers()에서 소수만 추출하여 합산
     - 분포 버킷 집계, 3-tier 집계
     - avg/min/max 계산, most_common_bucket 산출
     - 결과 캐시 저장 후 반환
1-5. invalidate_cache()에 _prime_sum_cache.clear() 추가
```

### 단계 2: routes/pages.py, routes/api.py — 라우트 핸들러

```
2-1. pages.py에 stats_prime_sum_page() 추가
     GET /stats/prime_sum → _render(request, "prime_sum.html", {...})
2-2. api.py에 get_prime_sum() 추가
     GET /api/stats/prime_sum → wd.get_prime_sum_stats(wd.get_draws())
```

### 단계 3: templates — HTML 페이지

```
3-1. prime_sum.html 생성 (SPEC-065 std_analysis.html 패턴 참조)
     - 빈 상태 처리: {% if stats.total_draws == 0 %}
     - 요약 카드: 총 회차, 평균 소수합, 최솟값/최댓값
     - 3-tier 분포 카드: 낮음/중간/높음 비율
     - 버킷 분포 테이블: 6개 행
     - Tailwind CSS 다크모드 지원
3-2. base.html nav에 "소수합" 링크 추가 (데스크탑 + 모바일 드롭다운)
```

### 단계 4: tests — 테스트 (20+ 케이스)

```
테스트 파일: tests/test_prime_sum_analysis.py

필수 케이스:
- 빈 데이터: 모든 0, 6 버킷 존재
- 단일 draw(소수 없음): prime_sum=0, low=1
- 단일 draw(소수 1개): prime_sum=소수값
- 단일 draw(소수만): prime_sum=합산값
- 보너스 번호 제외 검증
- avg/min/max 정확성
- 버킷 분류 경계값 (0, 29, 30, 59, 60, ...)
- 3-tier 경계값 (39, 40, 80, 81)
- 분포 비율 합계 ≈ 100.0
- most_common_bucket 동점 처리
- 캐시 히트 (동일 len)
- 캐시 미스 (다른 len)
- 캐시 무효화 (invalidate_cache)
- API 엔드포인트 200 + JSON 구조
- 페이지 엔드포인트 200
- 실제 데이터 smoke test
```

## 핵심 알고리즘

```python
# prime_sum 계산 (draw당)
prime_sum = sum(n for n in draw.numbers() if n in _PRIMES_1_45)

# 버킷 분류
def _prime_sum_bucket(s: int) -> str:
    if s < 30:   return "0-30"
    if s < 60:   return "30-60"
    if s < 90:   return "60-90"
    if s < 120:  return "90-120"
    if s < 150:  return "120-150"
    return "150+"

# 3-tier 분류
if prime_sum < 40:    tier = "low"
elif prime_sum <= 80: tier = "mid"
else:                 tier = "high"
```

## 예상 prime_sum 범위 및 버킷 근거

- 평균 소수 개수: ~2~3개/회차 (SPEC-058 기준)
- 자주 등장 소수: 7, 11, 13, 17, 19, 23 → 평균 합 약 50~70
- 버킷 "30-60", "60-90"에 대부분 집중 예상
- Low(0-39)에는 소수가 0~1개인 회차, High(81+)에는 소수 4~6개인 회차 분포

## 테스트 목표

- 현재 테스트 수: 1515개
- 목표: +20 테스트 → 1535개
- 모든 REQ 커버리지 달성
