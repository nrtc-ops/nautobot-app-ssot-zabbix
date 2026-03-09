"""Utility functions and client for working with the Zabbix API."""

import logging
from typing import Optional

from zabbix_utils import APIRequestError, ZabbixAPI

logger = logging.getLogger("nautobot.jobs")


class ZabbixClientError(Exception):
    """Raised when a Zabbix API operation fails."""


class ZabbixClient:
    """Thin wrapper around zabbix_utils.ZabbixAPI.

    Provides:
    - Token-based authentication (Zabbix >= 5.4)
    - Host group get-or-create
    - Template name -> ID resolution
    - Idempotent host upsert (get -> create or update)
    - Interface reconciliation on update
    - Bulk host listing for DiffSync load
    """

    INTERFACE_TYPE_AGENT = 1
    INTERFACE_TYPE_SNMP = 2
    INTERFACE_TYPE_IPMI = 3
    INTERFACE_TYPE_JMX = 4
    SNMP_V1 = 1
    SNMP_V2 = 2
    SNMP_V3 = 3

    def __init__(self, url: str, token: str, ssl_verify: bool = True):
        """Initialize the Zabbix API client."""
        self._url = url.rstrip("/")
        self._token = token
        self._ssl_verify = ssl_verify
        self._api: Optional[ZabbixAPI] = None

    def connect(self) -> None:
        """Establish an authenticated session with the Zabbix API."""
        try:
            self._api = ZabbixAPI(url=self._url, validate_certs=self._ssl_verify)
            self._api.login(token=self._token)
            logger.debug("Connected to Zabbix API at %s (version %s)", self._url, self._api.api_version())
        except APIRequestError as exc:
            raise ZabbixClientError(f"Failed to authenticate with Zabbix at {self._url}: {exc}") from exc

    def disconnect(self) -> None:
        """Log out and close the Zabbix API session."""
        if self._api:
            try:
                self._api.logout()
            except APIRequestError:
                pass
            self._api = None

    def __enter__(self):
        """Connect on context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Disconnect on context manager exit."""
        self.disconnect()

    @property
    def api(self) -> ZabbixAPI:
        """Return the active ZabbixAPI instance, raising if not connected."""
        if self._api is None:
            raise ZabbixClientError("ZabbixClient is not connected. Use connect() or a context manager.")
        return self._api

    def get_or_create_hostgroup(self, name: str) -> str:
        """Return groupid for named host group, creating it if absent."""
        results = self.api.hostgroup.get(filter={"name": name}, output=["groupid", "name"])
        if results:
            return results[0]["groupid"]
        created = self.api.hostgroup.create(name=name)
        groupid = created["groupids"][0]
        logger.info("Created Zabbix host group '%s' (id=%s)", name, groupid)
        return groupid

    def get_template_id(self, name: str) -> Optional[str]:
        """Resolve a template name to its Zabbix templateid, or None."""
        results = self.api.template.get(filter={"name": name}, output=["templateid", "name"])
        if results:
            return results[0]["templateid"]
        logger.warning("Zabbix template '%s' not found — skipping template link", name)
        return None

    def get_host(self, hostname: str) -> Optional[dict]:
        """Look up a Zabbix host by technical hostname, or return None."""
        results = self.api.host.get(
            filter={"host": hostname},
            output=["hostid", "host", "name", "status"],
            selectInterfaces=["interfaceid", "type", "ip", "dns", "useip", "port", "main", "details"],
            selectGroups=["groupid"],
            selectParentTemplates=["templateid"],
            selectTags=["tag", "value"],
        )
        return results[0] if results else None

    def build_interface(
        self,
        ip: str,
        dns: str = "",
        interface_type: int = INTERFACE_TYPE_AGENT,
        port: str = "10050",
        use_ip: bool = True,
        snmp_version: int = SNMP_V2,
        snmp_community: str = "public",
    ) -> dict:
        """Build a Zabbix interface dict for host create/update."""
        interface = {
            "type": interface_type,
            "main": 1,
            "useip": 1 if use_ip else 0,
            "ip": ip,
            "dns": dns,
            "port": port,
        }
        if interface_type == self.INTERFACE_TYPE_SNMP:
            interface["port"] = "161"
            interface["details"] = {"version": snmp_version, "bulk": 1}
            if snmp_version in (self.SNMP_V1, self.SNMP_V2):
                interface["details"]["community"] = snmp_community
        return interface

    def upsert_host(
        self,
        hostname: str,
        visible_name: str,
        ip: str,
        groupids: list,
        templateids: Optional[list] = None,
        interfaces: Optional[list] = None,
        macros: Optional[list] = None,
        tags: Optional[list] = None,
        description: str = "",
        enabled: bool = True,
    ) -> dict:
        """Idempotent host upsert: create if absent, update if present.

        Always does host.get first to avoid duplicates. Called from
        ZabbixRemoteAdapter DiffSync create/update model methods.

        Returns:
            Dict with keys 'action' ("created" or "updated") and 'hostid'
        """
        if not interfaces:
            interfaces = [self.build_interface(ip=ip)]
        if not tags:
            tags = []
        if not any(t.get("tag") == "source" for t in tags):
            tags.append({"tag": "source", "value": "nautobot"})

        host_params = {
            "host": hostname,
            "name": visible_name,
            "description": description,
            "status": 0 if enabled else 1,
            "groups": [{"groupid": gid} for gid in groupids],
            "tags": tags,
        }
        if templateids:
            host_params["templates"] = [{"templateid": tid} for tid in templateids]
        if macros:
            host_params["macros"] = macros

        existing = self.get_host(hostname)

        if existing is None:
            host_params["interfaces"] = interfaces
            try:
                result = self.api.host.create(**host_params)
                hostid = result["hostids"][0]
                logger.info("Created Zabbix host '%s' (id=%s)", hostname, hostid)
                return {"action": "created", "hostid": hostid}
            except APIRequestError as exc:
                raise ZabbixClientError(f"Failed to create Zabbix host '{hostname}': {exc}") from exc
        else:
            hostid = existing["hostid"]
            host_params["hostid"] = hostid
            try:
                self._reconcile_primary_interface(hostid, existing.get("interfaces", []), interfaces)
                self.api.host.update(**host_params)
                logger.info("Updated Zabbix host '%s' (id=%s)", hostname, hostid)
                return {"action": "updated", "hostid": hostid}
            except APIRequestError as exc:
                raise ZabbixClientError(
                    f"Failed to update Zabbix host '{hostname}' (id={hostid}): {exc}"
                ) from exc

    def _reconcile_primary_interface(
        self, hostid: str, existing_interfaces: list, desired_interfaces: list
    ) -> None:
        """Update the primary interface IP if it has changed."""
        if not existing_interfaces or not desired_interfaces:
            return
        primary_existing = next((i for i in existing_interfaces if str(i.get("main")) == "1"), None)
        primary_desired = desired_interfaces[0]
        if primary_existing and primary_existing.get("ip") != primary_desired.get("ip"):
            self.api.hostinterface.update(
                interfaceid=primary_existing["interfaceid"],
                ip=primary_desired["ip"],
                dns=primary_desired.get("dns", ""),
                useip=primary_desired.get("useip", 1),
                port=primary_desired.get("port", "10050"),
            )
            logger.debug(
                "Updated primary interface for hostid=%s: %s -> %s",
                hostid,
                primary_existing.get("ip"),
                primary_desired.get("ip"),
            )

    def delete_host(self, hostname: str) -> dict:
        """Delete a host from Zabbix by hostname."""
        existing = self.get_host(hostname)
        if not existing:
            return {"action": "not_found", "hostid": None}
        hostid = existing["hostid"]
        try:
            self.api.host.delete(hostid)
            logger.info("Deleted Zabbix host '%s' (id=%s)", hostname, hostid)
            return {"action": "deleted", "hostid": hostid}
        except APIRequestError as exc:
            raise ZabbixClientError(
                f"Failed to delete Zabbix host '{hostname}' (id={hostid}): {exc}"
            ) from exc

    def get_all_nautobot_hosts(self) -> list:
        """Return all Zabbix hosts that were created/managed by Nautobot.

        Filters by tag source=nautobot so we only touch what we own.
        """
        return self.api.host.get(
            output=["hostid", "host", "name", "status", "description"],
            selectInterfaces=["interfaceid", "type", "ip", "dns", "useip", "port", "main"],
            selectGroups=["groupid", "name"],
            selectParentTemplates=["templateid", "name"],
            selectTags=["tag", "value"],
            tags=[{"tag": "source", "value": "nautobot", "operator": 0}],
        )


def get_zabbix_client_from_config() -> ZabbixClient:
    """Instantiate a ZabbixClient from PLUGINS_CONFIG settings.

    Returns:
        ZabbixClient (not yet connected — use as context manager or call connect())

    Raises:
        ZabbixClientError: If required config keys are missing
    """
    from django.conf import settings

    cfg = settings.PLUGINS_CONFIG.get("nautobot_ssot_zabbix", {})
    url = cfg.get("zabbix_url")
    token = cfg.get("zabbix_token")

    if not url or not token:
        raise ZabbixClientError(
            "nautobot_ssot_zabbix requires 'zabbix_url' and 'zabbix_token' in PLUGINS_CONFIG."
        )

    return ZabbixClient(url=url, token=token, ssl_verify=cfg.get("ssl_verify", True))
