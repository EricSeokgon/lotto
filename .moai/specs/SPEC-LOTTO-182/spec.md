# SPEC-LOTTO-182: 십일각수(Hendecagonal Numbers) 포함 분포 분석

## 상태
DONE

## 목표
로또 당첨 번호 중 십일각수(Hendecagonal Number)가 몇 개 포함되는지 분포를 분석한다.

## 십일각수 정의
십일각수 H(n) = n(9n-7)/2.
1~45 범위 내 3개: {1, 11, 30}
이론 기댓값 = 3/45 × 6 = 0.4개/회

## 완료 기준
- [x] get_hendecagonal_analysis() 구현
- [x] /stats/hendecagonal 라우트 등록
- [x] hendecagonal.html 템플릿 완료
- [x] base.html 네비 항목 추가
- [x] 10개 테스트 통과
