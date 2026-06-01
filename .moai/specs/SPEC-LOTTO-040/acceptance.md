# SPEC-LOTTO-040 인수 기준

## AC-1 정상 구조 (REQ-CMP40-001,002,003,004,005,006)

- GIVEN 유효한 6개 번호와 추첨 데이터
- WHEN `compare_numbers(numbers, draws)` 호출
- THEN 응답에 `numbers`, `total_draws_checked`, `match_summary`(6/5/4/3 키),
  `number_frequency`, `grade` 키가 모두 존재한다.

## AC-2 6개 일치 (REQ-CMP40-003)

- GIVEN 입력이 어떤 회차의 본번호 6개와 완전히 일치
- WHEN 비교
- THEN `match_summary["6"]["count"] >= 1`이며 해당 회차가 `draws`에 포함된다.

## AC-3 3개 일치 정확도 (REQ-CMP40-003,004)

- GIVEN 알려진 fixture 데이터
- WHEN 비교
- THEN `match_summary["3"]["count"]`가 정확히 계산되고 회차 목록이 일치한다.

## AC-4 번호 빈도 (REQ-CMP40-005)

- GIVEN 입력 6개 번호
- WHEN 비교
- THEN `number_frequency`에 6개 번호가 모두 존재하고 각 count가 본번호 출현 횟수와 같다.

## AC-5 빈/None 데이터 (REQ-CMP40-007)

- GIVEN draws가 `[]` 또는 명시적 None
- WHEN 비교
- THEN 예외 없이 `total_draws_checked=0`, 모든 수준 count=0/draws=[], 입력 번호 count=0,
  일관된 `grade`를 반환한다.

## AC-6 모든 번호가 모든 회차에 출현 (REQ-CMP40-003)

- GIVEN 입력 6개가 모든 회차의 본번호에 포함
- WHEN 비교
- THEN `match_summary["6"]["count"] == total_draws_checked`.

## AC-7 결정론 (REQ-CMP40-001~006)

- GIVEN 동일 입력
- WHEN 두 번 호출
- THEN 동일 결과.

## AC-8 API 검증 (REQ-CMP40-008)

- 6개 미만 → 422
- 0 또는 46 등 범위 외 → 422
- 중복 번호 → 422

## AC-9 API 데이터 부재 (REQ-CMP40-007)

- `get_draws()`가 None → 200 + 빈 구조.

## AC-10 페이지 (REQ-CMP40-010)

- `GET /compare` → 200 HTML
- 메인 페이지에 `href="/compare"` 포함
- 입력 폼 마커 존재
- 데이터 None일 때도 200.
