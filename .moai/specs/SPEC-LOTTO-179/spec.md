# SPEC-LOTTO-179: 팔각수(Octagonal Numbers) 포함 분포 분석

## 상태
DONE

## 목표
로또 당첨 번호 중 팔각수(Octagonal Number)가 몇 개 포함되는지 분포를 분석한다.

## 팔각수 정의
팔각수 O(n) = n(3n-2).
1~45 범위 내 4개: {1, 8, 21, 40}
이론 기댓값 = 4/45 × 6 ≈ 0.533개/회

## 완료 기준
- [x] get_octagonal_analysis() 구현
- [x] /stats/octagonal 라우트 등록
- [x] octagonal.html 템플릿 완료
- [x] base.html 네비 항목 추가
- [x] 10개 테스트 통과
