---
id: SPEC-LOTTO-049
version: 0.1.0
status: Planned
created: 2026-06-02
updated: 2026-06-02
author: ircp
priority: medium
---

# SPEC-LOTTO-049 인수 기준

## 데이터 계층 — sum_range_analysis

- AC-01: 픽스처(합계 30/75/100/138x3)에서 avg_sum=103.17, min_sum=30, max_sum=138. (REQ-SUM-001)
- AC-02: distribution은 12개 버킷을 오름차순으로 나열하며 각 항목 키는 {range, low, high, count, ratio}. (REQ-SUM-002)
- AC-03: 버킷 count/ratio 정확 — 121-140 count=3 ratio=0.5, 21-40 count=1, 241-255 count=0. (REQ-SUM-002)
- AC-04: most_common_range == "121-140". (REQ-SUM-001)
- AC-05: count 동률 시 더 낮은 구간 선택. (REQ-SUM-007)
- AC-06: common_zone == {low:30, high:138} (nearest-rank p10/p90). (REQ-SUM-003)
- AC-07: 빈 리스트 → total_draws=0, avg/min/max=0, most_common_range=null, 12버킷 count 0, common_zone {0,0}. (REQ-SUM-009)
- AC-08: 명시적 None → 빈 구조 (get_draws 호출 없음). (REQ-SUM-009)
- AC-09: 결정적 (동일 입력 동일 출력). (REQ-SUM-001)

## 데이터 계층 — evaluate_sum

- AC-10: 합계 100 → in_common_zone=True, percentile=0.5, common_zone {30,138}. (REQ-SUM-004)
- AC-11: 합계 21 → in_common_zone=False, percentile=0.0. (REQ-SUM-004)
- AC-12: 데이터 부재 → percentile=0.0, common_zone {0,0}, 합계는 정상 계산. (REQ-SUM-010)

## API 계층

- AC-13: GET /api/stats/sum-range → 200 + 7개 키 + distribution 12개. (REQ-SUM-005)
- AC-14: get_draws None → 200, total_draws=0, most_common_range=null. (REQ-SUM-009)
- AC-15: GET /api/stats/sum-range/evaluate?n=...(6개 유효) → 200 + {sum, in_common_zone, common_zone, percentile}. (REQ-SUM-004)
- AC-16: n 6개 미만 → 422. (REQ-SUM-008)
- AC-17: n 범위 밖(46) → 422. (REQ-SUM-008)
- AC-18: n 중복 → 422. (REQ-SUM-008)

## 페이지 계층

- AC-19: GET /stats/sum-range → 200 HTML, "합계" 포함. (REQ-SUM-006)
- AC-20: 차트(sumRangeChart canvas)/테이블/최빈 구간 라벨 마커 포함. (REQ-SUM-006)
- AC-21: get_draws None → 200 빈 상태("데이터가 없습니다"). (REQ-SUM-009)
- AC-22: GET / 응답에 href="/stats/sum-range" 네비 링크 포함. (REQ-SUM-006)

## 품질

- AC-Q1: mypy . = Success (신규 테스트 모듈 mypy.ini 등록).
- AC-Q2: ruff clean, 신규 외부 의존성 없음.
- AC-Q3: 전체 테스트 스위트 1143 → 1165 통과.
