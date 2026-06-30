# SPEC-LOTTO-176: 오각수(Pentagonal Numbers) 포함 분포 분석

## 상태
DONE

## 목표
로또 당첨 번호 중 오각수(Pentagonal Number)가 몇 개 포함되는지 분포를 분석한다.

## 오각수 정의
오각수 P(n) = n(3n-1)/2.
1~45 범위 내 5개: {1, 5, 12, 22, 35}
이론 기댓값 = 5/45 × 6 ≈ 0.667개/회

## 완료 기준
- [x] get_pentagonal_analysis() 구현
- [x] /stats/pentagonal 라우트 등록
- [x] pentagonal.html 템플릿 완료
- [x] base.html 네비 항목 추가
- [x] 10개 테스트 통과
