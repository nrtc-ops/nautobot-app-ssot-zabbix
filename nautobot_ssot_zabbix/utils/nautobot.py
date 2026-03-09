"""Utility functions for translating Nautobot objects to Zabbix parameters."""

import logging
from typing import Optional

from django.conf import settings

logger = logging.getLogger("nautobot.jobs")


def get_plugin_config() -> dict:
    """Return the nautobot_ssot_zabbix PLUGINS_CONFIG dict."""
    return settings.PLUGINS_CONFIG.get("nautobot_ssot_zabbix", {})


def resolve_hostgroup_name(device) -> str:
    """Determine the Zabbix host group name for a Nautobot device.

    Resolution order:
    1. location_hostgroup_map config — keyed by location slug
    2. Tenant name if device has a tenant
    3. Location name prefixed by default_location_hostgroup_prefix config
    4. Fallback: "Nautobot-Managed"

    Args:
        device: Nautobot Device instance

    Returns:
        Host group name string
    """
    cfg = get_plugin_config()
    location_map: dict = cfg.get("location_hostgroup_map", {})
    prefix: str = cfg.get("default_location_hostgroup_prefix", "Location-")

    if device.location and device.location.slug in location_map:
        return location_map[device.location.slug]

    if device.tenant:
        return device.tenant.name

    if device.location:
        return f"{prefix}{device.location.name}"

    return "Nautobot-Managed"


def resolve_template_name(device) -> Optional[str]:
    """Determine the Zabbix template name for a Nautobot device.

    Resolution order:
    1. device_role_template_map config — keyed by device role slug
    2. default_template config value
    3. None (no template linked)

    Args:
        device: Nautobot Device instance

    Returns:
        Template name string or None
    """
    cfg = get_plugin_config()
    role_map: dict = cfg.get("device_role_template_map", {})
    default: Optional[str] = cfg.get("default_template")

    if device.role and device.role.slug in role_map:
        return role_map[device.role.slug]

    return default


def get_primary_ip(device) -> Optional[str]:
    """Extract the primary IP address string from a Nautobot device.

    Prefers primary_ip4 over primary_ip6.

    Args:
        device: Nautobot Device instance

    Returns:
        IP address string (without prefix length), or None
    """
    ip_obj = device.primary_ip4 or device.primary_ip6
    if ip_obj:
        return str(ip_obj.address.ip)
    return None


def build_zabbix_tags(device) -> list:
    """Build a list of Zabbix tags from Nautobot device metadata.

    Tags preserve Nautobot context in Zabbix and enable filtering.

    Args:
        device: Nautobot Device instance

    Returns:
        List of Zabbix tag dicts: [{"tag": "key", "value": "value"}, ...]
    """
    tags = [
        {"tag": "source", "value": "nautobot"},
        {"tag": "nautobot_id", "value": str(device.pk)},
    ]

    if device.location:
        tags.append({"tag": "location", "value": device.location.slug})

    if device.role:
        tags.append({"tag": "role", "value": device.role.slug})

    if device.device_type:
        tags.append({"tag": "device_type", "value": device.device_type.slug})

    if device.tenant:
        tags.append({"tag": "tenant", "value": device.tenant.slug})

    if device.platform:
        tags.append({"tag": "platform", "value": device.platform.slug})

    return tags
