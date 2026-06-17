# SPEC-LOTTO-080 구현 계획

## 충돌 검토 결과

- 기존 `get_gap_stats`(SPEC-LOTTO-056): 인접 간격 전체를 small/medium/large로 분류,
  평균/위치별 평균/최빈 간격 + `avg_max_gap`(회차별 max gap의 평균) 단일 수치 제공.
  → **max gap의 구간별 분포는 제공하지 않음**.
- `get_max_gap_dist_stats`, `_max_gap_dist_cache`, `/stats/max_gap_dist`,
  `/stats/max-gap-dist` 모두 미존재 → 충돌 없음.

## 변경 파일

1. `lotto/web/data.py`
   - 상수: `_MAX_GAP_KEYS`, `_max_gap_dist_cache` (SPEC-079 상수 영역 인접).
   - `invalidate_cache()`에 `_max_gap_dist_cache.clear()` 추가.
   - 헬퍼 `_max_gap_bucket(g)` + 함수 `get_max_gap_dist_stats(draws)`
     (`get_digit_sum_dist_stats` 이후 삽입).
2. `lotto/web/routes/api.py`: GET /api/stats/max_gap_dist
3. `lotto/web/routes/pages.py`: GET /stats/max-gap-dist
4. `lotto/web/templates/max_gap_dist.html`: 다크모드 Tailwind 페이지
5. `lotto/web/templates/base.html`: "최대간격" nav 링크 (데스크탑/모바일 + active_tab 제목)
6. `tests/test_max_gap_dist_analysis.py`: RED 테스트

## TDD 절차

- RED: 테스트 작성 → 실패 확인 (함수 미존재)
- GREEN: data.py/api/pages/template/nav 구현 → 테스트 통과
- REFACTOR: SPEC-079 패턴과 일관성 유지, 중복 제거 검토

## 응답 구조

```python
{
    "total_draws": int,
    "avg_max_gap": float,        # 회차별 max_gap 평균, 2dp
    "most_common_range": str,    # 최빈 구간 (동률 시 앞선 구간)
    "high_gap_pct": float,       # max_gap >= 21 비율, 2dp
    "max_gap_distribution": {각 구간: {"count": int, "pct": float}},
}
```

## 캐시 정책

- 캐시 키: `str(len(draws))` (빈 입력은 "0").
- `invalidate_cache()`로 무효화.
- conftest의 autouse `_isolate_data_cache` 픽스처가 테스트 간 격리.
