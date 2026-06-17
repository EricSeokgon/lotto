"""다크모드 & 반응형 UI 테스트 (SPEC-LOTTO-021).

검증 범위:
- REQ-DARK-001: 다크모드 토글 (Tailwind darkMode: 'class', localStorage, prefers-color-scheme)
- REQ-DARK-002: 반응형 햄버거 네비게이션
- REQ-DARK-003: 모바일 테이블 가로 스크롤 (overflow-x-auto)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """테스트 클라이언트 픽스처."""
    from lotto.web.app import app

    return TestClient(app)


# ──────────────────────────────────────────────────────────────────────
# 모든 페이지 라우트가 200을 반환하는지 확인 (기존 회귀 가드)
# ──────────────────────────────────────────────────────────────────────

PAGE_ROUTES = [
    "/",
    "/collect",
    "/analyze",
    "/recommend",
    "/simulate",
    "/history",
    "/purchases",
]


@pytest.mark.parametrize("route", PAGE_ROUTES)
def test_page_returns_200(client, route):
    """모든 페이지가 다크모드 적용 후에도 200을 반환해야 한다."""
    response = client.get(route)
    assert response.status_code == 200, f"{route} 응답 코드: {response.status_code}"


# ──────────────────────────────────────────────────────────────────────
# REQ-DARK-001: 다크모드 토글 검증
# ──────────────────────────────────────────────────────────────────────

def test_base_template_enables_tailwind_dark_mode_class(client):
    """base.html이 Tailwind의 class 기반 darkMode를 활성화해야 한다."""
    response = client.get("/")
    # tailwind.config의 darkMode: 'class' 설정 확인
    assert "darkMode" in response.text
    assert "'class'" in response.text or '"class"' in response.text


def test_base_template_includes_theme_persistence(client):
    """localStorage 기반 테마 저장 코드가 포함돼야 한다."""
    response = client.get("/")
    assert "localStorage" in response.text
    # 'theme' 키 사용
    assert "theme" in response.text


def test_base_template_detects_system_preference(client):
    """prefers-color-scheme 미디어 쿼리로 시스템 테마를 감지해야 한다."""
    response = client.get("/")
    assert "prefers-color-scheme" in response.text


def test_base_template_has_theme_toggle_button(client):
    """헤더에 테마 전환 버튼(id=theme-toggle)이 있어야 한다."""
    response = client.get("/")
    assert 'id="theme-toggle"' in response.text


@pytest.mark.parametrize("route", PAGE_ROUTES)
def test_pages_apply_dark_classes(client, route):
    """모든 페이지가 base.html을 통해 dark: 클래스를 적용받아야 한다."""
    response = client.get(route)
    # base.html에 정의된 다크 토큰들이 응답에 포함되어야 한다
    assert "dark:bg-gray-900" in response.text or "dark:bg-gray-800" in response.text
    assert "dark:text-gray-" in response.text


# ──────────────────────────────────────────────────────────────────────
# REQ-DARK-002: 반응형 햄버거 네비게이션 검증
# ──────────────────────────────────────────────────────────────────────

def test_base_template_has_hamburger_menu_button(client):
    """모바일 햄버거 메뉴 버튼(id=mobile-menu-btn)이 있어야 한다."""
    response = client.get("/")
    assert 'id="mobile-menu-btn"' in response.text
    assert 'id="mobile-menu"' in response.text


def test_base_template_has_responsive_breakpoint_classes(client):
    """md: 반응형 클래스로 모바일/데스크톱 레이아웃을 구분해야 한다."""
    response = client.get("/")
    # 데스크톱 탭은 'hidden md:flex', 햄버거 영역은 'md:hidden'
    assert "hidden md:flex" in response.text
    assert "md:hidden" in response.text


def test_active_tab_highlighted_on_dashboard(client):
    """활성 탭은 시각적 강조를 받아야 한다 (active_tab=dashboard일 때)."""
    response = client.get("/")
    # 대시보드 활성화 시 border-data-blue 클래스가 적용됨
    assert "border-data-blue" in response.text


# ──────────────────────────────────────────────────────────────────────
# REQ-DARK-003: 모바일 테이블 가로 스크롤 검증
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("route", ["/collect", "/history"])
def test_tables_have_horizontal_scroll(client, route):
    """테이블이 있는 페이지는 overflow-x-auto로 모바일 가로 스크롤을 지원해야 한다."""
    response = client.get(route)
    assert "overflow-x-auto" in response.text
