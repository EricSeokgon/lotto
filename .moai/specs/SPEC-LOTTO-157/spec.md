# SPEC-LOTTO-157: 완전제곱수 분포 분석

## 메타데이터

| 항목 | 값 |
|------|-----|
| SPEC ID | SPEC-LOTTO-157 |
| 제목 | 완전제곱수 분포 분석 |
| 상태 | DONE |
| 우선순위 | Medium |
| 생성일 | 2026-06-29 |

## 개요

1~45 범위의 완전제곱수(1, 4, 9, 16, 25, 36) 6개가 각 로또 회차 당첨 번호에 얼마나 포함되는지 분포를 분석한다. 이론적 기댓값(6/45×6 = 0.800)과 실제 데이터를 비교한다.

## 구현 파일

- `lotto/web/data.py`: `get_perfect_square_analysis()` 함수
- `lotto/web/routes/pages.py`: `/stats/perfect-square` 라우트
- `lotto/web/templates/perfect_square.html`: Bootstrap 5 템플릿
- `lotto/web/templates/base.html`: 네비게이션 항목 추가
- `tests/test_perfect_square.py`: 10개 테스트
