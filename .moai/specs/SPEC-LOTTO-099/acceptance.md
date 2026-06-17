# SPEC-LOTTO-099 Acceptance Criteria

## 데이터 함수 - get_quartile_dist_stats()

### AC-001: 빈 입력 처리 (None)
- Given: draws=None
- When: get_quartile_dist_stats(None) 호출
- Then: total_draws=0, avg_q1=0.0, avg_q2=0.0, avg_q3=0.0, avg_q4=0.0 반환

### AC-002: 빈 입력 처리 (빈 리스트)
- Given: draws=[]
- When: get_quartile_dist_stats([]) 호출
- Then: total_draws=0, balanced_pct=0.0, skewed_pct=0.0 반환

### AC-003: 빈 입력 시 most_common_combination
- Given: draws=[]
- When: get_quartile_dist_stats([]) 호출
- Then: most_common_combination="0-0-0-0" 반환

### AC-004: 빈 입력 시 quartile_distribution
- Given: draws=[]
- When: get_quartile_dist_stats([]) 호출
- Then: quartile_distribution={} (빈 딕셔너리) 반환

### AC-005: 단일 회차 - 사분위 카운트 합산
- Given: 번호 [1, 12, 23, 34, 2, 13] (Q1=2, Q2=2, Q3=1, Q4=1)
- When: get_quartile_dist_stats([단일회차]) 호출
- Then: quartile_distribution에 "2-2-1-1" 키가 {"count":1, "pct":100.0}으로 존재

### AC-006: 단일 회차 - most_common_combination
- Given: 번호 [1, 12, 23, 34, 2, 13] (Q1=2, Q2=2, Q3=1, Q4=1)
- When: get_quartile_dist_stats([단일회차]) 호출
- Then: most_common_combination="2-2-1-1"

### AC-007: Q1 구간 경계값 - 1번
- Given: 번호 [1, 2, 3, 4, 5, 6] (모두 Q1)
- When: get_quartile_dist_stats([해당회차]) 호출
- Then: quartile_distribution["6-0-0-0"]["count"] == 1

### AC-008: Q1 구간 경계값 - 11번
- Given: 번호 [11, 12, 23, 34, 5, 6] (Q1=3, Q2=1, Q3=1, Q4=1)
- When: get_quartile_dist_stats([해당회차]) 호출
- Then: 결과 조합 키에 "3-1-1-1"이 존재

### AC-009: Q2 구간 경계값 - 12번
- Given: 번호 [12, 13, 23, 34, 1, 2] (Q1=2, Q2=2, Q3=1, Q4=1)
- When: get_quartile_dist_stats([해당회차]) 호출
- Then: 결과 조합 키에 "2-2-1-1"이 존재

### AC-010: Q2 구간 경계값 - 22번
- Given: 번호 [22, 23, 34, 1, 2, 3] (Q1=3, Q2=1, Q3=1, Q4=1)
- When: get_quartile_dist_stats([해당회차]) 호출
- Then: 결과 조합 키에 "3-1-1-1"이 존재

### AC-011: Q3 구간 경계값 - 23번
- Given: 번호 [23, 24, 34, 1, 2, 3] (Q1=3, Q2=0, Q3=2, Q4=1)
- When: get_quartile_dist_stats([해당회차]) 호출
- Then: 결과 조합 키에 "3-0-2-1"이 존재

### AC-012: Q3 구간 경계값 - 33번
- Given: 번호 [33, 34, 1, 2, 3, 4] (Q1=4, Q2=0, Q3=1, Q4=1)
- When: get_quartile_dist_stats([해당회차]) 호출
- Then: 결과 조합 키에 "4-0-1-1"이 존재

### AC-013: Q4 구간 경계값 - 34번
- Given: 번호 [34, 35, 1, 2, 3, 4] (Q1=4, Q2=0, Q3=0, Q4=2)
- When: get_quartile_dist_stats([해당회차]) 호출
- Then: 결과 조합 키에 "4-0-0-2"이 존재

### AC-014: Q4 구간 경계값 - 45번
- Given: 번호 [45, 44, 43, 42, 41, 40] (모두 Q4)
- When: get_quartile_dist_stats([해당회차]) 호출
- Then: quartile_distribution["0-0-0-6"]["count"] == 1

