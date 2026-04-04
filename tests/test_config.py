"""Tests for configuration system."""

import os
from unittest.mock import patch

from omnirag.config import OmniRAGConfig, load_config


def test_default_config():
    config = OmniRAGConfig()
    assert config.server.host == "127.0.0.1"
    assert config.server.port == 8100
    assert config.security.enabled is False
    assert config.compiler.enabled is True


def test_load_config_from_env():
    env = {
        "OMNIRAG_HOST": "0.0.0.0",
        "OMNIRAG_PORT": "9000",
        "OMNIRAG_API_KEYS": "key1,key2",
        "OMNIRAG_RATE_LIMIT": "50",
        "OMNIRAG_COMPILER": "false",
        "OMNIRAG_LOG_LEVEL": "DEBUG",
    }
    with patch.dict(os.environ, env, clear=False):
        config = load_config()
    assert config.server.host == "0.0.0.0"
    assert config.server.port == 9000
    assert config.security.api_keys == ["key1", "key2"]
    assert config.security.enabled is True
    assert config.security.rate_limit == 50
    assert config.compiler.enabled is False
    assert config.observability.log_level == "DEBUG"


def test_empty_api_keys():
    with patch.dict(os.environ, {"OMNIRAG_API_KEYS": ""}, clear=False):
        config = load_config()
    assert config.security.api_keys == []
    assert config.security.enabled is False
