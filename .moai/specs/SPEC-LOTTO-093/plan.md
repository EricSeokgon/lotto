# SPEC-LOTTO-093 구현 계획

## 충돌 확인

- `get_first_last_zone_stats`, `_first_last_zone_cache`, `/stats/first_last_zone`
  미존재 확인 완료. 충돌 없음.
- 헬퍼 `_zone`은 함수로 정의되지 않았으나(`common_zone` 도큐먼트 문자열에만 등장),
  명확성을 위해 `_first_last_zone(n)` 이름 사용.
- SPEC-064 `get_min_max_stats`(값/범위)와는 별개 지표(구간 조합 분포).

## 구현 단계

1. data.py
   - 상수: `_FIRST_LAST_ZONE_KEYS = ["AA","AB","AC","BB","BC","CC"]`
   - 캐시: `_first_last_zone_cache: dict[str, Any] = {}`
   - 헬퍼: `_first_last_zone(n: int) -> str`
   - 함수: `get_first_last_zone_stats(draws)` — get_cluster_stats 뒤에 삽입
   - `invalidate_cache()`에 `_first_last_zone_cache.clear()` 추가

2. api.py — GET /stats/first_last_zone 엔드포인트

3. pages.py — GET /stats/first-last-zone 페이지 라우트

4. first_last_zone.html — 6키 분포 테이블 + 4 요약 카드 (low_high.html 패턴)

5. base.html — "첫끝구간" nav 링크 + active_tab 타이틀

## 테스트

`tests/test_first_last_zone_analysis.py` — ~27 tests (RED → GREEN)

## 캐시 격리

conftest.py의 autouse `_isolate_data_cache`가 invalidate_cache()를 호출하므로
`_first_last_zone_cache.clear()` 추가 후 자동 격리됨.
