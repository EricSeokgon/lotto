# SPEC-LOTTO-184: 십삼각수(Tridecagonal Numbers) 포함 분포 분석

## 상태
DONE

## 목표
로또 당첨 번호 중 십삼각수(Tridecagonal Number)가 몇 개 포함되는지 분포를 분석한다.

## 십삼각수 정의
십삼각수 T(n) = n(11n-9)/2.
1~45 범위 내 3개: {1, 13, 36}
이론 기댓값 = 3/45 × 6 = 0.4개/회

## 완료 기준
- [x] get_tridecagonal_analysis() 구현
- [x] /stats/tridecagonal 라우트 등록
- [x] tridecagonal.html 템플릿 완료
- [x] base.html 네비 항목 추가
- [x] 10개 테스트 통과
