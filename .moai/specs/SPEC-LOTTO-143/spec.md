# SPEC-LOTTO-143: 합성수(Composite Number) 분포 분석

## 개요
1~45 내 합성수(소수·1 제외) 30개의 당첨 번호 포함 빈도 분석 페이지 구현.

## 요구사항

### 기능 요구사항
- REQ-143-01: 합성수 30개 정의 및 포함 개수(0~6) 분포 분석
- REQ-143-02: 실제 평균 포함 수 vs 이론적 기댓값(30/45×6=4.0) 비교
- REQ-143-03: 상위 15개 최빈 합성수 출현 빈도 순위
- REQ-143-04: 하위 5개 최저 빈도 합성수 표시
- REQ-143-05: 최근 20회차 합성수 포함 현황 테이블

### 비기능 요구사항
- REQ-143-06: Bootstrap 5 반응형 UI
- REQ-143-07: 데스크톱·모바일 양쪽 내비게이션에 링크 추가

## 기술 구현
- 분석 함수: `get_composite_analysis()` in `lotto/web/data.py`
- 라우트: `GET /stats/composite` in `lotto/web/routes/pages.py`
- 템플릿: `lotto/web/templates/composite.html`
- 내비게이션: `lotto/web/templates/base.html` (데스크톱·모바일)
- 테스트: `tests/test_composite.py` (10개)

## 인수 기준
- [x] composite_count == 30
- [x] expected == 4.0
- [x] dist_list 길이 7
- [x] freq_list 최대 15개
- [x] `/stats/composite` HTTP 200 응답
- [x] 전체 테스트 통과 (3383 → 3393)
