# SPEC-LOTTO-181: 십각수(Decagonal Numbers) 포함 분포 분석

## 상태
DONE

## 목표
로또 당첨 번호 중 십각수(Decagonal Number)가 몇 개 포함되는지 분포를 분석한다.

## 십각수 정의
십각수 D(n) = n(4n-3).
1~45 범위 내 3개: {1, 10, 27}
이론 기댓값 = 3/45 × 6 = 0.4개/회

## 완료 기준
- [x] get_decagonal_analysis() 구현
- [x] /stats/decagonal 라우트 등록
- [x] decagonal.html 템플릿 완료
- [x] base.html 네비 항목 추가
- [x] 10개 테스트 통과
