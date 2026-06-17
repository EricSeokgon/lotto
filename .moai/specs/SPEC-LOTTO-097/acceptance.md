# Acceptance Criteria: SPEC-LOTTO-097

## AC-01: 빈 데이터 — None 입력 시 기본 구조 반환
**Given**: draws=None
**When**: get_gap_median_dist_stats(None) 호출
**Then**: total_draws=0, avg_gap_median=0.0, most_common_range="1-2", low_median_pct=0.0, high_median_pct=0.0, gap_median_distribution의 6개 키 모두 count=0, pct=0.0

## AC-02: 빈 데이터 — 빈 리스트 입력 시 기본 구조 반환
**Given**: draws=[]
**When**: get_gap_median_dist_stats([]) 호출
**Then**: total_draws=0, avg_gap_median=0.0, most_common_range="1-2", low_median_pct=0.0, high_median_pct=0.0, gap_median_distribution의 6개 키 모두 count=0, pct=0.0

## AC-03: 빈 데이터 — 반환값에 6개 버킷 키가 모두 포함
**Given**: draws=[]
**When**: get_gap_median_dist_stats([]) 호출
**Then**: gap_median_distribution의 키 집합 == {"1-2", "3-4", "5-6", "7-8", "9-10", "11+"}

## AC-04: 단일 회차 — gap_median=1 (연속번호 포함)
**Given**: 본번호 [1,2,3,4,5,6] (gaps=[1,1,1,1,1], sorted=[1,1,1,1,1], median=gaps[2]=1)
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: gap_median_distribution["1-2"]["count"]==1, avg_gap_median==1.0

## AC-05: 단일 회차 — gap_median=2
**Given**: 본번호 [1,3,5,7,9,11] (gaps=[2,2,2,2,2], median=2)
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: gap_median_distribution["1-2"]["count"]==1, avg_gap_median==2.0

## AC-06: 단일 회차 — gap_median=3
**Given**: 본번호 [1,4,7,10,13,16] (gaps=[3,3,3,3,3], median=3)
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: gap_median_distribution["3-4"]["count"]==1, avg_gap_median==3.0

## AC-07: 단일 회차 — gap_median=4
**Given**: 본번호 [1,5,9,13,17,21] (gaps=[4,4,4,4,4], median=4)
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: gap_median_distribution["3-4"]["count"]==1, avg_gap_median==4.0

## AC-08: 단일 회차 — gap_median=5
**Given**: 본번호 [1,6,11,16,21,26] (gaps=[5,5,5,5,5], median=5)
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: gap_median_distribution["5-6"]["count"]==1, avg_gap_median==5.0

## AC-09: 단일 회차 — gap_median=6
**Given**: 본번호 [1,7,13,19,25,31] (gaps=[6,6,6,6,6], median=6)
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: gap_median_distribution["5-6"]["count"]==1, avg_gap_median==6.0

## AC-10: 단일 회차 — gap_median=7
**Given**: 본번호 [1,8,15,22,29,36] (gaps=[7,7,7,7,7], median=7)
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: gap_median_distribution["7-8"]["count"]==1, avg_gap_median==7.0

## AC-11: 단일 회차 — gap_median=8
**Given**: 본번호 [1,9,17,25,33,41] (gaps=[8,8,8,8,8], median=8)
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: gap_median_distribution["7-8"]["count"]==1, avg_gap_median==8.0

## AC-12: 단일 회차 — gap_median=9
**Given**: 본번호 [1,10,19,28,37,44] (gaps=[9,9,9,9,7], sorted=[7,9,9,9,9], median=9)
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: gap_median_distribution["9-10"]["count"]==1, avg_gap_median==9.0

## AC-13: 단일 회차 — gap_median=10
**Given**: 본번호 [1,11,21,31,41,43] (gaps=[10,10,10,10,2], sorted=[2,10,10,10,10], median=10)
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: gap_median_distribution["9-10"]["count"]==1, avg_gap_median==10.0

## AC-14: 단일 회차 — gap_median=11 (11+ 버킷)
**Given**: 본번호 [1,12,23,34,40,42] (gaps=[11,11,11,6,2], sorted=[2,6,11,11,11], median=11)
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: gap_median_distribution["11+"]["count"]==1, avg_gap_median==11.0

