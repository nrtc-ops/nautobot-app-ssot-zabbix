"""Pytest conftest — mock out heavy Nautobot/Django dependencies for unit tests."""

import importlib.metadata
import sys
from unittest.mock import MagicMock

# ---- Pre-mock Django and Nautobot so our package can be imported ----
# These mocks must be in place BEFORE any nautobot_ssot_zabbix import happens.

_MODULES_TO_MOCK = [
    "django",
    "django.conf",
    "django.db",
    "django.db.models",
    "nautobot",
    "nautobot.apps",
    "nautobot.apps.jobs",
    "nautobot.dcim",
    "nautobot.dcim.models",
    "nautobot_ssot",
    "nautobot_ssot.contrib",
    "nautobot_ssot.jobs",
    "nautobot_ssot.jobs.base",
]

for mod_name in _MODULES_TO_MOCK:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# Provide a minimal NautobotAppConfig so our __init__.py class definition works
nautobot_apps = sys.modules["nautobot.apps"]
nautobot_apps.NautobotAppConfig = type("NautobotAppConfig", (), {})

# Provide NautobotAdapter, DataSource, DataTarget stubs
nautobot_ssot_contrib = sys.modules["nautobot_ssot.contrib"]
nautobot_ssot_contrib.NautobotAdapter = type("NautobotAdapter", (), {"__init__": lambda self, *a, **kw: None})

nautobot_ssot_base = sys.modules["nautobot_ssot.jobs.base"]
nautobot_ssot_base.DataSource = type("DataSource", (), {})
nautobot_ssot_base.DataTarget = type("DataTarget", (), {})
nautobot_ssot_base.DataMapping = MagicMock

nautobot_jobs = sys.modules["nautobot.apps.jobs"]
nautobot_jobs.BooleanVar = MagicMock
nautobot_jobs.register_jobs = MagicMock()

# Mock importlib.metadata.version to return a fake version
_original_version = importlib.metadata.version


def _patched_version(name):
    if name == "nautobot_ssot_zabbix":
        return "0.1.0-test"
    return _original_version(name)


importlib.metadata.version = _patched_version
