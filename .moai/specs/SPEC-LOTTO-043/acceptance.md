# SPEC-LOTTO-043 인수 기준 (Given-When-Then)

## 데이터 함수 (consecutive_pattern)

### AC-1: 길이 3 런 집계
- Given 한 회차의 본번호가 `[3,4,5,18,33,40]`인 데이터
- When `consecutive_pattern(draws)`를 호출하면
- Then `run_length_distribution["3"] == 1`이고
  `most_common_pairs`에 `3-4`, `4-5`가 각각 count 1로 집계된다.

### AC-2: 길이 2 런 2개
- Given 본번호 `[7,8,19,20,41,45]`인 회차
- When 분석하면
- Then `run_length_distribution["2"] == 2` (7-8, 19-20 두 개의 길이 2 런).

### AC-3: 연속 미포함 회차
- Given 본번호 `[2,5,9,14,30,44]` (인접 차이 모두 ≥2)인 회차
- When 분석하면
- Then 이 회차는 `draws_without_consecutive`에 집계되고
  `draws_with_consecutive`에는 집계되지 않는다.

### AC-4: 연속 비율 계산
- Given 4회차 중 3회차가 연속 런을 포함
- When 분석하면
- Then `consecutive_ratio == round(3/4, 4) == 0.75`.

### AC-5: 최장 런
- Given 본번호가 `[1,2,3,4,5,6]`인 회차
- When 분석하면
- Then `max_run_length == 6`, `run_length_distribution["6"] == 1`.

### AC-6: 연속 쌍 정렬
- Given 여러 회차에서 다양한 연속 쌍이 등장
- When 분석하면
- Then `most_common_pairs`는 count 내림차순, 동률은 pair 라벨 오름차순,
  최대 10개로 정렬되어 반환된다.

### AC-7: 빈 리스트
- Given `draws=[]`
- When 분석하면
- Then 예외 없이 빈 구조(`total_draws=0`, 모든 분포 0, `consecutive_ratio=0.0`,
  `max_run_length=0`, `most_common_pairs=[]`)를 반환한다.

### AC-8: None draws
- Given `draws=None`(명시)
- When 분석하면
- Then AC-7과 동일한 빈 구조를 반환한다.

### AC-9: recent_n 클램프
- Given recent_n이 전체 회차 수보다 큰 값
- When 분석하면
- Then `total_draws`는 가용 전체 회차 수가 된다(예외 없음).

## API (GET /api/patterns/consecutive)

### AC-10: 정상 응답
- Given get_draws가 데이터를 반환
- When `GET /api/patterns/consecutive`를 호출하면
- Then 200과 7개 최상위 키를 모두 포함한 JSON을 반환한다.

### AC-11: recent_n 윈도
- Given 다수의 회차 데이터
- When `GET /api/patterns/consecutive?recent_n=50`을 호출하면
- Then 200, 최신 50회차(또는 가용 전체) 기준 결과를 반환한다.

### AC-12: recent_n=0 → 422
- When `GET /api/patterns/consecutive?recent_n=0`을 호출하면
- Then FastAPI 검증으로 422를 반환한다 (ge=1 위반).

### AC-13: 데이터 부재 → 200 빈 구조
- Given get_draws가 None
- When `GET /api/patterns/consecutive`를 호출하면
- Then 200과 빈 구조를 반환한다.

## 페이지 (GET /patterns/consecutive)

### AC-14: 정상 렌더링
- When `GET /patterns/consecutive`를 호출하면
- Then 200 HTML을 반환한다.

### AC-15: recent_n 파라미터
- When `GET /patterns/consecutive?recent_n=100`을 호출하면
- Then 200 HTML을 반환한다.

### AC-16: 데이터 부재에도 200
- Given get_draws가 None
- When `GET /patterns/consecutive`를 호출하면
- Then 200 (빈 상태 메시지, 크래시 없음).

### AC-17: 네비게이션 링크
- When `GET /`를 호출하면
- Then 응답 HTML에 `href="/patterns/consecutive"`가 포함된다.
