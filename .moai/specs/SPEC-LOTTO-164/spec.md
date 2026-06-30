# SPEC-LOTTO-164: 합성수 분포 분석

## 메타데이터

| 항목 | 값 |
|------|-----|
| SPEC ID | SPEC-LOTTO-164 |
| 제목 | 합성수 분포 분석 |
| 상태 | DONE |
| 우선순위 | Medium |
| 생성일 | 2026-06-30 |

## 개요

1~45 범위의 합성수(소수도 1도 아닌 수) 30개가 각 로또 회차 당첨 번호에 얼마나 포함되는지 분포를 분석한다. 이론적 기댓값(30/45×6 = 4.0)과 실제 데이터를 비교한다.

## 구현 파일

- `lotto/web/data.py`: `get_composite_analysis()` 함수
- `lotto/web/routes/pages.py`: `/stats/composite` 라우트
- `lotto/web/templates/composite.html`: Bootstrap 5 템플릿
- `lotto/web/templates/base.html`: 네비게이션 항목 추가
- `tests/test_composite.py`: 10개 테스트
