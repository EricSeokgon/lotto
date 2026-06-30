# SPEC-LOTTO-173: 하샤드 수 포함 분포 분석

## 메타데이터

| 항목 | 값 |
|------|-----|
| SPEC ID | SPEC-LOTTO-173 |
| 제목 | 하샤드 수(Harshad Number) 포함 분포 분석 |
| 상태 | DONE |
| 우선순위 | Medium |
| 생성일 | 2026-06-30 |

## 개요

각 자릿수의 합으로 나누어 떨어지는 하샤드 수 21개
{1~9, 10, 12, 18, 20, 21, 24, 27, 30, 36, 40, 42, 45}의
당첨 번호 포함 빈도 분포를 분석한다. 이론 기댓값 = 21/45×6 = 2.8.

## 구현 파일

- `lotto/web/data.py`: `get_harshad_analysis()` 함수
- `lotto/web/routes/pages.py`: `/stats/harshad` 라우트
- `lotto/web/templates/harshad.html`: Bootstrap 5 템플릿 (bg-success 테마)
- `lotto/web/templates/base.html`: 네비게이션 항목 추가
- `tests/test_harshad.py`: 10개 테스트
