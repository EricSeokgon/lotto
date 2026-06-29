# SPEC-LOTTO-154: 37의 배수 분포 분석

## 메타데이터

| 항목 | 값 |
|------|-----|
| SPEC ID | SPEC-LOTTO-154 |
| 제목 | 37의 배수 분포 분석 |
| 상태 | DONE |
| 우선순위 | Medium |
| 생성일 | 2026-06-29 |

## 개요

1~45 범위에서 37의 배수(37)가 각 로또 회차 당첨 번호 6개에 얼마나 포함되는지 분포를 분석한다. 이론적 기댓값(1/45×6 = 0.133)과 실제 데이터를 비교한다.

## 구현 파일

- `lotto/web/data.py`: `get_multiples37_analysis()` 함수
- `lotto/web/routes/pages.py`: `/stats/multiples-37` 라우트
- `lotto/web/templates/multiples37.html`: Bootstrap 5 템플릿
- `lotto/web/templates/base.html`: 네비게이션 항목 추가
- `tests/test_multiples37.py`: 10개 테스트
