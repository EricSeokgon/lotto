# SPEC-LOTTO-167: 고구간(31~45) 분포 분석

## 메타데이터

| 항목 | 값 |
|------|-----|
| SPEC ID | SPEC-LOTTO-167 |
| 제목 | 고구간(31~45) 분포 분석 |
| 상태 | DONE |
| 우선순위 | Medium |
| 생성일 | 2026-06-30 |

## 개요

1~45를 세 구간으로 나눌 때 고구간(31~45) 15개가 각 로또 회차 당첨 번호에 얼마나 포함되는지 분포를 분석한다. 이론적 기댓값(15/45×6 = 2.0)과 실제 데이터를 비교한다.

## 구현 파일

- `lotto/web/data.py`: `get_high_zone_analysis()` 함수
- `lotto/web/routes/pages.py`: `/stats/high-zone` 라우트
- `lotto/web/templates/high_zone.html`: Bootstrap 5 템플릿
- `lotto/web/templates/base.html`: 네비게이션 항목 추가
- `tests/test_high_zone.py`: 10개 테스트
