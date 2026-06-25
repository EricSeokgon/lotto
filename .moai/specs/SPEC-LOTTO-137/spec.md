# SPEC-LOTTO-137: 번호 끝자리(일의 자리) 분포 분석

## 개요
당첨 번호의 일의 자리(0~9)별 출현 빈도 및 분포 분석 페이지 구현.

## 요구사항

### 기능 요구사항
- REQ-137-01: 끝자리(0~9)별 풀 크기 계산 (1~45 중 각 끝자리 번호 수)
- REQ-137-02: 끝자리별 총 출현 횟수·평균 및 이론적 기댓값 비교
- REQ-137-03: 끝자리별 회차당 포함 개수 분포(0~6) 통계
- REQ-137-04: 가장 많이/적게 나온 끝자리 하이라이트
- REQ-137-05: 최근 20회차 끝자리 현황 테이블

### 비기능 요구사항
- REQ-137-06: Bootstrap 5 반응형 UI
- REQ-137-07: 데스크톱·모바일 양쪽 내비게이션에 링크 추가

## 기술 구현
- 분석 함수: `get_units_digit_analysis()` in `lotto/web/data.py`
- 라우트: `GET /stats/units-digit` in `lotto/web/routes/pages.py`
- 템플릿: `lotto/web/templates/units_digit.html`
- 내비게이션: `lotto/web/templates/base.html` (데스크톱·모바일)
- 테스트: `tests/test_units_digit.py` (10개)

## 인수 기준
- [x] digit_stats 리스트 길이 10 (끝자리 0~9)
- [x] 풀 크기 합계 = 45
- [x] 각 끝자리 dist_list 길이 7
- [x] diff = avg - expected
- [x] `/stats/units-digit` HTTP 200 응답
- [x] 전체 테스트 통과 (3323 → 3333)

## 커밋
- feat: `07b5362` feat(SPEC-LOTTO-137): 번호 끝자리(일의 자리) 분포 분석 구현 (+10 tests, 3323→3333)
