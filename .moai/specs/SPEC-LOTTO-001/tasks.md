## Task Decomposition
SPEC: SPEC-LOTTO-001

| Task ID | Description | Requirement | Dependencies | Planned Files | Status |
|---------|-------------|-------------|--------------|---------------|--------|
| T-001 | 프로젝트 설정 파일 생성 (pyproject.toml, ruff.toml, mypy.ini, .gitignore) | REQ-CLI-01 | - | pyproject.toml, ruff.toml, mypy.ini, .gitignore | pending |
| T-002 | Draw/Stats/Recommendation/SimulationResult 데이터 모델 TDD | REQ-COLLECT-01, REQ-ANALYZE-01, REQ-RECOMMEND-01, REQ-SIMULATE-01 | T-001 | lotto/__init__.py, lotto/models.py, tests/test_models.py, tests/conftest.py | pending |
| T-003 | LottoCollector API 수집/재시도/딜레이 TDD | REQ-COLLECT-02~06 | T-002 | lotto/collector.py, tests/test_collector.py, tests/fixtures/api_response.json | pending |
| T-004 | LottoAnalyzer 4종 통계 분석 TDD | REQ-ANALYZE-02~07 | T-002 | lotto/analyzer.py, tests/test_analyzer.py, tests/fixtures/mini_draws.csv | pending |
| T-005 | LottoRecommender 가중 점수 추천 TDD | REQ-RECOMMEND-02~07 | T-004 | lotto/recommender.py, tests/test_recommender.py | pending |
| T-006 | LottoSimulator causal-safe 백테스팅 TDD | REQ-SIMULATE-02~06 | T-003, T-005 | lotto/simulator.py, tests/test_simulator.py | pending |
| T-007 | CLI typer 4개 서브커맨드 + 통합 테스트 | REQ-CLI-01~06 | T-003, T-004, T-005, T-006 | main.py, tests/test_cli.py, tests/test_integration.py, README.md | pending |
