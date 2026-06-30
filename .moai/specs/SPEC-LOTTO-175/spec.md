# SPEC-LOTTO-175: 완전수(Perfect Numbers) 포함 분포 분석

## 상태
DONE

## 목표
로또 당첨 번호 중 완전수(Perfect Number)가 몇 개 포함되는지 분포를 분석한다.

## 완전수 정의
완전수: 자신을 제외한 양의 약수의 합이 자신과 같은 수.
- 6 = 1 + 2 + 3
- 28 = 1 + 2 + 4 + 7 + 14

1~45 범위 내 완전수: {6, 28} — 2개
이론 기댓값 = 2/45 × 6 ≈ 0.267개/회

## 요구사항

### REQ-PERF-001
`get_perfect_analysis()` 함수가 `lotto/web/data.py`에 추가되어야 한다.

반환 형식:
- `total`: 전체 회차 수
- `perfect_count`: 완전수 개수 (2)
- `perfect_list`: 완전수 목록 [6, 28]
- `avg`: 회차당 평균 완전수 포함 수
- `expected`: 이론 기댓값 (≈0.267)
- `diff`: avg - expected
- `best_count`: 최빈 포함 개수
- `best_count_pct`: 최빈 개수 비율 (%)
- `zero_pct`: 0개 포함 회차 비율 (%)
- `dist_list`: [{count, draws, pct}] — 포함 개수별 분포
- `freq_list`: [{number, divisors, count, pct}] — 번호별 출현 빈도
- `recent`: 최근 20회차 상세 [{drwNo, numbers, perfects, count}]

### REQ-PERF-002
`/stats/perfect` GET 엔드포인트가 `lotto/web/routes/pages.py`에 추가되어야 한다.

### REQ-PERF-003
`lotto/web/templates/perfect.html` 템플릿이 작성되어야 한다.
- Bootstrap 5 + 그린(bg-success) 테마
- 요약 카드 4개
- 완전수 목록 배지
- 포함 개수 분포 테이블
- 번호별 출현 빈도 테이블
- 최근 20회차 현황 테이블

### REQ-PERF-004
네비게이션에 `/stats/perfect` (완전수) 항목이 추가되어야 한다.

### REQ-PERF-005
`tests/test_perfect.py`에 최소 10개 테스트가 작성되어야 한다.

## 완료 기준
- [ ] `get_perfect_analysis()` 구현 완료
- [ ] `/stats/perfect` 라우트 등록 완료
- [ ] `perfect.html` 템플릿 완료
- [ ] `base.html` 네비 항목 추가 완료
- [ ] 10개 테스트 통과
- [ ] ruff 린트 통과
