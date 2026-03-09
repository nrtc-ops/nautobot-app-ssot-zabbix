"""DiffSync models for nautobot_ssot_zabbix.

These shared models define the data contract between the Nautobot adapter
and the Zabbix adapter. Each model maps to one entity type that is
synchronized in both directions.
"""

import logging
from typing import ClassVar, List, Optional

from diffsync import DiffSyncModel

logger = logging.getLogger("nautobot.jobs")


class ZabbixHost(DiffSyncModel):
    """Shared DiffSync model representing a monitored host in Zabbix.

    Maps to a Nautobot Device on the Nautobot side and a Zabbix Host
    on the Zabbix side.

    Identifiers:
        name: The technical hostname, unique in both Nautobot and Zabbix.

    Attributes:
        visible_name: Display name shown in Zabbix UI.
        ip_address: Primary IPv4 address used for monitoring.
        hostgroup: Zabbix host group name.
        template: Zabbix template name, or None.
        enabled: Whether the host is actively monitored.
        description: Free-text description.
        zabbix_id: Zabbix hostid (populated after create/load from Zabbix).
    """

    _modelname: ClassVar[str] = "host"
    _identifiers: ClassVar[tuple] = ("name",)
    _attributes: ClassVar[tuple] = (
        "visible_name",
        "ip_address",
        "hostgroup",
        "template",
        "enabled",
        "description",
    )

    name: str
    visible_name: str = ""
    ip_address: Optional[str] = None
    hostgroup: str = "Nautobot-Managed"
    template: Optional[str] = None
    enabled: bool = True
    description: str = ""
    zabbix_id: Optional[str] = None  # non-synced metadata, populated from Zabbix side

    def create(self, adapter, ids, attrs):
        """Create a new host in the target system (Zabbix).

        Called by DiffSync when a host exists in Nautobot but not in Zabbix.
        """
        from nautobot_ssot_zabbix.utils.zabbix import get_zabbix_client_from_config

        hostname = ids["name"]
        ip = attrs.get("ip_address")
        if not ip:
            adapter.job.logger.warning("Skipping create for '%s' — no IP address.", hostname)
            return self

        client = get_zabbix_client_from_config()
        with client:
            groupid = client.get_or_create_hostgroup(attrs.get("hostgroup", "Nautobot-Managed"))
            templateids = []
            if attrs.get("template"):
                tid = client.get_template_id(attrs["template"])
                if tid:
                    templateids.append(tid)

            result = client.upsert_host(
                hostname=hostname,
                visible_name=attrs.get("visible_name", hostname),
                ip=ip,
                groupids=[groupid],
                templateids=templateids or None,
                description=attrs.get("description", ""),
                enabled=attrs.get("enabled", True),
            )

        adapter.job.logger.info(
            "DiffSync create -> Zabbix '%s': action=%s, hostid=%s",
            hostname,
            result.get("action"),
            result.get("hostid"),
        )
        return self

    def update(self, attrs):
        """Update an existing host in Zabbix.

        Called by DiffSync when a host exists in both systems but attributes differ.
        """
        from nautobot_ssot_zabbix.utils.zabbix import get_zabbix_client_from_config

        hostname = self.name
        ip = attrs.get("ip_address", self.ip_address)
        if not ip:
            logger.warning("Skipping update for '%s' — no IP address.", hostname)
            return self

        client = get_zabbix_client_from_config()
        with client:
            groupid = client.get_or_create_hostgroup(
                attrs.get("hostgroup", self.hostgroup)
            )
            templateids = []
            template_name = attrs.get("template", self.template)
            if template_name:
                tid = client.get_template_id(template_name)
                if tid:
                    templateids.append(tid)

            result = client.upsert_host(
                hostname=hostname,
                visible_name=attrs.get("visible_name", self.visible_name),
                ip=ip,
                groupids=[groupid],
                templateids=templateids or None,
                description=attrs.get("description", self.description),
                enabled=attrs.get("enabled", self.enabled),
            )

        logger.info(
            "DiffSync update -> Zabbix '%s': action=%s, hostid=%s",
            hostname,
            result.get("action"),
            result.get("hostid"),
        )
        return super().update(attrs)

    def delete(self):
        """Delete the host from Zabbix.

        Called by DiffSync when a host exists in Zabbix but not in Nautobot.
        Only removes hosts that were tagged source=nautobot (enforced in the
        ZabbixRemoteAdapter.load() by using get_all_nautobot_hosts()).
        """
        from nautobot_ssot_zabbix.utils.zabbix import get_zabbix_client_from_config

        client = get_zabbix_client_from_config()
        with client:
            result = client.delete_host(hostname=self.name)

        logger.info(
            "DiffSync delete -> Zabbix '%s': action=%s",
            self.name,
            result.get("action"),
        )
        return super().delete()
