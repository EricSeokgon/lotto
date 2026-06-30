# SPEC-LOTTO-174: 삼각수 포함 분포 분석

## 메타데이터

| 항목 | 값 |
|------|-----|
| SPEC ID | SPEC-LOTTO-174 |
| 제목 | 삼각수(Triangular Number) 포함 분포 분석 |
| 상태 | DONE |
| 우선순위 | Medium |
| 생성일 | 2026-06-30 |

## 개요

삼각수 T(n)=n(n+1)/2 중 1~45 범위 내 9개
{1,3,6,10,15,21,28,36,45}의 당첨 번호 포함 빈도 분포를 분석한다.
이론 기댓값 = 9/45×6 = 1.2.

## 구현 파일

- `lotto/web/data.py`: `get_triangular_analysis()` 함수
- `lotto/web/routes/pages.py`: `/stats/triangular` 라우트
- `lotto/web/templates/triangular.html`: Bootstrap 5 템플릿 (bg-info 테마)
- `lotto/web/templates/base.html`: 네비게이션 항목 추가
- `tests/test_triangular.py`: 10개 테스트
