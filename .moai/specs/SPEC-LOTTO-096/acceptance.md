# Acceptance Criteria: SPEC-LOTTO-096

## AC-01: 빈 데이터 — None 입력 시 기본 구조 반환
**Given**: draws=None
**When**: get_min_gap_dist_stats(None) 호출
**Then**: total_draws=0, avg_min_gap=0.0, min1_pct=0.0, large_gap_pct=0.0, most_common_range="1", min_gap_distribution의 6개 키 모두 count=0, pct=0.0

## AC-02: 빈 데이터 — 빈 리스트 입력 시 기본 구조 반환
**Given**: draws=[]
**When**: get_min_gap_dist_stats([]) 호출
**Then**: total_draws=0, avg_min_gap=0.0, min1_pct=0.0, large_gap_pct=0.0, most_common_range="1", min_gap_distribution의 6개 키 모두 count=0, pct=0.0

## AC-03: 빈 데이터 — 반환값에 6개 버킷 키가 모두 포함
**Given**: draws=[]
**When**: get_min_gap_dist_stats([]) 호출
**Then**: min_gap_distribution의 키 집합 == {"1", "2", "3", "4-5", "6-10", "11+"}

## AC-04: 단일 회차 — min_gap=1 (연속번호 포함)
**Given**: 본번호 [1,2,10,20,30,40]을 가진 단일 회차 (1-2가 연속)
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: min_gap_distribution["1"]["count"]==1, total_draws==1, avg_min_gap==1.0

## AC-05: 단일 회차 — min_gap=2
**Given**: 본번호 [1,3,10,20,30,40]을 가진 단일 회차 (gaps: 2,7,10,10,10)
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: min_gap_distribution["2"]["count"]==1, avg_min_gap==2.0

## AC-06: 단일 회차 — min_gap=3
**Given**: 본번호 [1,4,10,20,30,40]을 가진 단일 회차 (gaps: 3,6,10,10,10)
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: min_gap_distribution["3"]["count"]==1, avg_min_gap==3.0

## AC-07: 단일 회차 — min_gap=4 (버킷 "4-5")
**Given**: 본번호 [1,5,10,20,30,40]을 가진 단일 회차 (gaps: 4,5,10,10,10)
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: min_gap_distribution["4-5"]["count"]==1, avg_min_gap==4.0

## AC-08: 단일 회차 — min_gap=5 (버킷 "4-5")
**Given**: 본번호 [1,6,12,20,30,40]을 가진 단일 회차 (gaps: 5,6,8,10,10)
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: min_gap_distribution["4-5"]["count"]==1, avg_min_gap==5.0

## AC-09: 단일 회차 — min_gap=6 (버킷 "6-10")
**Given**: 본번호 [1,7,14,22,31,40]을 가진 단일 회차 (gaps: 6,7,8,9,9)
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: min_gap_distribution["6-10"]["count"]==1, avg_min_gap==6.0

## AC-10: 단일 회차 — min_gap=10 (버킷 "6-10")
**Given**: 본번호 [1,11,21,31,41,45] 을 가진 단일 회차 (gaps: 10,10,10,10,4)
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: min_gap_distribution["4-5"]["count"]==1 (min=4), avg_min_gap==4.0

## AC-11: 단일 회차 — min_gap=11 (버킷 "11+")
**Given**: 본번호 [1,13,25,31,37,43]을 가진 단일 회차 (gaps: 12,12,6,6,6)
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: min_gap_distribution["6-10"]["count"]==1 (min=6)

## AC-12: 단일 회차 — min_gap이 11 이상인 경우 "11+" 버킷에 분류
**Given**: 본번호 [1,14,27,33,39,45]을 가진 단일 회차 (gaps: 13,13,6,6,6)
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: min_gap_distribution["6-10"]["count"]==1 (실제 min=6)

## AC-13: 단일 회차 — 순수 min_gap>=11인 경우 "11+" 버킷 분류
**Given**: 본번호 [1,15,29,33,39,45]를 가진 단일 회차 (gaps: 14,14,4,6,6) — min=4
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: min_gap_distribution["4-5"]["count"]==1

## AC-14: "11+" 버킷 분류 — min_gap=11
**Given**: 번호 [1,12,23,34,45,45]와 같이 min_gap이 11인 가상 회차 (min_gap=11)
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: 해당 회차는 min_gap_distribution["11+"] 버킷에 분류

## AC-15: 복수 회차 — total_draws 정확성
**Given**: 5개 회차 리스트
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: total_draws==5

## AC-16: 복수 회차 — avg_min_gap 정확성
**Given**: min_gap가 각각 1,2,3,4,5인 5개 회차
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: avg_min_gap==3.0

## AC-17: 복수 회차 — avg_min_gap 소수 2자리
**Given**: min_gap이 [1,2,2]인 3개 회차 (합계=5)
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: avg_min_gap==1.67 (round(5/3, 2))

## AC-18: 복수 회차 — pct 계산 정확성
**Given**: 10개 회차 중 3개가 min_gap==1
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: min_gap_distribution["1"]["pct"]==30.0

## AC-19: 복수 회차 — pct 소수 2자리 반올림
**Given**: 3개 회차 중 1개가 min_gap==1 (pct=33.333...)
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: min_gap_distribution["1"]["pct"]==33.33

