"""SPEC-LOTTO-002: lotto/config.py 설정 외부화 모듈 테스트.

@MX:SPEC: SPEC-LOTTO-002 REQ-CFG-001~005
"""

from __future__ import annotations

import importlib
import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _clear_lotto_env() -> Iterator[None]:
    """각 테스트 전후 LOTTO_* 환경 변수를 격리합니다."""
    saved = {k: v for k, v in os.environ.items() if k.startswith("LOTTO_")}
    for k in list(os.environ.keys()):
        if k.startswith("LOTTO_"):
            del os.environ[k]
    # lotto.config 모듈 캐시 무효화
    sys.modules.pop("lotto.config", None)
    yield
    for k in list(os.environ.keys()):
        if k.startswith("LOTTO_"):
            del os.environ[k]
    os.environ.update(saved)
    sys.modules.pop("lotto.config", None)


def _import_config():
    """매 테스트마다 깨끗한 lotto.config 모듈을 가져옵니다."""
    sys.modules.pop("lotto.config", None)
    return importlib.import_module("lotto.config")


def test_config_module_exists_and_exports_settings() -> None:
    """REQ-CFG-001: lotto.config 모듈이 settings 객체를 export 해야 한다."""
    config = _import_config()
    assert hasattr(config, "settings"), "config 모듈에 settings 객체가 없습니다"


def test_default_api_url_when_env_unset() -> None:
    """REQ-CFG-002 (3): 환경 변수 미설정 시 기본 API URL을 사용."""
    config = _import_config()
    assert "dhlottery.co.kr" in config.settings.api_url
    assert "{drw_no}" in config.settings.api_url


def test_api_url_overridden_by_env() -> None:
    """REQ-CFG-002 (1): 환경 변수가 있으면 환경 변수 값을 사용."""
    os.environ["LOTTO_API_URL"] = "https://example.com/lotto?drwNo={drw_no}"
    config = _import_config()
    assert config.settings.api_url == "https://example.com/lotto?drwNo={drw_no}"


def test_default_data_dir() -> None:
    """REQ-CFG-004: LOTTO_DATA_DIR 기본값은 'data'."""
    config = _import_config()
    assert config.settings.data_dir == Path("data")


def test_data_dir_overridden_by_env() -> None:
    """REQ-CFG-002: LOTTO_DATA_DIR 환경 변수 오버라이드."""
    os.environ["LOTTO_DATA_DIR"] = "/tmp/lotto_test_data"
    config = _import_config()
    assert config.settings.data_dir == Path("/tmp/lotto_test_data")


def test_default_recommender_weights() -> None:
    """REQ-CFG-004: 기본 추천 가중치는 (0.4, 0.3, 0.2, 0.1)."""
    config = _import_config()
    assert config.settings.recommender_weights == (0.4, 0.3, 0.2, 0.1)


def test_recommender_weights_parsed_from_env() -> None:
    """REQ-CFG-002: 콤마 구분 문자열을 float 4-튜플로 파싱."""
    os.environ["LOTTO_RECOMMENDER_WEIGHTS"] = "0.5,0.25,0.15,0.1"
    config = _import_config()
    assert config.settings.recommender_weights == (0.5, 0.25, 0.15, 0.1)


def test_recommender_weights_invalid_raises_value_error() -> None:
    """REQ-CFG-005: 잘못된 형식의 가중치는 ValueError를 발생시켜야 한다."""
    os.environ["LOTTO_RECOMMENDER_WEIGHTS"] = "not,valid,floats,here"
    with pytest.raises(ValueError, match="LOTTO_RECOMMENDER_WEIGHTS"):
        _import_config()


def test_recommender_weights_wrong_count_raises_value_error() -> None:
    """REQ-CFG-005: 가중치 개수가 4가 아니면 ValueError."""
    os.environ["LOTTO_RECOMMENDER_WEIGHTS"] = "0.4,0.3,0.2"
    with pytest.raises(ValueError, match="LOTTO_RECOMMENDER_WEIGHTS"):
        _import_config()


def test_default_checkpoint_interval() -> None:
    """REQ-CFG-004: 기본 체크포인트 간격은 20."""
    config = _import_config()
    assert config.settings.checkpoint_interval == 20


def test_checkpoint_interval_parsed_from_env() -> None:
    """REQ-CFG-002: LOTTO_CHECKPOINT_INTERVAL 환경 변수 정수 파싱."""
    os.environ["LOTTO_CHECKPOINT_INTERVAL"] = "50"
    config = _import_config()
    assert config.settings.checkpoint_interval == 50


def test_checkpoint_interval_invalid_raises_value_error() -> None:
    """REQ-CFG-005: 잘못된 정수 형식은 ValueError."""
    os.environ["LOTTO_CHECKPOINT_INTERVAL"] = "not-a-number"
    with pytest.raises(ValueError, match="LOTTO_CHECKPOINT_INTERVAL"):
        _import_config()


def test_default_scraper_urls() -> None:
    """REQ-CFG-004: 기본 스크래퍼 URL 2개."""
    config = _import_config()
    assert len(config.settings.scraper_urls) == 2
    assert all("tistory" in url for url in config.settings.scraper_urls)


def test_scraper_urls_overridden_by_env() -> None:
    """REQ-CFG-002: LOTTO_SCRAPER_URL_1/2로 개별 오버라이드."""
    os.environ["LOTTO_SCRAPER_URL_1"] = "https://example.com/page1"
    os.environ["LOTTO_SCRAPER_URL_2"] = "https://example.com/page2"
    config = _import_config()
    assert config.settings.scraper_urls == [
        "https://example.com/page1",
        "https://example.com/page2",
    ]


def test_default_web_host_and_port() -> None:
    """REQ-CFG-004: 기본 웹 호스트/포트."""
    config = _import_config()
    assert config.settings.web_host == "127.0.0.1"
    assert config.settings.web_port == 8000


def test_web_host_port_overridden() -> None:
    """REQ-CFG-002: 웹 호스트/포트 환경 변수 오버라이드."""
    os.environ["LOTTO_WEB_HOST"] = "0.0.0.0"  # noqa: S104
    os.environ["LOTTO_WEB_PORT"] = "9090"
    config = _import_config()
    assert config.settings.web_host == "0.0.0.0"  # noqa: S104
    assert config.settings.web_port == 9090


def test_web_port_invalid_raises_value_error() -> None:
    """REQ-CFG-005: 잘못된 포트 형식은 ValueError."""
    os.environ["LOTTO_WEB_PORT"] = "abc"
    with pytest.raises(ValueError, match="LOTTO_WEB_PORT"):
        _import_config()


def test_dotenv_optional_import_does_not_fail() -> None:
    """REQ-CFG-003: python-dotenv 미설치 환경에서도 임포트가 실패하지 않아야 한다.

    실제 미설치 환경에서 _import_config() 가 성공하는 것으로 충분히 검증된다.
    """
    config = _import_config()
    assert config.settings is not None
