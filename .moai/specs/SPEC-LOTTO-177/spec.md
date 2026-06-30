# SPEC-LOTTO-177: 육각수(Hexagonal Numbers) 포함 분포 분석

## 상태
DONE

## 목표
로또 당첨 번호 중 육각수(Hexagonal Number)가 몇 개 포함되는지 분포를 분석한다.

## 육각수 정의
육각수 H(n) = n(2n-1).
1~45 범위 내 5개: {1, 6, 15, 28, 45}
이론 기댓값 = 5/45 × 6 ≈ 0.667개/회

## 완료 기준
- [x] get_hexagonal_analysis() 구현
- [x] /stats/hexagonal 라우트 등록
- [x] hexagonal.html 템플릿 완료
- [x] base.html 네비 항목 추가
- [x] 10개 테스트 통과
