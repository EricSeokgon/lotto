# SPEC-LOTTO-187: 십육각수(Hexadecagonal Numbers) 포함 분포 분석

## 상태
DONE

## 목표
로또 당첨 번호 중 십육각수(Hexadecagonal Number)가 몇 개 포함되는지 분포를 분석한다.

## 십육각수 정의
십육각수 H(n) = 7n²-6n.
1~45 범위 내 3개: {1, 16, 45}
이론 기댓값 = 3/45 × 6 = 0.4개/회

## 완료 기준
- [x] get_hexadecagonal_analysis() 구현
- [x] /stats/hexadecagonal 라우트 등록
- [x] hexadecagonal.html 템플릿 완료
- [x] base.html 네비 항목 추가
- [x] 10개 테스트 통과
