## Task Decomposition
SPEC: SPEC-WEB-001

| Task ID | Description | Requirement | Dependencies | Planned Files | Status |
|---------|-------------|-------------|--------------|---------------|--------|
| T-001 | 의존성 추가 및 패키지 골격 생성 | REQ-WEB-SERVER-03 | - | requirements.txt, pyproject.toml, lotto/web/__init__.py, lotto/web/routes/__init__.py | completed |
| T-002 | FastAPI 앱 인스턴스 + /health 엔드포인트 | REQ-WEB-SERVER-01/03/05 | T-001 | lotto/web/app.py, lotto/web/routes/api.py (partial), tests/test_web_app.py | completed |
| T-003 | 픽스처 생성 + interpolate_color 함수 | REQ-WEB-BADGE-02, REQ-WEB-DATA-01 | T-001 | tests/fixtures/web_mini_stats.json, lotto/web/data.py (partial), tests/test_web_data.py (partial) | completed |
| T-004 | compute_frequency_percentiles 함수 | REQ-WEB-BADGE-01 | T-003 | lotto/web/data.py (partial), tests/test_web_data.py (partial) | completed |
| T-005 | get_draws / get_stats / get_data_status 래퍼 | REQ-WEB-DATA-01/02, REQ-WEB-SERVER-04 | T-004 | lotto/web/data.py (partial), tests/test_web_data.py (partial), tests/conftest.py | completed |
| T-006 | get_recommendations / get_simulation 래퍼 | REQ-WEB-DATA-01 | T-005 | lotto/web/data.py (complete), tests/test_web_data.py (complete) | completed |
| T-007 | base.html + 면책 배너 + 탭 네비게이션 | REQ-WEB-PAGE-06/07/08, REQ-WEB-STYLE-01/02 | T-002 | lotto/web/templates/base.html, lotto/web/static/.gitkeep | completed |
| T-008 | index.html + GET / 라우트 | REQ-WEB-PAGE-01 | T-007 | lotto/web/templates/index.html, lotto/web/routes/pages.py (partial), tests/test_web_pages.py (partial) | completed |
| T-009 | collect.html + GET /collect 라우트 | REQ-WEB-PAGE-02 | T-007 | lotto/web/templates/collect.html, lotto/web/routes/pages.py (partial), tests/test_web_pages.py (partial) | completed |
| T-010 | analyze.html + 시그니처 배지 + GET /analyze | REQ-WEB-PAGE-03, REQ-WEB-BADGE-01/02/03, REQ-WEB-CHART-01/02 | T-007 | lotto/web/templates/analyze.html, lotto/web/routes/pages.py (partial), tests/test_web_pages.py (partial) | completed |
| T-011 | recommend.html + GET /recommend?count=N | REQ-WEB-PAGE-04, REQ-WEB-API-07 | T-007 | lotto/web/templates/recommend.html, lotto/web/routes/pages.py (partial), tests/test_web_pages.py (partial) | completed |
| T-012 | simulate.html + GET /simulate?rounds=K | REQ-WEB-PAGE-05, REQ-WEB-CHART-03 | T-007 | lotto/web/templates/simulate.html, lotto/web/routes/pages.py (complete), tests/test_web_pages.py (complete) | completed |
| T-013 | GET API 4개 + 입력 검증 + 503 처리 | REQ-WEB-API-01/02/03/04/07/08 | T-006 | lotto/web/routes/api.py (partial), tests/test_web_api.py (partial) | completed |
| T-014 | POST /api/collect + /api/analyze (BackgroundTasks) | REQ-WEB-API-05/06, REQ-WEB-ASYNC-02 | T-013 | lotto/web/routes/api.py (complete), tests/test_web_api.py (complete) | completed |
| T-015 | web CLI 서브커맨드 | REQ-WEB-SERVER-01/02 | T-002 | main.py 또는 lotto/cli.py, tests/test_cli_web.py | completed |
| T-016 | 커버리지 보강 + 회귀 검증 + 문서 업데이트 | REQ-WEB-TEST-03, AC-034~039 | T-001~T-015 all | tests/ (coverage gap fills), README.md, CHANGELOG.md | completed |
