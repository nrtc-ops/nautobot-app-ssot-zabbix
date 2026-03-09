"""App declaration for nautobot_ssot_zabbix."""

# Metadata is inherited from Nautobot. If not including Nautobot in the environment, this should be added
from importlib import metadata

from nautobot.apps import NautobotAppConfig

__version__ = metadata.version(__name__)


class NautobotSsotZabbixConfig(NautobotAppConfig):
    """App configuration for the nautobot_ssot_zabbix app."""

    name = "nautobot_ssot_zabbix"
    verbose_name = "SSoT Zabbix"
    version = __version__
    author = "NRTC"
    description = "Nautobot SSoT integration for Zabbix monitoring synchronization."
    base_url = "ssot-zabbix"
    required_settings = ["zabbix_url", "zabbix_token"]
    default_settings = {
        "zabbix_url": None,
        "zabbix_token": None,
        "default_location_hostgroup_prefix": "Location-",
        "default_template": None,
        "device_role_template_map": {},
        "location_hostgroup_map": {},
        "ssl_verify": True,
        "sync_saved_objects": True,
    }
    docs_view_name = "plugins:nautobot_ssot_zabbix:docs"
    searchable_models = []


config = NautobotSsotZabbixConfig  # pylint:disable=invalid-name