## AC-20: min1_pct — min_gap=1 회차 비율 정확성
**Given**: 10개 회차 중 4개가 min_gap==1
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: min1_pct==40.0

## AC-21: min1_pct — 빈 데이터 시 0.0
**Given**: draws=[]
**When**: get_min_gap_dist_stats([]) 호출
**Then**: min1_pct==0.0

## AC-22: large_gap_pct — min_gap>=6 회차 비율 정확성
**Given**: 10개 회차 중 2개가 min_gap==6, 1개가 min_gap==8
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: large_gap_pct==30.0

## AC-23: large_gap_pct — 빈 데이터 시 0.0
**Given**: draws=[]
**When**: get_min_gap_dist_stats([]) 호출
**Then**: large_gap_pct==0.0

## AC-24: most_common_range — 최빈 버킷 반환
**Given**: 10개 회차 중 "2" 버킷이 5개로 최다
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: most_common_range=="2"

## AC-25: most_common_range — 동률 시 버킷 정의 순서 앞선 키 선택
**Given**: "1" 버킷 3개, "2" 버킷 3개로 동률
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: most_common_range=="1" (정의 순서상 앞선 키)

## AC-26: 캐시 히트 — 동일 len(draws) 호출 시 동일 객체 반환
**Given**: 동일한 길이의 draws를 두 번 호출
**When**: 첫 번째와 두 번째 호출 결과를 비교
**Then**: 두 결과 딕셔너리의 내용이 동일

## AC-27: 캐시 무효화 — invalidate_cache() 호출 후 캐시 초기화
**Given**: get_min_gap_dist_stats(draws)를 한 번 호출하여 캐시 적재
**When**: invalidate_cache() 호출 후 동일 draws로 재호출
**Then**: 재계산이 수행되어 동일한 결과 반환 (캐시가 비워진 후 재채워짐 검증)

## AC-28: API 엔드포인트 — GET /api/stats/min_gap_dist 200 반환
**Given**: 서버가 정상 가동 중
**When**: GET /api/stats/min_gap_dist 요청
**Then**: HTTP 200, Content-Type: application/json, 응답 바디에 total_draws, avg_min_gap, most_common_range, min1_pct, large_gap_pct, min_gap_distribution 키 포함

## AC-29: API 엔드포인트 — 응답 구조 버킷 키 검증
**Given**: 서버가 정상 가동 중
**When**: GET /api/stats/min_gap_dist 요청
**Then**: min_gap_distribution 키 집합 == {"1", "2", "3", "4-5", "6-10", "11+"}

## AC-30: API 엔드포인트 — 각 버킷 값 구조 검증
**Given**: 서버가 정상 가동 중
**When**: GET /api/stats/min_gap_dist 요청
**Then**: min_gap_distribution의 각 버킷 값에 "count"(int)와 "pct"(float) 키가 존재

## AC-31: 페이지 엔드포인트 — GET /stats/min_gap_dist 200 반환
**Given**: 서버가 정상 가동 중
**When**: GET /stats/min_gap_dist 요청
**Then**: HTTP 200, Content-Type: text/html

## AC-32: 페이지 엔드포인트 — 한국어 제목 포함
**Given**: 서버가 정상 가동 중
**When**: GET /stats/min_gap_dist 요청
**Then**: 응답 HTML에 "최소 간격" 또는 "min_gap" 관련 텍스트 포함

## AC-33: 보너스 번호 제외 — min_gap 계산에 보너스 미포함
**Given**: 본번호 [1,2,10,20,30,40], 보너스=3인 단일 회차
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: min_gap==1 (보너스 3을 포함하면 min이 1이 아닌 1로 동일하지만, 보너스 제외 로직이 명시적으로 검증됨)

## AC-34: 보너스 번호 제외 — 보너스가 작은 간격을 만드는 경우 무시
**Given**: 본번호 [5,10,20,30,40,45], 보너스=11인 회차 (본번호만의 min_gap=5)
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: min_gap==5, min_gap_distribution["4-5"]["count"]==1 (보너스 11과 10의 차이 1이 반영되지 않음)

## AC-35: 전체 회차 분포 — pct 합계가 100에 근접
**Given**: 실제 로또 전체 회차 데이터
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: sum(v["pct"] for v in min_gap_distribution.values()) 가 99.9~100.1 범위 내

## AC-36: 정수 타입 — count는 int 타입
**Given**: 1개 이상의 회차 데이터
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: min_gap_distribution의 각 버킷 count 값이 int 타입

## AC-37: 부동소수점 타입 — pct는 float 타입
**Given**: 1개 이상의 회차 데이터
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: min_gap_distribution의 각 버킷 pct 값이 float 타입

## AC-38: 반환값 — total_draws는 draws 길이와 일치
**Given**: 50개 회차 리스트
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: total_draws==50

## AC-39: 경계값 — min_gap=5 → "4-5" 버킷 분류
**Given**: min_gap=5인 회차
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: min_gap_distribution["4-5"]["count"]==1

## AC-40: 경계값 — min_gap=6 → "6-10" 버킷 분류
**Given**: min_gap=6인 회차
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: min_gap_distribution["6-10"]["count"]==1

## AC-41: 경계값 — min_gap=10 → "6-10" 버킷 분류
**Given**: min_gap=10인 회차
**When**: get_min_gap_dist_stats(draws) 호출
**Then**: min_gap_distribution["6-10"]["count"]==1
