# SPEC-LOTTO-041 인수 기준 (Given-When-Then)

## 데이터 레이어: range_stats

### AC-1: 정상 구간 집계
- Given 회차 1~4를 가진 데이터셋
- When `range_stats(1, 2)` 호출
- Then `total_draws == 2`, `number_frequency`는 1~45 전체 키(45개),
  구간 1~2 회차 번호만 집계됨

### AC-2: 당첨금 통계
- Given 구간 내 prize1Amount가 있는 회차들
- When `range_stats(start, end)` 호출
- Then `avg_prize1`은 정수 평균, `highest_prize1_draw`/`lowest_prize1_draw`는
  올바른 회차를 식별

### AC-3: 구간 내 당첨금 데이터 없음
- Given 구간 내 모든 prize1Amount가 None
- When `range_stats` 호출
- Then `avg_prize1 is None`, `highest_prize1_draw is None`,
  `lowest_prize1_draw is None`

### AC-4: 역전 구간 (start > end)
- Given 임의 데이터
- When `range_stats(100, 1)` 호출
- Then 예외 없이 `total_draws == 0`인 일관된 빈 구조 반환

### AC-5: 매칭 회차 없음
- Given 회차 1~3만 존재하는 데이터
- When `range_stats(50, 100)` 호출
- Then `total_draws == 0`, 모든 빈도 0, 당첨금 None

### AC-6: 단일 회차 구간
- Given 회차 5 포함 데이터
- When `range_stats(5, 5)` 호출
- Then `total_draws == 1`, 해당 회차 통계 정확

### AC-7: None 입력
- Given `draws=None` 명시 전달
- When `range_stats(1, 100, None)` 호출
- Then 일관된 빈 구조 반환 (예외 없음)

### AC-8: 결정성
- Given 동일 데이터셋
- When `range_stats`를 반복 호출
- Then 동일 결과 반환

## API: GET /api/stats/range

### AC-9: 정상 응답
- When `GET /api/stats/range?start_drw=1&end_drw=50`
- Then HTTP 200, 모든 키 포함 JSON

### AC-10: 역전 구간 검증
- When `GET /api/stats/range?start_drw=50&end_drw=1`
- Then HTTP 422

### AC-11: 필수 파라미터 누락
- When `GET /api/stats/range?end_drw=50` (start_drw 누락)
- Then HTTP 422

### AC-12: 데이터 부재
- Given `get_draws()`가 None을 반환하도록 patch
- When `GET /api/stats/range?start_drw=1&end_drw=50`
- Then HTTP 200 + 빈 구조

### AC-13: total_draws 정확성
- Given 회차 데이터를 patch
- When 유효 구간 호출
- Then 응답의 `total_draws`가 구간 내 회차 수와 일치

## 페이지: GET /stats/range

### AC-14: 폼만 표시
- When `GET /stats/range` (파라미터 없음)
- Then HTTP 200 HTML, 입력 폼 표시

### AC-15: 통계 표시
- When `GET /stats/range?start_drw=1&end_drw=10`
- Then HTTP 200 HTML, 통계 결과 표시

### AC-16: 데이터 부재에도 200
- Given `get_draws()`가 None을 반환하도록 patch
- When `GET /stats/range?start_drw=1&end_drw=10`
- Then HTTP 200 (정상 동작)

### AC-17: 네비게이션 링크
- When `GET /` (인덱스)
- Then 응답 HTML에 `href="/stats/range"` 포함