## AC-15: 단일 회차 — gap_median=15 (11+ 버킷)
**Given**: 본번호 [1,3,5,21,36,45] (gaps=[2,2,16,15,9], sorted=[2,2,9,15,16], median=9)
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: gap_median_distribution["9-10"]["count"]==1

## AC-16: 중앙값 계산 — 불균등 간격에서 중앙값은 정렬 후 3번째
**Given**: 본번호 [1,2,10,20,30,40] (gaps=[1,8,10,10,10], sorted=[1,8,10,10,10], median=10)
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: gap_median_distribution["9-10"]["count"]==1, avg_gap_median==10.0

## AC-17: 중앙값 계산 — 짝수 간격 수가 아닌 홀수 간격 수(5개)의 중간값
**Given**: 본번호 [5,10,15,20,25,30] (gaps=[5,5,5,5,5], median=5)
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: avg_gap_median==5.0, gap_median_distribution["5-6"]["count"]==1

## AC-18: 보너스 번호 제외 확인
**Given**: DrawResult with numbers=[1,7,13,19,25,31], bonus=45 (bonus 무시)
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: 계산에 45가 포함되지 않으며 gaps=[6,6,6,6,6], avg_gap_median==6.0

## AC-19: 다중 회차 — total_draws 정확성
**Given**: 3개 회차 데이터
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: total_draws==3

## AC-20: 다중 회차 — avg_gap_median 정확성 (소수 2자리)
**Given**: gap_median 값이 [4, 6, 8]인 3개 회차
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: avg_gap_median == round((4+6+8)/3, 2) == 6.0

## AC-21: 다중 회차 — count 합산이 total_draws와 일치
**Given**: N개 회차 데이터
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: sum(v["count"] for v in gap_median_distribution.values()) == total_draws

## AC-22: 다중 회차 — pct 합산이 100.0에 근사 (부동소수점 오차 허용)
**Given**: 5개 회차 데이터
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: sum(v["pct"] for v in gap_median_distribution.values()) 가 100.0에서 0.1 이내

## AC-23: most_common_range — 단일 최빈 구간 선택
**Given**: "5-6" 구간이 다른 구간보다 많은 회차 데이터
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: most_common_range == "5-6"

## AC-24: most_common_range — 동률 시 앞선 구간 선택
**Given**: "3-4"와 "5-6"이 같은 count를 가진 회차 데이터
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: most_common_range == "3-4" (정의 순서상 앞선 구간)

## AC-25: low_median_pct — gap_median <= 4 비율 정확성
**Given**: 5개 회차 중 2개가 gap_median <= 4
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: low_median_pct == 40.0

## AC-26: high_median_pct — gap_median >= 9 비율 정확성
**Given**: 4개 회차 중 1개가 gap_median >= 9
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: high_median_pct == 25.0

## AC-27: low_median_pct와 high_median_pct가 모두 0인 경우
**Given**: 모든 회차의 gap_median이 5~8 범위인 데이터
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: low_median_pct==0.0, high_median_pct==0.0

## AC-28: 캐시 적중 — 같은 draws 길이로 두 번 호출 시 동일 결과 반환
**Given**: N개 회차 데이터
**When**: get_gap_median_dist_stats(draws)를 두 번 호출
**Then**: 두 번째 호출이 첫 번째와 동일한 dict를 반환 (is 비교)

## AC-29: 캐시 무효화 — invalidate_cache() 호출 후 재계산
**Given**: 캐시가 채워진 상태
**When**: invalidate_cache() 호출 후 get_gap_median_dist_stats(draws) 재호출
**Then**: 캐시 miss가 발생하고 신규 계산 결과 반환

## AC-30: pct 소수 2자리 반올림
**Given**: 3개 회차 중 1개가 "1-2" 버킷 (1/3 = 33.333...%)
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: gap_median_distribution["1-2"]["pct"] == 33.33

## AC-31: avg_gap_median 소수 2자리 반올림
**Given**: gap_median 값이 [1, 2, 3]인 3개 회차
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: avg_gap_median == 2.0

