"""Jobs for Zabbix SSoT integration."""

from django.conf import settings
from nautobot.apps.jobs import BooleanVar, register_jobs
from nautobot_ssot.jobs.base import DataMapping, DataSource, DataTarget

from nautobot_ssot_zabbix.diff import CustomOrderingDiff
from nautobot_ssot_zabbix.diffsync.adapters import ZabbixNautobotAdapter, ZabbixRemoteAdapter

name = "Zabbix SSoT"  # pylint: disable=invalid-name


class ZabbixDataSource(DataSource):
    """Sync data FROM Zabbix INTO Nautobot.

    Pulls the current Zabbix host inventory (source=nautobot tagged hosts)
    and reconciles it with what Nautobot expects. Useful for auditing drift
    or recovering Nautobot state after an out-of-band Zabbix change.
    """

    debug = BooleanVar(description="Enable verbose debug logging.", default=False)

    class Meta:  # pylint: disable=too-few-public-methods
        """SSoT Job metadata for Zabbix DataSource."""

        name = "Zabbix to Nautobot"
        data_source = "Zabbix"
        data_target = "Nautobot"
        description = "Sync Zabbix host inventory into Nautobot. Useful for auditing drift between the two systems."

    @classmethod
    def config_information(cls):
        """Return user-facing configuration information shown in the SSoT dashboard."""
        cfg = settings.PLUGINS_CONFIG.get("nautobot_ssot_zabbix", {})
        return {
            "Zabbix URL": cfg.get("zabbix_url", "(not configured)"),
            "SSL Verify": cfg.get("ssl_verify", True),
            "Default Host Group": cfg.get("default_location_hostgroup_prefix", "Location-") + "*",
            "Default Template": cfg.get("default_template", "(none)"),
        }

    @classmethod
    def data_mappings(cls):
        """Describe the data mappings for the SSoT dashboard."""
        return (DataMapping("Zabbix Host", None, "Nautobot Device", None),)

    def load_source_adapter(self):
        """Load hosts from Zabbix into DiffSync models."""
        self.source_adapter = ZabbixRemoteAdapter(job=self, sync=self.sync)
        self.source_adapter.load()

    def load_target_adapter(self):
        """Load devices from Nautobot into DiffSync models."""
        self.target_adapter = ZabbixNautobotAdapter(job=self, sync=self.sync)
        self.target_adapter.load()

    def run(self, dryrun, memory_profiling, debug, *args, **kwargs):  # pylint: disable=arguments-differ
        """Perform Zabbix -> Nautobot synchronization."""
        self.debug = debug
        self.dryrun = dryrun
        self.memory_profiling = memory_profiling
        super().run(dryrun=self.dryrun, memory_profiling=self.memory_profiling, *args, **kwargs)


class ZabbixDataTarget(DataTarget):
    """Sync data FROM Nautobot INTO Zabbix.

    This is the primary operational job for NRTC. When devices are added or
    updated in Nautobot (via the nautobot-app-autobot or manually), running
    this job will create or update the corresponding hosts in Zabbix.

    Idempotent: safe to run repeatedly. Only changes what has drifted.
    """

    debug = BooleanVar(description="Enable verbose debug logging.", default=False)

    class Meta:  # pylint: disable=too-few-public-methods
        """SSoT Job metadata for Zabbix DataTarget."""

        name = "Nautobot to Zabbix"
        data_source = "Nautobot"
        data_target = "Zabbix"
        description = (
            "Sync Nautobot device inventory into Zabbix as monitored hosts. "
            "Creates, updates, or removes hosts based on the current Nautobot state. "
            "Only manages hosts tagged source=nautobot."
        )

    @classmethod
    def config_information(cls):
        """Return user-facing configuration information shown in the SSoT dashboard."""
        cfg = settings.PLUGINS_CONFIG.get("nautobot_ssot_zabbix", {})
        return {
            "Zabbix URL": cfg.get("zabbix_url", "(not configured)"),
            "SSL Verify": cfg.get("ssl_verify", True),
            "Default Host Group Prefix": cfg.get("default_location_hostgroup_prefix", "Location-"),
            "Default Template": cfg.get("default_template", "(none)"),
            "Role->Template Map": str(cfg.get("device_role_template_map", {})),
            "Location->Group Map": str(cfg.get("location_hostgroup_map", {})),
        }

    @classmethod
    def data_mappings(cls):
        """Describe the data mappings for the SSoT dashboard."""
        return (DataMapping("Nautobot Device", None, "Zabbix Host", None),)

    def load_source_adapter(self):
        """Load devices from Nautobot into DiffSync models."""
        self.source_adapter = ZabbixNautobotAdapter(job=self, sync=self.sync)
        self.source_adapter.load()

    def load_target_adapter(self):
        """Load hosts from Zabbix into DiffSync models.

        Uses managed_only=True so deletions are scoped to hosts we created
        (tagged source=nautobot). Unmanaged Zabbix hosts are left alone.
        """
        self.target_adapter = ZabbixRemoteAdapter(job=self, sync=self.sync, managed_only=True)
        self.target_adapter.load()

    def run(self, dryrun, memory_profiling, debug, *args, **kwargs):  # pylint: disable=arguments-differ
        """Perform Nautobot -> Zabbix synchronization."""
        self.debug = debug
        self.dryrun = dryrun
        self.memory_profiling = memory_profiling
        super().run(dryrun=self.dryrun, memory_profiling=self.memory_profiling, *args, **kwargs)

    def execute_sync(self):
        """Synchronize using CustomOrderingDiff to defer deletions until last."""
        if self.source_adapter is not None and self.target_adapter is not None:
            self.source_adapter.sync_to(
                self.target_adapter,
                flags=self.diffsync_flags,
                diff_class=CustomOrderingDiff,
            )
        else:
            self.logger.warning("One of the adapters was not properly initialized prior to synchronization.")


jobs = [ZabbixDataSource, ZabbixDataTarget]
register_jobs(*jobs)