### AC-015: q1+q2+q3+q4 합산 검증
- Given: 임의의 유효 회차 리스트
- When: get_quartile_dist_stats(draws) 호출
- Then: 모든 조합 키 "{q1}-{q2}-{q3}-{q4}"에서 q1+q2+q3+q4 == 6

### AC-016: total_draws 정확성
- Given: 10개 회차 리스트
- When: get_quartile_dist_stats(draws) 호출
- Then: total_draws == 10

### AC-017: 백분율 합산 검증
- Given: 임의의 유효 회차 리스트
- When: get_quartile_dist_stats(draws) 호출
- Then: quartile_distribution의 모든 pct 합이 100.0 (±0.1 허용)

### AC-018: avg_q1 계산 정확성
- Given: 3회차: [1,12,23,34,2,13] / [3,14,25,36,4,15] / [5,16,27,38,1,2] (Q1: 2+2+4=8)
- When: get_quartile_dist_stats(draws) 호출
- Then: avg_q1 == round(8/3, 2)

### AC-019: avg_q2 계산 정확성
- Given: 3회차: [1,12,23,34,2,13] / [3,14,25,36,4,15] / [5,16,27,38,1,2] (Q2: 2+2+2=6)
- When: get_quartile_dist_stats(draws) 호출
- Then: avg_q2 == round(6/3, 2)

### AC-020: 균형 분포(balanced_pct) 계산
- Given: 회차1: [1,12,23,34,2,13] (Q1=2,Q2=2,Q3=1,Q4=1) balanced=True
         회차2: [1,2,3,4,5,6] (Q1=6,...) balanced=False
- When: get_quartile_dist_stats(2회차) 호출
- Then: balanced_pct == 50.0

### AC-021: 균형 분포 경계 - 정확히 (1,1,2,2) 포함
- Given: 번호 [1, 12, 23, 24, 34, 35] (Q1=1, Q2=1, Q3=2, Q4=2)
- When: get_quartile_dist_stats([해당회차]) 호출
- Then: balanced_pct == 100.0 (균형으로 분류됨)

### AC-022: 균형 분포 경계 - (3,1,1,1) 불포함
- Given: 번호 [1, 2, 3, 12, 23, 34] (Q1=3, Q2=1, Q3=1, Q4=1)
- When: get_quartile_dist_stats([해당회차]) 호출
- Then: balanced_pct == 0.0 (균형 아님, Q1=3 > 2)

### AC-023: 쏠림 분포(skewed_pct) 계산
- Given: 회차1: [1,2,3,4,12,23] (Q1=4,...) skewed=True
         회차2: [1,12,23,34,2,13] skewed=False
- When: get_quartile_dist_stats(2회차) 호출
- Then: skewed_pct == 50.0

### AC-024: 쏠림 분포 경계 - Q2에 4개
- Given: 번호 [12,13,14,15,1,23] (Q2=4)
- When: get_quartile_dist_stats([해당회차]) 호출
- Then: skewed_pct == 100.0

### AC-025: 쏠림 분포 경계 - 어떤 구간에도 3개 이하면 미분류
- Given: 번호 [1,2,3,12,23,34] (Q1=3, 4 미만)
- When: get_quartile_dist_stats([해당회차]) 호출
- Then: skewed_pct == 0.0

### AC-026: most_common_combination 동률 처리
- Given: 회차1: 조합 "2-1-2-1", 회차2: 조합 "1-2-2-1" (각 1회)
- When: get_quartile_dist_stats(2회차) 호출
- Then: most_common_combination == "1-2-2-1" (사전순 "1-2-2-1" < "2-1-2-1")

### AC-027: 캐시 히트 - 동일 draws 수 재호출
- Given: 10개 회차로 첫 호출 후
- When: 동일한 10개 회차로 재호출
- Then: 캐시에서 동일 객체 반환 (is 비교 또는 동일 값)

### AC-028: 캐시 무효화 - invalidate_cache() 호출 후
- Given: 10개 회차로 첫 호출 후 invalidate_cache() 호출
- When: 동일한 10개 회차로 재호출
- Then: 새로 계산된 결과 반환 (캐시 미스)

### AC-029: 보너스 번호 제외 확인
- Given: DrawResult에서 numbers() 메서드가 본번호 6개만 반환하는 구조 확인
- When: get_quartile_dist_stats(draws) 호출
- Then: 보너스 번호가 구간 카운트에 포함되지 않음 (q1+q2+q3+q4==6 유지)

