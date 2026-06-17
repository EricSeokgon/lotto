# Acceptance Criteria: SPEC-LOTTO-098

## AC-01: 빈 데이터 — None 입력 시 기본 구조 반환
**Given**: draws=None
**When**: get_zone_coverage_stats(None) 호출
**Then**: total_draws=0, avg_zones_covered=0.0, most_common_zones="1", full_spread_pct=0.0, concentrated_pct=0.0, zone_coverage_distribution의 6개 키 모두 count=0, pct=0.0

## AC-02: 빈 데이터 — 빈 리스트 입력 시 기본 구조 반환
**Given**: draws=[]
**When**: get_zone_coverage_stats([]) 호출
**Then**: total_draws=0, avg_zones_covered=0.0, most_common_zones="1", full_spread_pct=0.0, concentrated_pct=0.0, zone_coverage_distribution의 6개 키 모두 count=0, pct=0.0

## AC-03: 빈 데이터 — 반환값에 6개 버킷 키가 모두 포함
**Given**: draws=[]
**When**: get_zone_coverage_stats([]) 호출
**Then**: zone_coverage_distribution의 키 집합 == {"1", "2", "3", "4", "5", "6"}

## AC-04: 단일 회차 — 1구간 커버 (같은 구간에 6개)
**Given**: 본번호 [1,2,3,4,5,6] (1-5 구간 5개 + 6-10 구간 1개 → 실제 zones=2) — 오직 1구간만 커버하려면 [1,2,3,4,5,_]가 필요하나 본번호 6개 모두 구간 0이면 불가 → 대신 [1,2,3,4,5,6]은 zones=2
**Note**: 1구간 커버 케이스는 실제 로또에서 발생 불가. 모든 번호가 동일 구간(5개 슬롯 중 6개)은 구조적으로 불가. 따라서 zones_covered 최솟값은 2.
**Revised Given**: 본번호 [6,7,8,9,10,11] (구간[6-10]=5개, 구간[11-15]=1개 → zones=2)
**When**: get_zone_coverage_stats(draws) 호출
**Then**: zone_coverage_distribution["2"]["count"] == 1, zones_covered == 2

## AC-05: 단일 회차 — 2구간 커버
**Given**: 본번호 [1,2,3,6,7,8] (구간[1-5]=3개, 구간[6-10]=3개 → zones=2)
**When**: get_zone_coverage_stats(draws) 호출
**Then**: zone_coverage_distribution["2"]["count"] == 1, total_draws == 1, avg_zones_covered == 2.0

## AC-06: 단일 회차 — 3구간 커버
**Given**: 본번호 [1,2,6,7,11,12] (구간 0,1,2 → zones=3)
**When**: get_zone_coverage_stats(draws) 호출
**Then**: zone_coverage_distribution["3"]["count"] == 1, avg_zones_covered == 3.0

## AC-07: 단일 회차 — 4구간 커버
**Given**: 본번호 [1,6,11,16,20,21] (구간 0,1,2,3,3,4 → unique 4구간 → zones=4)
**When**: get_zone_coverage_stats(draws) 호출
**Then**: zone_coverage_distribution["4"]["count"] == 1, avg_zones_covered == 4.0

## AC-08: 단일 회차 — 5구간 커버
**Given**: 본번호 [1,6,11,16,21,26] (구간 0,1,2,3,4,5 → zones=5 — 단, 26은 구간[26-30]=5)
**When**: get_zone_coverage_stats(draws) 호출
**Then**: zone_coverage_distribution["5"]["count"] == 1, avg_zones_covered == 5.0

## AC-09: 단일 회차 — 6구간 커버 (완전 분산)
**Given**: 본번호 [1,6,11,16,21,26] 또는 각 구간 1개씩 포함하는 6개 번호 (zones=6)
**Note**: [1,7,13,19,25,31] = 구간 0(1-5),1(6-10),2(11-15),3(16-20),4(21-25),5(26-30) → zones=6
**When**: get_zone_coverage_stats(draws) 호출
**Then**: zone_coverage_distribution["6"]["count"] == 1, full_spread_pct == 100.0

