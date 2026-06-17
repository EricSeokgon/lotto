# SPEC-LOTTO-041 구현 계획

## 마일스톤 (우선순위 기반)

### M1 (Priority High): 데이터 레이어 `range_stats`

- `lotto/web/data.py`에 `range_stats(start_drw, end_drw, draws=_UNSET)` 추가
- 기존 `dashboard_overview` 단일 O(N) 패스 패턴 + `_prize_beats`/`_draw_prize_payload`
  헬퍼 재사용
- 구간 필터링 → 빈도/홀짝/번호대/당첨금 집계
- 빈 구조 일관성 보장 (start>end, 빈 데이터, None 모두 동일 구조)
- 테스트: `tests/test_range_stats.py` (RED → GREEN)

### M2 (Priority High): API `GET /api/stats/range`

- `lotto/web/routes/api.py`에 `api_stats_range` 추가
- `start_drw`/`end_drw` Query(ge=1, required), `start > end` 검증 → 422
- `wd.get_draws()` 동적 호출 (테스트 patch 호환)
- 테스트: `tests/test_api_range_stats.py` (RED → GREEN)

### M3 (Priority Medium): 페이지 `GET /stats/range` + 템플릿 + 네비

- `lotto/web/routes/pages.py`에 `stats_range_page` 추가 (active_tab="stats_range")
- `lotto/web/templates/stats_range.html` 신규 (base.html 확장, 입력 폼 + 결과 영역)
- `base.html` 데스크톱/모바일 네비에 "구간 통계" 링크(`/stats/range`) 추가
- 테스트: `tests/test_range_stats_page.py` (RED → GREEN)

### M4 (Priority Low): REFACTOR + 전체 검증

- 중복 제거 / 네이밍 점검
- 전체 스위트 실행 (1003 + 12+ → 통과)

## 의존성

- M2는 M1 완료 후 (API가 range_stats 호출)
- M3는 M1 완료 후 (페이지가 range_stats 호출)
- M2, M3는 상호 독립

## @MX 태그 대상

- `range_stats`: `@MX:NOTE` + `@MX:SPEC` (신규 공개 집계 함수)
- API/페이지 라우트: `@MX:NOTE` + `@MX:SPEC`