### AC-030: 관측되지 않은 조합 미포함
- Given: 단일 회차 [1,12,23,34,2,13] (조합 "2-2-1-1"만 존재)
- When: get_quartile_dist_stats([단일회차]) 호출
- Then: quartile_distribution에 "2-2-1-1"만 존재하고 다른 키 없음

## API 엔드포인트

### AC-031: GET /api/stats/quartile_dist - 정상 응답
- Given: 서버 실행 중, 회차 데이터 존재
- When: GET /api/stats/quartile_dist 요청
- Then: HTTP 200, JSON 응답에 total_draws, avg_q1, avg_q2, avg_q3, avg_q4, most_common_combination, balanced_pct, skewed_pct, quartile_distribution 키 포함

### AC-032: GET /api/stats/quartile_dist?limit=100 - limit 파라미터 적용
- Given: 전체 회차 수가 100 초과인 상태
- When: GET /api/stats/quartile_dist?limit=100 요청
- Then: total_draws == 100

### AC-033: GET /api/stats/quartile_dist?limit=0 - 전체 데이터 사용
- Given: 전체 회차 수 N
- When: GET /api/stats/quartile_dist?limit=0 요청
- Then: total_draws == N

### AC-034: API 응답 quartile_distribution 타입 검증
- Given: 서버 실행 중
- When: GET /api/stats/quartile_dist 요청
- Then: quartile_distribution 내 각 값은 count(int)와 pct(float) 포함

## 웹 페이지

### AC-035: GET /stats/quartile-dist - 페이지 정상 렌더링
- Given: 서버 실행 중
- When: GET /stats/quartile-dist 요청
- Then: HTTP 200, quartile_dist.html 템플릿 렌더링, "사분위 분포" 제목 포함

### AC-036: 사이드바 내비게이션 - "사분위 분포" 링크 존재
- Given: 임의 통계 페이지 접근
- When: base.html 사이드바 렌더링
- Then: "/stats/quartile-dist" 링크가 "사분위 분포" 텍스트로 존재

### AC-037: 템플릿 - 핵심 통계 표시
- Given: quartile_dist.html 템플릿
- When: 데이터와 함께 렌더링
- Then: avg_q1, avg_q2, avg_q3, avg_q4, balanced_pct, skewed_pct 값이 페이지에 표시됨

### AC-038: 템플릿 - most_common_combination 표시
- Given: quartile_dist.html 템플릿
- When: 데이터와 함께 렌더링
- Then: most_common_combination 값이 페이지에 표시됨

### AC-039: 템플릿 - 한국어 UI 라벨
- Given: quartile_dist.html 템플릿
- When: 렌더링
- Then: "Q1 구간", "Q2 구간", "Q3 구간", "Q4 구간", "균형 분포", "쏠림 분포" 등 한국어 라벨 포함

## 회귀 방지

### AC-040: 기존 통계 함수 미변경 확인
- Given: 기존 2618개 테스트
- When: SPEC-099 구현 후 전체 테스트 실행
- Then: 기존 테스트 모두 통과 (회귀 없음)

### AC-041: invalidate_cache() - quartile_dist 캐시 초기화 포함
- Given: _quartile_dist_cache에 데이터 존재
- When: invalidate_cache() 호출
- Then: _quartile_dist_cache가 비어 있음

### AC-042: avg_q3, avg_q4 소수점 2자리
- Given: 다수 회차 데이터
- When: get_quartile_dist_stats(draws) 호출
- Then: avg_q3, avg_q4 각각 소수점 2자리로 반올림된 float 값

### AC-043: balanced_pct, skewed_pct 소수점 2자리
- Given: 다수 회차 데이터
- When: get_quartile_dist_stats(draws) 호출
- Then: balanced_pct, skewed_pct 각각 소수점 2자리로 반올림된 float 값

### AC-044: quartile_distribution pct 소수점 2자리
- Given: 다수 회차 데이터
- When: get_quartile_dist_stats(draws) 호출
- Then: quartile_distribution 내 모든 pct 값이 소수점 2자리로 반올림됨

### AC-045: Python 3.9 호환성 - match/case 미사용
- Given: SPEC-099 구현 코드
- When: Python 3.9 환경에서 import
- Then: SyntaxError 없이 정상 import
