# Interview: 로또 웹 대시보드

## Round 0: Scope Clarification
Question: 웹 대시보드에 대해 더 자세히 설명해 주세요.
Answer: CLI 결과를 브라우저에서 시각화 — analyze 및 recommend 명령어 결과를 차트와 테이블로 보여주는 웹 UI (FastAPI/Jinja2 또는 React로 구현, 실시간 데이터 업데이트 없음)

## Round 1: Scope
Question: 대시보드에 포함할 화면과 제외할 것은 무엇인가요?
Answer: 포함 — 수집 + 통계 + 추천 + 시뮬레이션 전체 (CLI 4개 명령 결과를 모두 화면으로 제공, 탭 및 네비게이션 포함)

## Round 2: Constraints
Question: 기술 스택 제약사항은 무엇인가요?
Answer: FastAPI + Jinja2 — Python만 사용, 기존 lotto 패키지를 직접 import, Chart.js나 Plotly.js로 차트 렌더링, Node.js 빌드 환경 불필요

## Clarity Score
Initial: 2/10
Final: 8/10
Rounds completed: 2