## AC-10: 구간 산출 공식 검증 — (num-1)//5
**Given**: 번호별 구간 확인: 1→0, 5→0, 6→1, 10→1, 45→8, 41→8
**When**: 구간 인덱스 계산
**Then**: (1-1)//5==0, (5-1)//5==0, (6-1)//5==1, (10-1)//5==1, (45-1)//5==8, (41-1)//5==8

## AC-11: 구간 경계 번호 — 5와 6은 서로 다른 구간
**Given**: 본번호 [1,2,3,4,5,6] (5는 구간0, 6은 구간1 → zones=2)
**When**: get_zone_coverage_stats(draws) 호출
**Then**: zone_coverage_distribution["2"]["count"] == 1

## AC-12: 구간 경계 번호 — 10과 11은 서로 다른 구간
**Given**: 본번호 [1,2,6,7,10,11] (구간0,1,1,1,1,2 → unique={0,1,2} → zones=3)
**When**: get_zone_coverage_stats(draws) 호출
**Then**: zone_coverage_distribution["3"]["count"] == 1

## AC-13: 구간 경계 번호 — 45가 구간8에 속함
**Given**: 본번호 [1,6,11,16,21,45] (구간 0,1,2,3,4,8 → zones=6)
**When**: get_zone_coverage_stats(draws) 호출
**Then**: zone_coverage_distribution["6"]["count"] == 1

## AC-14: 다중 회차 — 집계 검증 (3회차)
**Given**: 
  - 회차1: 본번호 [1,2,3,6,7,8] → zones=2
  - 회차2: [1,6,11,16,21,26] → zones=6
  - 회차3: [1,6,11,16,20,21] → zones=4 (구간 0,1,2,3,3,4 → unique={0,1,2,3,4} → zones=5)
**Note**: 회차3 재계산: 20은 (20-1)//5=3, 21은 (21-1)//5=4 → 구간{0,1,2,3,4} → zones=5
**When**: get_zone_coverage_stats(draws) 호출
**Then**: total_draws==3, zone_coverage_distribution["2"]["count"]==1, zone_coverage_distribution["6"]["count"]==1, zone_coverage_distribution["5"]["count"]==1

## AC-15: 다중 회차 — avg_zones_covered 계산 정확성
**Given**: zones_covered 값이 각각 4, 5, 5, 5, 6인 5회차
**When**: get_zone_coverage_stats(draws) 호출
**Then**: avg_zones_covered == round((4+5+5+5+6)/5, 2) == 5.0

## AC-16: avg_zones_covered — 소수 2자리 반올림
**Given**: zones_covered 합계가 10이고 total_draws==3 → 10/3 = 3.333...
**When**: get_zone_coverage_stats(draws) 호출
**Then**: avg_zones_covered == 3.33

## AC-17: most_common_zones — 최빈 버킷 선택
**Given**: zones_covered 분포: 3→1회, 4→2회, 5→3회
**When**: get_zone_coverage_stats(draws) 호출
**Then**: most_common_zones == "5"

## AC-18: most_common_zones — 동률 시 더 작은 버킷 선택
**Given**: zones_covered 분포: 4→2회, 5→2회, 6→1회
**When**: get_zone_coverage_stats(draws) 호출
**Then**: most_common_zones == "4" (동률 시 _ZONE_COV_KEYS 정의 순서상 앞선 값)

## AC-19: full_spread_pct — zones_covered==6 비율 계산
**Given**: 5회차 중 zones_covered==6인 회차가 2회
**When**: get_zone_coverage_stats(draws) 호출
**Then**: full_spread_pct == round(2/5*100, 2) == 40.0

## AC-20: full_spread_pct — 완전 분산 없을 때 0.0
**Given**: 모든 회차의 zones_covered < 6
**When**: get_zone_coverage_stats(draws) 호출
**Then**: full_spread_pct == 0.0

## AC-21: concentrated_pct — zones_covered<=3 비율 계산
**Given**: 5회차 중 zones_covered가 2,2,3,4,5인 경우 (<=3인 회차: 3회)
**When**: get_zone_coverage_stats(draws) 호출
**Then**: concentrated_pct == round(3/5*100, 2) == 60.0

## AC-22: concentrated_pct — 집중 없을 때 0.0
**Given**: 모든 회차의 zones_covered > 3
**When**: get_zone_coverage_stats(draws) 호출
**Then**: concentrated_pct == 0.0

