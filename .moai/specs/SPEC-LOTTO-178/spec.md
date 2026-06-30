# SPEC-LOTTO-178: 칠각수(Heptagonal Numbers) 포함 분포 분석

## 상태
DONE

## 목표
로또 당첨 번호 중 칠각수(Heptagonal Number)가 몇 개 포함되는지 분포를 분석한다.

## 칠각수 정의
칠각수 H(n) = n(5n-3)/2.
1~45 범위 내 4개: {1, 7, 18, 34}
이론 기댓값 = 4/45 × 6 ≈ 0.533개/회

## 완료 기준
- [x] get_heptagonal_analysis() 구현
- [x] /stats/heptagonal 라우트 등록
- [x] heptagonal.html 템플릿 완료
- [x] base.html 네비 항목 추가
- [x] 10개 테스트 통과
