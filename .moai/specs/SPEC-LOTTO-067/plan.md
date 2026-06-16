---
id: SPEC-LOTTO-067
version: 0.1.0
status: Planned
created: 2026-06-11
updated: 2026-06-11
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-067 구현 계획

## 방법론

TDD (RED → GREEN → REFACTOR), 브라운필드 보강. 기존 동작을 보존하며 읽기 전용
통계 분석 계층만 추가한다. 데이터 계층(`get_total_sum_stats`) → API 계층
(`/api/stats/total_sum`) → 페이지/템플릿 계층(`/stats/total_sum`) 순으로
각 계층마다 실패 테스트 작성 후 최소 구현.

핵심 재사용: `data.py`의 캐시/분포/3-tier 패턴
(SPEC-065: `get_std_stats`, SPEC-066: `get_prime_sum_stats`).

## 변경 파일

| 파일 | 변경 내용 | 델타 |
|------|-----------|------|
| `lotto/web/data.py` | `_total_sum_cache`, `_TOTAL_SUM_BUCKETS`, `get_total_sum_stats()`, `invalidate_cache()` 수정 | +55 LOC |
| `lotto/web/routes/pages.py` | `stats_total_sum_page()` 핸들러 | +10 LOC |
| `lotto/web/routes/api.py` | `get_total_sum()` 핸들러 | +8 LOC |
| `lotto/web/templates/total_sum.html` | 통계 페이지 템플릿 | +90 LOC |
| `lotto/web/templates/base.html` | nav 링크 추가 (데스크탑+모바일) | +2 LOC |
| `tests/test_total_sum_analysis.py` | 테스트 파일 (20+ 케이스) | +200 LOC |

## 구현 단계

### 단계 1: data.py — 통계 계산 함수 (REQ-067-F-001, F-004, F-005, F-006, NF-001~004)

```
1-1. _total_sum_cache 딕셔너리 변수 선언
1-2. _TOTAL_SUM_BUCKETS 상수 정의
     버킷: "21-80", "81-110", "111-130", "131-150", "151-170", "171-255"
1-3. _TOTAL_SUM_LOW_MAX = 110, _TOTAL_SUM_HIGH_MIN = 171 상수 정의
1-4. get_total_sum_stats(draws) 구현
     - 캐시 히트 체크 (key: str(len(draws)))
     - draws 빈 경우 → 0-값 딕셔너리 반환 (6 버킷 zero-fill)
     - 각 draw.numbers()의 6개 번호 합산 (sum())
     - 분포 버킷 집계, 3-tier 집계
     - avg/min/max 계산, most_common_bucket 산출
     - 결과 캐시 저장 후 반환
1-5. invalidate_cache()에 _total_sum_cache.clear() 추가
```

### 단계 2: routes/pages.py, routes/api.py — 라우트 핸들러

```
2-1. pages.py에 stats_total_sum_page() 추가
     GET /stats/total_sum → _render(request, "total_sum.html", {...})
2-2. api.py에 get_total_sum() 추가
     GET /api/stats/total_sum → wd.get_total_sum_stats(wd.get_draws())
```

### 단계 3: templates — HTML 페이지

```
3-1. total_sum.html 생성 (SPEC-066 prime_sum.html 패턴 참조)
     - 빈 상태 처리: {% if stats.total_draws == 0 %}
     - 요약 카드: 총 회차, 평균 총합, 최솟값/최댓값
     - 3-tier 분포 카드: 낮음/중간/높음 비율
     - 버킷 분포 테이블: 6개 행
     - Tailwind CSS 다크모드 지원
3-2. base.html nav에 "총합" 링크 추가 (데스크탑 + 모바일 드롭다운)
```

### 단계 4: tests — 테스트 (20+ 케이스)

```
테스트 파일: tests/test_total_sum_analysis.py

필수 케이스:
- 빈 데이터: 모든 0, 6 버킷 존재
- 단일 draw(최솟값 = 21): sum=21, low=1, "21-80"
- 단일 draw(최댓값 = 255): sum=255, high=1, "171-255"
- 보너스 번호 제외 검증
- avg/min/max 정확성
- 버킷 분류 경계값 (80/81, 110/111, 130/131, 150/151, 170/171)
- 3-tier 경계값 (109/110, 170/171)
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
# total_sum 계산 (draw당)
total_sum = sum(draw.numbers())

# 버킷 분류
def _total_sum_bucket(s: int) -> str:
    if s <= 80:  return "21-80"
    if s <= 110: return "81-110"
    if s <= 130: return "111-130"
    if s <= 150: return "131-150"
    if s <= 170: return "151-170"
    return "171-255"

# 3-tier 분류
if total_sum < 110:    tier = "low"
elif total_sum <= 170: tier = "mid"
else:                  tier = "high"
```

## 버킷 근거 (통계 기반)

- 기댓값 E[sum] = 138, SD ≈ 30 (비복원 추출)
- "21-80": E - 2SD 이하 (~2% 회차)
- "81-110": E - 1SD ~ E - 0.9SD 구간 (~11% 회차)
- "111-130": E - 0.9SD ~ E - 0.3SD 구간 (~22% 회차)
- "131-150": E ± 0.4SD 구간 (~27% 회차, 최빈 구간)
- "151-170": E + 0.4SD ~ E + 1.1SD 구간 (~22% 회차)
- "171-255": E + 1.1SD 이상 (~16% 회차)

## 테스트 목표

- 현재 테스트 수: 1541개
- 목표: +20 테스트 → 1561개
- 모든 REQ 커버리지 달성
