"""SPEC-LOTTO-004 REQ-INT-005: Config 검증 에러 경로 테스트.

부동소수 가중치 파싱 실패, dotenv 미설치 분기를 검증한다.

@MX:SPEC: SPEC-LOTTO-004 REQ-INT-005
"""

from __future__ import annotations

import importlib
import os
import sys
from collections.abc import Iterator
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _clear_lotto_env() -> Iterator[None]:
    """각 테스트 전후 LOTTO_* 환경 변수를 격리한다."""
    saved = {k: v for k, v in os.environ.items() if k.startswith("LOTTO_")}
    for k in list(os.environ.keys()):
        if k.startswith("LOTTO_"):
            del os.environ[k]
    sys.modules.pop("lotto.config", None)
    yield
    for k in list(os.environ.keys()):
        if k.startswith("LOTTO_"):
            del os.environ[k]
    os.environ.update(saved)
    sys.modules.pop("lotto.config", None)


def _import_config():
    """매 테스트마다 깨끗한 lotto.config 모듈을 가져온다."""
    sys.modules.pop("lotto.config", None)
    return importlib.import_module("lotto.config")


# === Scenario 5.1: 잘못된 보너스 회피 가중치 ===


def test_invalid_bonus_avoidance_weight_raises_value_error() -> None:
    """Scenario 5.1: 비숫자 값에 대해 ValueError 발생."""
    os.environ["LOTTO_BONUS_AVOIDANCE_WEIGHT"] = "abc"

    with pytest.raises(ValueError, match="LOTTO_BONUS_AVOIDANCE_WEIGHT"):
        _import_config()


def test_invalid_bonus_avoidance_weight_with_empty_string() -> None:
    """빈 문자열도 ValueError 발생."""
    os.environ["LOTTO_BONUS_AVOIDANCE_WEIGHT"] = ""

    with pytest.raises(ValueError, match="LOTTO_BONUS_AVOIDANCE_WEIGHT"):
        _import_config()


def test_valid_bonus_avoidance_weight_parsed() -> None:
    """정상 float 값은 정상 파싱되어야 한다."""
    os.environ["LOTTO_BONUS_AVOIDANCE_WEIGHT"] = "0.75"

    config = _import_config()

    assert config.settings.bonus_avoidance_weight == 0.75


# === Scenario 5.2: dotenv 미설치 경로 ===


def test_load_settings_works_without_dotenv() -> None:
    """Scenario 5.2: _DOTENV_AVAILABLE=False 환경에서도 정상 동작한다."""
    config = _import_config()

    # 강제로 dotenv 비활성화 후 _load_settings 재호출
    with patch.object(config, "_DOTENV_AVAILABLE", False):
        settings = config._load_settings()

    assert settings is not None
    assert settings.api_url is not None
    assert settings.data_dir is not None


def test_load_dotenv_noop_when_unavailable() -> None:
    """_DOTENV_AVAILABLE=False 시 _load_dotenv가 호출되지 않거나 no-op."""
    config = _import_config()

    # _load_dotenv가 False를 반환하거나 호출되지 않는지 확인
    with (
        patch.object(config, "_DOTENV_AVAILABLE", False),
        patch.object(config, "_load_dotenv") as mock_loader,
    ):
        settings = config._load_settings()
        # _DOTENV_AVAILABLE이 False일 때는 _load_dotenv를 호출하지 않아야 한다
        mock_loader.assert_not_called()

    assert settings is not None


# === 추가 에러 경로 ===


def test_invalid_web_port_raises_with_clear_message() -> None:
    """LOTTO_WEB_PORT 잘못된 값에 대한 명확한 메시지."""
    os.environ["LOTTO_WEB_PORT"] = "xyz"

    with pytest.raises(ValueError, match="LOTTO_WEB_PORT"):
        _import_config()


def test_invalid_checkpoint_interval_message() -> None:
    """LOTTO_CHECKPOINT_INTERVAL 잘못된 값에 대한 명확한 메시지."""
    os.environ["LOTTO_CHECKPOINT_INTERVAL"] = "not-a-number"

    with pytest.raises(ValueError, match="LOTTO_CHECKPOINT_INTERVAL"):
        _import_config()


def test_default_bonus_avoidance_weight_is_zero() -> None:
    """환경 변수 미설정 시 기본값은 0.0."""
    config = _import_config()

    assert config.settings.bonus_avoidance_weight == 0.0


def test_recommender_weights_with_partial_invalid_content() -> None:
    """REQ-INT-005: 가중치 일부가 비숫자(예: 'abc') 시 ValueError."""
    os.environ["LOTTO_RECOMMENDER_WEIGHTS"] = "0.5,0.3,abc,0.1"

    with pytest.raises(ValueError, match="LOTTO_RECOMMENDER_WEIGHTS"):
        _import_config()


def test_recommender_weights_wrong_count_two_values() -> None:
    """REQ-INT-005: 가중치 개수 < 4 시 ValueError (4개 필요)."""
    os.environ["LOTTO_RECOMMENDER_WEIGHTS"] = "0.5,0.5"

    with pytest.raises(ValueError, match="정확히 4개"):
        _import_config()


def test_fallback_load_dotenv_returns_false() -> None:
    """_DOTENV_AVAILABLE=False 환경에서 fallback _load_dotenv()는 False를 반환한다."""
    config = _import_config()

    if not config._DOTENV_AVAILABLE:
        result = config._load_dotenv()
        assert result is False