## AC-23: pct 계산 — 소수 2자리 반올림
**Given**: 3회차 중 zones_covered==4가 1회 → 1/3 = 33.333...%
**When**: get_zone_coverage_stats(draws) 호출
**Then**: zone_coverage_distribution["4"]["pct"] == 33.33

## AC-24: pct 합계 — 6개 버킷 pct 합계가 ~100%
**Given**: 10회차 데이터
**When**: get_zone_coverage_stats(draws) 호출
**Then**: sum(bucket["pct"] for bucket in zone_coverage_distribution.values()) ≈ 100.0 (반올림 오차 허용 ±0.1)

## AC-25: 캐시 동작 — 동일 데이터 2회 호출 시 동일 결과 반환
**Given**: 동일한 draws 리스트로 2회 호출
**When**: 두 번째 호출
**Then**: 첫 번째 호출과 동일한 결과 딕셔너리 반환

## AC-26: 캐시 동작 — invalidate_cache() 후 캐시 무효화
**Given**: get_zone_coverage_stats(draws) 호출 후 invalidate_cache() 실행
**When**: 다시 get_zone_coverage_stats(draws) 호출
**Then**: 새로 계산된 결과 반환 (캐시 키 _zone_coverage_cache가 비어있음)

## AC-27: 캐시 키 — draws 길이 기준
**Given**: len(draws)==5인 데이터 호출 후 len(draws)==10인 다른 데이터 호출
**When**: 두 번째 호출
**Then**: _zone_coverage_cache에 "5"와 "10" 두 개 키가 모두 존재

## AC-28: limit 파라미터 — 최근 N회차만 분석
**Given**: 10회차 데이터에 limit=3으로 API 호출
**When**: GET /api/stats/zone_coverage?limit=3
**Then**: total_draws == 3 (최근 3회차만 분석)

## AC-29: API 엔드포인트 — GET /api/stats/zone_coverage 200 OK
**Given**: 정상 데이터 존재 시
**When**: GET /api/stats/zone_coverage
**Then**: HTTP 200, JSON body에 total_draws, avg_zones_covered, most_common_zones, full_spread_pct, concentrated_pct, zone_coverage_distribution 포함

## AC-30: API 응답 구조 — zone_coverage_distribution 6개 키 보장
**Given**: GET /api/stats/zone_coverage 응답
**When**: zone_coverage_distribution 파싱
**Then**: 키 집합 == {"1", "2", "3", "4", "5", "6"}

## AC-31: API 응답 구조 — 각 버킷의 count와 pct 존재
**Given**: GET /api/stats/zone_coverage 응답
**When**: zone_coverage_distribution["5"] 파싱
**Then**: "count" 키와 "pct" 키 모두 존재

## AC-32: 페이지 라우트 — GET /stats/zone-coverage 200 OK
**Given**: FastAPI 테스트 클라이언트
**When**: GET /stats/zone-coverage
**Then**: HTTP 200, text/html 응답

## AC-33: 페이지 라우트 — 템플릿 파일 존재 확인
**Given**: 파일시스템
**When**: lotto/web/templates/zone_coverage.html 경로 확인
**Then**: 파일이 존재함

## AC-34: 템플릿 렌더링 — 핵심 텍스트 포함
**Given**: GET /stats/zone-coverage 응답 HTML
**When**: 응답 본문 파싱
**Then**: "구간별 번호 선택 분포" 또는 "zone_coverage" 텍스트 포함

## AC-35: 보너스 번호 제외 — bonus_number는 구간 계산에 사용하지 않음
**Given**: draw.numbers()로 본번호 6개만 반환되는 구조
**When**: get_zone_coverage_stats(draws) 호출
**Then**: 결과가 본번호 6개만으로 계산됨 (bonus_number 영향 없음)

## AC-36: zones_covered 타입 — 정수 반환
**Given**: 임의 단일 회차
**When**: 내부 zones_covered 계산
**Then**: zones_covered는 int 타입이며 1 이상 6 이하

## AC-37: zones_covered 최댓값 — 6개 번호로 최대 6구간 커버
**Given**: 각각 다른 구간에 속하는 6개 번호 [1,7,13,19,25,31]
**When**: zones_covered 계산
**Then**: zones_covered == 6

