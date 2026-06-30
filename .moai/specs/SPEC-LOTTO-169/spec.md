# SPEC-LOTTO-169: 번호 합계 분포 분석

## 메타데이터

| 항목 | 값 |
|------|-----|
| SPEC ID | SPEC-LOTTO-169 |
| 제목 | 번호 합계 분포 분석 |
| 상태 | DONE |
| 우선순위 | Medium |
| 생성일 | 2026-06-30 |

## 개요

6개 당첨 번호의 합계를 6개 구간(~99, 100~124, 125~149, 150~174, 175~199, 200~)으로 분류해 분포를 분석한다. 이론 평균 = 6 × (1+45)/2 = 138.0.

## 구현 파일

- `lotto/web/data.py`: `get_sum_analysis()` 함수
- `lotto/web/routes/pages.py`: `/stats/sum` 라우트
- `lotto/web/templates/sum_dist.html`: Bootstrap 5 템플릿
- `lotto/web/templates/base.html`: 네비게이션 항목 추가
- `tests/test_sum_dist.py`: 10개 테스트
