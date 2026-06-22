# SPEC-LOTTO-109 구현 계획 (Plan)

## 방법론

TDD (RED-GREEN-REFACTOR). 신규 기능이므로 명세 테스트 우선.

## 변경 파일

1. **lotto/web/data.py**
   - `_gap_dist_cache: dict[str, Any] = {}` 캐시 선언 추가
   - `invalidate_cache()`에 `_gap_dist_cache.clear()` 추가
   - 상수: `_GAP_DIST_DISCLAIMER`, `_GAP_NUMBER_MAX=45`, `_GAP_BUCKETS`
   - 헬퍼: `_empty_gap_number_item(n, appearance_count)`,
     `_gap_histogram(gaps)`, `_build_gap_number_item(n, gaps, appearance_count)`
   - 메인: `get_gap_distribution(draws) -> dict[str, Any]` (@MX:ANCHOR)
     - top_n 파라미터 없음

2. **lotto/web/routes/api.py**
   - `GET /stats/gap-distribution` 라우트 (파라미터 없음)
   - `wd.get_gap_distribution(wd.get_draws())` 동적 호출

3. **lotto/web/routes/pages.py**
   - `GET /stats/gap-distribution` 페이지 라우트
   - `gap_distribution.html` 렌더, active_tab="gap_dist"

4. **lotto/web/templates/gap_distribution.html** (신규)
   - 전체 요약 섹션(avg_gap_all, max/min gap ever + 번호)
   - 45개 번호 테이블(번호 | 출현 | 간격수 | avg | min | max | std | 히스토그램 막대)
   - 면책 고지, Tailwind, 다크모드 지원, 서버 렌더링

5. **lotto/web/templates/base.html**
   - desktop_nav_items, nav_items에 `('/stats/gap-distribution', 'gap_dist', '간격 분포')` 추가
   - active_tab 서브타이틀 분기에 'gap_dist' 추가

6. **tests/test_gap_distribution.py** (신규, ~18 단위 + API/페이지)

## 알고리즘

```
get_gap_distribution(draws):
    if not draws: return 0 채움 구조
    sorted_draws = sorted(draws, key=lambda d: d.drwNo)
    # 번호별 출현 drwNo 수집 (단일 패스)
    occ: dict[int, list[int]] = {n: [] for n in 1..45}
    for draw in sorted_draws:
        for n in draw.numbers():
            occ[n].append(draw.drwNo)
    # 번호별 항목 + 전체 간격 누적
    all_gaps_with_owner = []  # (gap, number)
    numbers = []
    for n in 1..45:
        drwnos = occ[n]
        gaps = [drwnos[i+1]-drwnos[i] for i in range(len(drwnos)-1)]
        numbers.append(_build_gap_number_item(n, gaps, len(drwnos)))
        for g in gaps: all_gaps_with_owner.append((g, n))
    overall_summary = _overall_summary(all_gaps_with_owner)
    return {...}
```

- 동률 처리: max/min gap_number는 더 작은 번호 우선. 번호 1→45 순회에서
  `>`/`<` 비교(같으면 갱신 안 함)로 자연 보장.

## 검증

- `/home/sklee/.local/bin/pytest tests/test_gap_distribution.py -q --no-cov`
- `ruff check lotto/web/data.py lotto/web/routes/api.py lotto/web/routes/pages.py tests/test_gap_distribution.py`

## 회귀 주의

- `_draws_cache`/모듈 캐시 누수는 conftest autouse fixture가 처리(기존 패턴).
- 코어 모듈 불변, 기존 라우트 영향 없음.
