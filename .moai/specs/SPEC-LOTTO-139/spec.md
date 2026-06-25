# SPEC-LOTTO-139: 번호 소수(Prime Number) 분포 분석

## 개요
1~45 범위 내 소수(2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43) 14개의 당첨 번호 포함 빈도를 분석하는 페이지 구현. 이론적 기댓값(14/45×6≈1.867)과 실제 평균을 비교한다.

## 요구사항

### 기능 요구사항
- REQ-139-01: 소수 14개 목록 및 전체 대비 비율 표시
- REQ-139-02: 회차당 소수 포함 개수(0~6) 분포 통계
- REQ-139-03: 개별 소수별 출현 빈도 및 출현율 표시 (빈도 내림차순 정렬)
- REQ-139-04: 평균 소수 포함 수 vs 이론적 기댓값(14/45×6) 비교
- REQ-139-05: 최근 20회차 소수 포함 현황 테이블 (소수 강조 배지)

### 비기능 요구사항
- REQ-139-06: Bootstrap 5 반응형 UI (소수 배지: bg-warning text-dark)
- REQ-139-07: 데스크톱·모바일 양쪽 내비게이션에 링크 추가

## 기술 구현
- 분석 함수: `get_prime_number_dist_analysis()` in `lotto/web/data.py`
- 라우트: `GET /stats/prime-number-dist` in `lotto/web/routes/pages.py`
- 템플릿: `lotto/web/templates/prime_number_dist.html`
- 내비게이션: `lotto/web/templates/base.html` (데스크톱·모바일)
- 테스트: `tests/test_prime_number_dist.py` (10개)

## 인수 기준
- [x] prime_count == 14
- [x] dist_list 길이 7 (0~6개)
- [x] freq_list 길이 14
- [x] diff == round(avg_primes - expected, 3)
- [x] freq_list 내 모든 번호가 실제 소수
- [x] recent 길이 <= 20
- [x] `/stats/prime-number-dist` HTTP 200 응답
- [x] 전체 테스트 통과 (3343 → 3353)

## 커밋
- feat: `021074e` feat(SPEC-LOTTO-139): 번호 소수 분포 분석 구현 (+10 tests, 3343→3353)
