# SPEC-LOTTO-087 인수 기준

| ID | 시나리오 | 기대 |
|----|----------|------|
| AC-01 | 빈 draws | total_draws=0, avg_median=0.0, most_common_range="1-9", central_median_pct=0.0 |
| AC-02 | None draws | 빈 구조, 5개 키 0 |
| AC-03 | 빈 draws 분포 | 5개 키 전부 count=0, pct=0.0 |
| AC-04 | [1,2,3,4,5,6] median=3.5 | "1-9" count=1 |
| AC-05 | [20,21,22,23,24,25] median=22.5 | "20-29" count=1 |
| AC-06 | [30,31,32,33,34,35] median=32.5 | "30-39" count=1 |
| AC-07 | [1,2,3,40,41,42] median=21.5 | "20-29" count=1 |
| AC-08 | [1,10,11,12,13,40] median=11.5 | "10-19" count=1 |
| AC-09 | [35,36,37,38,39,40] median=37.5 | "30-39" count=1 |
| AC-10 | [40,41,42,43,44,45] median=42.5 | "40-45" count=1 |
| AC-11 | 경계 median=9.5 | "1-9" |
| AC-12 | 경계 median=10.0 | "10-19" |
| AC-13 | 경계 median=19.5 | "10-19" |
| AC-14 | 경계 median=20.0 | "20-29" |
| AC-15 | 경계 median=39.5 | "30-39" |
| AC-16 | 경계 median=40.0 | "40-45" |
| AC-17 | 분포 키 개수 | 정확히 5개 |
| AC-18 | count 합 | == total_draws |
| AC-19 | pct 소수 2자리 | 33.33 |
| AC-20 | most_common 동률 | 키 순서상 앞선 구간 |
| AC-21 | central_median_pct | "20-29" 비율만 |
| AC-22 | avg_median 소수 2자리 | 반올림 |
| AC-23 | 4-draw 픽스처 요약 | avg=20.0, most_common="20-29", central=50.0 |
| AC-24 | 4-draw 픽스처 분포 | 1-9:1, 10-19:0, 20-29:2, 30-39:1, 40-45:0 |
| AC-25 | 캐시 동일 객체 | r1 is r2 |
| AC-26 | invalidate_cache | _median_range_cache 비움 |
| AC-27 | GET /api/stats/median_range | 200 JSON |
| AC-28 | API 빈 데이터 | 200, total_draws=0 |
| AC-29 | GET /stats/median-range | 200 HTML |
| AC-30 | 페이지 빈 데이터 | 200 |
