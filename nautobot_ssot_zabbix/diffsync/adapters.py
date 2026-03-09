"""DiffSync adapters for nautobot_ssot_zabbix.

Two adapters bridge the gap between Nautobot and Zabbix:

  ZabbixRemoteAdapter  — loads hosts from the live Zabbix API
  ZabbixNautobotAdapter — loads devices from the Nautobot ORM
"""

import logging
from typing import Optional

from diffsync import Adapter
from nautobot_ssot.contrib import NautobotAdapter

from nautobot_ssot_zabbix.diffsync.models import ZabbixHost
from nautobot_ssot_zabbix.utils.nautobot import (
    build_zabbix_tags,
    get_primary_ip,
    resolve_hostgroup_name,
    resolve_template_name,
)
from nautobot_ssot_zabbix.utils.zabbix import get_zabbix_client_from_config

logger = logging.getLogger("nautobot.jobs")


class ZabbixRemoteAdapter(Adapter):
    """DiffSync adapter that loads data from the Zabbix API.

    Represents the current state of Zabbix. Used as the *target* adapter
    in a Nautobot → Zabbix (DataTarget) sync, and as the *source* adapter
    in a Zabbix → Nautobot (DataSource) sync.
    """

    host = ZabbixHost
    top_level = ["host"]

    def __init__(self, *args, job=None, sync=None, managed_only=False, **kwargs):
        """Initialize the Zabbix remote adapter.

        Args:
            job: The running SSoT Job instance (provides self.job.logger)
            sync: The SSoT Sync model instance
            managed_only: If True, only load hosts tagged source=nautobot.
                          If False (default), load all Zabbix hosts.
        """
        super().__init__(*args, **kwargs)
        self.job = job
        self.sync = sync
        self.managed_only = managed_only

    def load(self):
        """Load hosts from Zabbix into DiffSync models.

        By default loads ALL hosts. When managed_only=True (used by DataTarget),
        only loads hosts tagged source=nautobot so deletions are scoped correctly.
        """
        client = get_zabbix_client_from_config()
        with client:
            hosts = client.get_all_hosts(managed_only=self.managed_only)

        self.job.logger.info("Loading %d hosts from Zabbix (managed_only=%s).", len(hosts), self.managed_only)

        for host_data in hosts:
            hostname = host_data["host"]

            # Extract primary IP from interfaces
            primary_iface = next(
                (i for i in host_data.get("interfaces", []) if str(i.get("main")) == "1"),
                None,
            )
            ip_address = primary_iface["ip"] if primary_iface else None

            # Extract group name (first group)
            groups = host_data.get("groups", [])
            hostgroup = groups[0]["name"] if groups else "Nautobot-Managed"

            # Extract template name (first linked template)
            templates = host_data.get("parentTemplates", [])
            template = templates[0]["name"] if templates else None

            # Extract nautobot_id tag if present
            tags = host_data.get("tags", [])

            zabbix_host = ZabbixHost(
                name=hostname,
                visible_name=host_data.get("name", hostname),
                ip_address=ip_address,
                hostgroup=hostgroup,
                template=template,
                enabled=(str(host_data.get("status", "0")) == "0"),
                description=host_data.get("description", ""),
                zabbix_id=host_data["hostid"],
            )

            try:
                self.add(zabbix_host)
            except Exception as exc:  # noqa: BLE001
                self.job.logger.warning("Could not load Zabbix host '%s': %s", hostname, exc)


class ZabbixNautobotAdapter(NautobotAdapter):
    """DiffSync adapter that loads data from the Nautobot ORM.

    Represents the desired state of monitoring as defined in Nautobot.
    Used as the *source* adapter in a Nautobot → Zabbix sync, and as
    the *target* adapter in a Zabbix → Nautobot sync.
    """

    host = ZabbixHost
    top_level = ["host"]

    def __init__(self, *args, job=None, sync=None, **kwargs):
        """Initialize the Nautobot adapter.

        Args:
            job: The running SSoT Job instance
            sync: The SSoT Sync model instance
        """
        super().__init__(*args, job=job, sync=sync, **kwargs)

    def load(self):
        """Load active Nautobot devices into DiffSync models.

        Skips devices that:
        - Have no primary IP (can't be monitored)
        - Are not in an active/staged status
        """
        from nautobot.dcim.models import Device

        active_statuses = {"Active", "Staged"}

        qs = (
            Device.objects.filter(status__name__in=active_statuses)
            .select_related(
                "location",
                "role",
                "device_type",
                "tenant",
                "platform",
                "primary_ip4",
                "primary_ip6",
                "status",
            )
        )

        self.job.logger.info("Loading %d active Nautobot devices.", qs.count())

        for device in qs:
            ip = get_primary_ip(device)
            if not ip:
                self.job.logger.debug(
                    "Skipping '%s' — no primary IP assigned.", device.name
                )
                continue

            nautobot_host = ZabbixHost(
                name=device.name,
                visible_name=str(device),
                ip_address=ip,
                hostgroup=resolve_hostgroup_name(device),
                template=resolve_template_name(device),
                enabled=True,
                description=(
                    f"Managed by Nautobot | ID: {device.pk} | "
                    f"Location: {device.location} | Role: {device.role} | "
                    f"Type: {device.device_type}"
                ),
            )

            try:
                self.add(nautobot_host)
            except Exception as exc:  # noqa: BLE001
                self.job.logger.warning(
                    "Could not load Nautobot device '%s': %s", device.name, exc
                )
