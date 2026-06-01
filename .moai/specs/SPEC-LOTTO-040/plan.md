# SPEC-LOTTO-040 구현 계획

## 방법론

TDD (RED-GREEN-REFACTOR). `quality.yaml` development_mode=tdd 기준.

## 영향 범위 파일

| 파일 | 변경 | 설명 |
|------|------|------|
| `lotto/web/data.py` | 추가 | `compare_numbers()` 집계 함수 + 등급/빈도 헬퍼 |
| `lotto/web/routes/api.py` | 추가 | `CompareRequest` 모델 + `POST /api/compare` |
| `lotto/web/routes/pages.py` | 추가 | `GET /compare` 페이지 라우트 |
| `lotto/web/templates/compare.html` | 신규 | 입력 폼 + 결과 표시 |
| `lotto/web/templates/base.html` | 수정 | 네비게이션에 `/compare` 추가 (데스크톱+모바일) |
| `tests/test_compare_numbers.py` | 신규 | 단위 테스트 (~8) |
| `tests/test_api_compare.py` | 신규 | API 테스트 (~5) |
| `tests/test_compare_page.py` | 신규 | 페이지 테스트 (~4) |

## TDD 순서

1. RED: `test_compare_numbers.py` 작성 → 전부 실패
2. GREEN: `compare_numbers()` 구현 → 단위 통과
3. RED: `test_api_compare.py` 작성 → 실패
4. GREEN: `POST /api/compare` 추가 → API 통과
5. RED: `test_compare_page.py` 작성 → 실패
6. GREEN: `/compare` 라우트 + `compare.html` + nav 추가 → 페이지 통과
7. 전체 스위트 실행 (985 → 985+신규)
8. REFACTOR (필요 시)

## 설계 결정

- POST + Pydantic 검증: `analyze-combination`(SPEC-LOTTO-028) 패턴과 일관.
- `_UNSET` 센티넬: `dashboard_overview`/`prediction_report` 패턴과 일관.
- 등급: 3+ 일치 비율 vs 무작위 기대치(C(6,3)*C(39,3)/C(45,6) ≈ 0.0186).

## 품질 게이트

- LSP 0 에러, 신규 테스트 전부 통과, 전체 회귀 없음.
- @MX 태그: data.py 집계 함수에 NOTE + SPEC.
