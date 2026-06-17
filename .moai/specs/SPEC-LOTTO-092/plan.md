# SPEC-LOTTO-092 구현 계획

## 목표

번호 군집 수(길이 2 이상 연속 정수 묶음 개수, 0~3) 분포 분석을 TDD로 구현한다.

## 충돌 검토 결과

- `get_cluster_stats` / `_count_clusters` / `_cluster_cache`: 미존재 (신규)
- `/api/stats/cluster_count`, `/stats/cluster-count`: 미존재 (신규)
- 기존 연속 지표(SPEC-069/062/078)와 정의가 구별됨 — 충돌 없음

## 구현 단위

1. SPEC 문서 (spec/plan/acceptance)
2. 테스트 작성 (RED) — `tests/test_cluster_analysis.py` (~27개)
3. data.py 구현 (GREEN)
   - 상수: `_cluster_cache`, `_CLUSTER_KEYS`
   - 헬퍼: `_count_clusters(numbers)`
   - 공개 API: `get_cluster_stats(draws)` — get_prime_neighbor_stats(091) 뒤 삽입
   - `invalidate_cache()`에 `_cluster_cache.clear()` 추가
4. API 라우트 — `lotto/web/routes/api.py` GET /stats/cluster_count
5. 페이지 라우트 — `lotto/web/routes/pages.py` GET /stats/cluster-count
6. 템플릿 — `lotto/web/templates/cluster_count.html` (odd_run.html 4키 패턴)
7. 네비게이션 — `base.html`에 "군집수" 링크 + title 블록

## 알고리즘

```python
def _count_clusters(numbers):
    sorted_nums = sorted(numbers)
    clusters = 0
    run_len = 1
    for i in range(1, len(sorted_nums)):
        if sorted_nums[i] == sorted_nums[i - 1] + 1:
            run_len += 1
        else:
            if run_len >= 2:
                clusters += 1
            run_len = 1
    if run_len >= 2:
        clusters += 1
    return min(clusters, 3)
```

## 검증

- `/home/sklee/.local/bin/pytest tests/test_cluster_analysis.py`
- `/home/sklee/.local/bin/ruff check` (신규 파일)
- 새 파일 mypy clean 확인