## AC-32: API 엔드포인트 — GET /api/stats/gap_median_dist 응답 구조
**Given**: FastAPI 앱 실행 중
**When**: GET /api/stats/gap_median_dist 요청
**Then**: HTTP 200, JSON body에 total_draws, avg_gap_median, most_common_range, low_median_pct, high_median_pct, gap_median_distribution 키 포함

## AC-33: API 엔드포인트 — limit 파라미터 적용
**Given**: 총 100개 회차 데이터가 있는 상태
**When**: GET /api/stats/gap_median_dist?limit=50 요청
**Then**: total_draws==50, 최근 50개 회차만 분석

## AC-34: 페이지 엔드포인트 — GET /stats/gap-median-dist 응답
**Given**: FastAPI 앱 실행 중
**When**: GET /stats/gap-median-dist 요청
**Then**: HTTP 200, gap_median_dist.html 템플릿 렌더링, Content-Type이 text/html

## AC-35: 템플릿 — 6개 구간 레이블 및 분포 표시
**Given**: gap_median_dist.html 템플릿
**When**: 페이지 렌더링
**Then**: "1-2", "3-4", "5-6", "7-8", "9-10", "11+" 레이블이 모두 표시되고, 한국어 제목("번호 간격 중앙값 구간 분포") 포함

## AC-36: 버킷 경계 — gap_median=2 가 "1-2" 버킷에 분류
**Given**: gaps=[1,2,3,4,5]에서 median=3이 아닌, gaps=[1,1,2,2,3]에서 sorted=[1,1,2,2,3], median=2
**When**: _gap_median_bucket(2) 호출
**Then**: "1-2" 반환

## AC-37: 버킷 경계 — gap_median=3 가 "3-4" 버킷에 분류
**When**: _gap_median_bucket(3) 호출
**Then**: "3-4" 반환

## AC-38: 버킷 경계 — gap_median=4 가 "3-4" 버킷에 분류
**When**: _gap_median_bucket(4) 호출
**Then**: "3-4" 반환

## AC-39: 버킷 경계 — gap_median=5 가 "5-6" 버킷에 분류
**When**: _gap_median_bucket(5) 호출
**Then**: "5-6" 반환

## AC-40: 버킷 경계 — gap_median=6 가 "5-6" 버킷에 분류
**When**: _gap_median_bucket(6) 호출
**Then**: "5-6" 반환

## AC-41: 버킷 경계 — gap_median=7 가 "7-8" 버킷에 분류
**When**: _gap_median_bucket(7) 호출
**Then**: "7-8" 반환

## AC-42: 버킷 경계 — gap_median=8 가 "7-8" 버킷에 분류
**When**: _gap_median_bucket(8) 호출
**Then**: "7-8" 반환

## AC-43: 버킷 경계 — gap_median=9 가 "9-10" 버킷에 분류
**When**: _gap_median_bucket(9) 호출
**Then**: "9-10" 반환

## AC-44: 버킷 경계 — gap_median=10 가 "9-10" 버킷에 분류
**When**: _gap_median_bucket(10) 호출
**Then**: "9-10" 반환

## AC-45: 버킷 경계 — gap_median=11 가 "11+" 버킷에 분류
**When**: _gap_median_bucket(11) 호출
**Then**: "11+" 반환

## AC-46: 버킷 경계 — gap_median=20 가 "11+" 버킷에 분류
**When**: _gap_median_bucket(20) 호출
**Then**: "11+" 반환

## AC-47: base.html — 사이드바에 간격 중앙값 구간 분포 링크 추가
**Given**: base.html 템플릿
**When**: 사이드바 렌더링
**Then**: /stats/gap-median-dist 링크와 "간격 중앙값 구간 분포" 텍스트 포함

## AC-48: 단일 회차 — 극단적 분산 간격에서 중앙값 정확성
**Given**: 본번호 [1,2,3,4,5,45] (gaps=[1,1,1,1,40], sorted=[1,1,1,1,40], median=1)
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: gap_median_distribution["1-2"]["count"]==1, avg_gap_median==1.0

## AC-49: 다중 회차 — 모든 구간에 적어도 1개씩 분포
**Given**: 6개 회차 데이터로 각 구간에 정확히 1개씩 해당하는 데이터
**When**: get_gap_median_dist_stats(draws) 호출
**Then**: 6개 버킷 모두 count==1, total_draws==6
