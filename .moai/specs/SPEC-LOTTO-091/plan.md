---
id: SPEC-LOTTO-091
title: 소수 이웃 번호 포함 분포 분석 — 구현 계획
status: Planned
version: 0.1.0
created: 2026-06-16
---

# 구현 계획

## 충돌 확인

- `get_prime_neighbor_stats` / "prime_neighbor" / `/stats/prime_neighbor` 미존재 확인 완료.
- SPEC-058 `get_prime_stats`(소수 개수만)와 정의·출력 구조가 다른 별개 함수.

## 변경 파일

1. `lotto/web/data.py`
   - 상수 추가: `_PRIME_NEIGHBOR_SET`(frozenset), `_PRIME_NEIGHBOR_KEYS`
   - 캐시 추가: `_prime_neighbor_cache`
   - 헬퍼 추가: `_count_prime_neighbors(numbers)`
   - 함수 추가: `get_prime_neighbor_stats(draws)` (SPEC-090 get_sum_last_digit_stats 패턴)
   - `invalidate_cache()`에 `_prime_neighbor_cache.clear()` 추가
2. `lotto/web/routes/api.py`
   - GET /api/stats/prime_neighbor 엔드포인트 추가
3. `lotto/web/routes/pages.py`
   - GET /stats/prime-neighbor 페이지 라우트 추가
4. `lotto/web/templates/prime_neighbor.html`
   - 7키 분포 다크모드 Tailwind 템플릿
5. `lotto/web/templates/base.html`
   - "소수이웃" 네비 링크 + active_tab 타이틀 추가
6. `tests/test_prime_neighbor_analysis.py`
   - ~27 테스트 (RED → GREEN)

## 핵심 로직

```python
_PRIME_NEIGHBOR_SET = frozenset([
    1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20,
    22, 23, 24, 28, 29, 30, 31, 32, 36, 37, 38, 40, 41, 42, 43, 44
])

def _count_prime_neighbors(numbers):
    return sum(1 for n in numbers if n in _PRIME_NEIGHBOR_SET)
```

## 검증

- `/home/sklee/.local/bin/pytest tests/test_prime_neighbor_analysis.py`
- `/home/sklee/.local/bin/ruff check lotto/web/data.py`
- Python 3.9 호환(walrus/zip(strict)/match 미사용)