## AC-38: full_spread_pct 타입 — float 반환
**Given**: 임의 데이터
**When**: get_zone_coverage_stats(draws) 호출
**Then**: full_spread_pct는 float 타입

## AC-39: concentrated_pct 타입 — float 반환
**Given**: 임의 데이터
**When**: get_zone_coverage_stats(draws) 호출
**Then**: concentrated_pct는 float 타입

## AC-40: 전 구간 분포 — zones_covered 1~6 모두 포함하는 대규모 데이터
**Given**: 6가지 zones_covered 값이 모두 포함된 12회차 데이터 (각 2회씩)
**When**: get_zone_coverage_stats(draws) 호출
**Then**: zone_coverage_distribution의 모든 버킷이 count >= 1

## AC-41: 현실적 분포 — 실제 로또 데이터에서 zones_covered=5가 최빈값
**Given**: 실제 전체 회차 데이터 (total_draws >= 1000)
**When**: get_zone_coverage_stats(draws) 호출
**Then**: most_common_zones 값이 "4" 또는 "5" (현실적 기대치, 단 테스트는 데이터 의존)

## AC-42: avg_zones_covered 타입 — float 반환
**Given**: 임의 데이터
**When**: get_zone_coverage_stats(draws) 호출
**Then**: avg_zones_covered는 float 타입

## AC-43: 단일 회차 — pct가 100.0
**Given**: 단일 회차 데이터, zones_covered==5
**When**: get_zone_coverage_stats(draws) 호출
**Then**: zone_coverage_distribution["5"]["pct"] == 100.0

## AC-44: 구간 인덱스 범위 — 모든 번호(1~45)에서 0~8 범위
**Given**: 번호 1, 5, 6, 40, 41, 45
**When**: 구간 인덱스 (num-1)//5 계산
**Then**: 모두 0~8 범위 내 정수

## AC-45: invalidate_cache 함수 — _zone_coverage_cache 포함 여부
**Given**: get_zone_coverage_stats(draws) 로 캐시 생성 후
**When**: invalidate_cache() 호출
**Then**: _zone_coverage_cache == {}

## AC-46: 상수 _ZONE_COV_KEYS — 6개 고정 키 순서
**Given**: _ZONE_COV_KEYS 상수
**When**: 값 확인
**Then**: ["1", "2", "3", "4", "5", "6"] 순서 정확

## AC-47: most_common_zones 타입 — string 반환
**Given**: 임의 단일 회차 데이터
**When**: get_zone_coverage_stats(draws) 호출
**Then**: most_common_zones는 str 타입 ("1"~"6" 중 하나)

## AC-48: 경계값 검증 — 번호 45가 정상 처리
**Given**: 본번호 [40,41,42,43,44,45] (모두 구간[41-45]=8 → zones=1)
**Note**: 실제로는 구간 8(41-45)에 5개 슬롯만 있으므로 6개 번호 중 1개는 구간8을 벗어남 — 사실 40도 (40-1)//5=7이므로 구간7, 41-45만 구간8
**Revised**: [41,42,43,44,45,36] → 구간8(5개), 구간7(1개) → zones=2
**When**: get_zone_coverage_stats(draws) 호출
**Then**: zone_coverage_distribution["2"]["count"] == 1

## AC-49: 전 구간 균등 분포 검증
**Given**: zones_covered가 정확히 1,2,3,4,5,6 각 1회씩인 6회차 (zone=1은 구조상 불가이므로 2,2,3,4,5,6 각 1,1,1,1,1,1회 구성)
**Note**: zones_covered==1은 6개 번호가 동일 5개 슬롯 구간에 모두 들어가야 하는데 슬롯이 5개뿐이므로 실제로 불가. 테스트는 2~6 분포로 구성.
**Revised Given**: zones_covered=2,3,4,5,6 각 1회씩 (5회차)
**When**: get_zone_coverage_stats(draws) 호출
**Then**: zone_coverage_distribution["1"]["count"]==0, zone_coverage_distribution["2"]["count"]==1, zone_coverage_distribution["6"]["count"]==1

## AC-50: base.html — 사이드바 메뉴에 zone-coverage 링크 추가
**Given**: lotto/web/templates/base.html
**When**: 파일 내용 확인
**Then**: "/stats/zone-coverage" 경로를 포함하는 링크 태그 존재
