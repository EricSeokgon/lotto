# SPEC-LOTTO-076 구현 계획

## 개요

회차별 본번호 6개(보너스 제외) 중 4의 배수 개수(0~6) 분포를 분석하는 읽기 전용
통계 기능. SPEC-075(5의 배수)의 `data.py` 확장 패턴을 그대로 따른다.

## 변경 대상 파일

1. `lotto/web/data.py`
   - 모듈 레벨: `_mult4_cache`, `_MULT4_KEYS`, `_MULT4_SET` 추가
   - `get_mult4_stats(draws)` 함수 추가 (get_mult5_stats 뒤)
   - `invalidate_cache()`에 `_mult4_cache.clear()` 추가

2. `lotto/web/routes/api.py`
   - `GET /stats/mult4` 엔드포인트 추가

3. `lotto/web/routes/pages.py`
   - `GET /stats/mult4` 페이지 라우트 추가 (active_tab="mult4")

4. `lotto/web/templates/mult4.html` (신규)
   - mult5.html 패턴을 따른 다크모드 Tailwind 페이지

5. `lotto/web/templates/base.html`
   - 두 nav 리스트(desktop_nav_items, nav_items)에 4배수 링크 추가
   - 타이틀 블록에 `mult4` 분기 추가

6. `tests/test_mult4_analysis.py` (신규)
   - ~25개 테스트 (RED → GREEN)

## TDD 순서

1. RED: test_mult4_analysis.py 작성 → 실패 확인
2. GREEN: data.py 구현 → API/page 라우트 → 템플릿 → nav
3. REFACTOR: 기존 mult5 패턴과 일관성 검증

## 계산 규칙

- 4의 배수: {4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44} = 11개
- 분포 키: "0".."6" 7개 고정 (zero-fill)
- avg/most_common(동률 시 작은 값)/high(>=3 비율) 파생 지표

## 손계산 픽스처

- D1 [1,2,3,5,7,9] → 0
- D2 [4,8,12,16,20,24] → 6
- D3 [4,5,6,7,8,9] → 2 (4,8)
- D4 [10,20,30,40,41,42] → 2 (20,40)
- avg=(0+6+2+2)/4=2.5, high_pct=1/4=25.0, most_common=2
