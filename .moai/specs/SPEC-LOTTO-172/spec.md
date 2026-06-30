# SPEC-LOTTO-172: 카탈란 수 포함 분포 분석

## 메타데이터

| 항목 | 값 |
|------|-----|
| SPEC ID | SPEC-LOTTO-172 |
| 제목 | 카탈란 수(Catalan Number) 포함 분포 분석 |
| 상태 | DONE |
| 우선순위 | Medium |
| 생성일 | 2026-06-30 |

## 개요

카탈란 수(Cn = C(2n,n)/(n+1)) 중 1~45 범위 내 값 {1,2,5,14,42} = 5개의
당첨 번호 포함 빈도 분포를 분석한다. 이론 기댓값 = 5/45×6 ≈ 0.667.

## 구현 파일

- `lotto/web/data.py`: `get_catalan_analysis()` 함수
- `lotto/web/routes/pages.py`: `/stats/catalan` 라우트
- `lotto/web/templates/catalan.html`: Bootstrap 5 템플릿 (보라색 #6f42c1 테마)
- `lotto/web/templates/base.html`: 네비게이션 항목 추가
- `tests/test_catalan.py`: 10개 테스트
