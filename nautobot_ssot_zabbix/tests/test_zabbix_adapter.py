"""Unit tests for ZabbixRemoteAdapter and ZabbixHost CRUD methods."""

from unittest.mock import MagicMock, patch

from diffsync import Adapter

from nautobot_ssot_zabbix.diffsync.adapters import ZabbixRemoteAdapter
from nautobot_ssot_zabbix.diffsync.models import ZabbixHost


class TestZabbixRemoteAdapterLoad:
    """Tests for ZabbixRemoteAdapter.load()."""

    def _make_adapter(self, managed_only=False):
        job = MagicMock()
        job.logger = MagicMock()
        return ZabbixRemoteAdapter(job=job, sync=None, managed_only=managed_only)

    def _host_fixture(self):
        return [
            {
                "hostid": "1001",
                "host": "router-athens-01",
                "name": "Router Athens 01",
                "status": "0",
                "description": "Test router",
                "interfaces": [
                    {"interfaceid": "5", "type": "1", "ip": "10.0.1.1", "main": "1", "port": "10050"},
                ],
                "groups": [{"groupid": "42", "name": "Location-Athens"}],
                "parentTemplates": [{"templateid": "500", "name": "Template Net Cisco IOS-XE"}],
                "tags": [{"tag": "source", "value": "nautobot"}, {"tag": "nautobot_id", "value": "abc-123"}],
            }
        ]

    @patch("nautobot_ssot_zabbix.diffsync.adapters.get_zabbix_client_from_config")
    def test_load_creates_diffsync_objects(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get_all_hosts.return_value = self._host_fixture()
        mock_get_client.return_value = mock_client

        adapter = self._make_adapter()
        adapter.load()

        host = adapter.get("host", "router-athens-01")
        assert host is not None
        assert host.ip_address == "10.0.1.1"
        assert host.hostgroup == "Location-Athens"
        assert host.template == "Template Net Cisco IOS-XE"
        assert host.enabled is True
        assert host.zabbix_id == "1001"

    @patch("nautobot_ssot_zabbix.diffsync.adapters.get_zabbix_client_from_config")
    def test_load_empty_zabbix(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get_all_hosts.return_value = []
        mock_get_client.return_value = mock_client

        adapter = self._make_adapter()
        adapter.load()

        assert not any(adapter.get_all("host"))

    @patch("nautobot_ssot_zabbix.diffsync.adapters.get_zabbix_client_from_config")
    def test_load_managed_only_passes_flag(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get_all_hosts.return_value = []
        mock_get_client.return_value = mock_client

        adapter = self._make_adapter(managed_only=True)
        adapter.load()

        mock_client.get_all_hosts.assert_called_once_with(managed_only=True)

    @patch("nautobot_ssot_zabbix.diffsync.adapters.get_zabbix_client_from_config")
    def test_load_host_without_interface(self, mock_get_client):
        """Host with no interfaces should load with ip_address=None."""
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get_all_hosts.return_value = [
            {
                "hostid": "1002",
                "host": "no-iface-host",
                "name": "No Interface Host",
                "status": "0",
                "description": "",
                "interfaces": [],
                "groups": [{"groupid": "1", "name": "Nautobot-Managed"}],
                "parentTemplates": [],
                "tags": [],
            }
        ]
        mock_get_client.return_value = mock_client

        adapter = self._make_adapter()
        adapter.load()

        host = adapter.get("host", "no-iface-host")
        assert host.ip_address is None
        assert host.template is None


class TestZabbixHostModel:
    """Tests for ZabbixHost DiffSync model create/update/delete.

    CRUD methods only write to Zabbix when the target adapter is a
    ZabbixRemoteAdapter. We test both directions.
    """

    def _make_zabbix_adapter(self):
        """Create a mock that passes the _is_zabbix_target() check."""
        adapter = MagicMock(spec=ZabbixRemoteAdapter)
        adapter.job = MagicMock()
        adapter.job.logger = MagicMock()
        return adapter

    def _make_nautobot_adapter(self):
        """Create a mock that does NOT pass the _is_zabbix_target() check."""
        adapter = MagicMock(spec=Adapter)
        adapter.job = MagicMock()
        adapter.job.logger = MagicMock()
        return adapter

    # --- Nautobot -> Zabbix direction (writes to Zabbix) ---

    @patch("nautobot_ssot_zabbix.diffsync.models.get_zabbix_client_from_config")
    def test_create_calls_upsert_when_target_is_zabbix(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get_or_create_hostgroup.return_value = "42"
        mock_client.get_template_id.return_value = "500"
        mock_client.upsert_host.return_value = {"action": "created", "hostid": "1001"}
        mock_get_client.return_value = mock_client

        adapter = self._make_zabbix_adapter()

        result = ZabbixHost.create(
            adapter=adapter,
            ids={"name": "test-router-01"},
            attrs={
                "ip_address": "10.0.0.1",
                "hostgroup": "Location-Athens",
                "template": "Template Net Cisco IOS-XE",
                "visible_name": "Test Router 01",
                "enabled": True,
                "description": "Test",
            },
        )

        assert result is not None
        mock_client.upsert_host.assert_called_once()
        call_kwargs = mock_client.upsert_host.call_args[1]
        assert call_kwargs["hostname"] == "test-router-01"
        assert call_kwargs["ip"] == "10.0.0.1"

    @patch("nautobot_ssot_zabbix.diffsync.models.get_zabbix_client_from_config")
    def test_create_skips_no_ip(self, mock_get_client):
        adapter = self._make_zabbix_adapter()

        result = ZabbixHost.create(
            adapter=adapter,
            ids={"name": "no-ip-device"},
            attrs={
                "ip_address": None,
                "hostgroup": "Nautobot-Managed",
                "visible_name": "No IP",
                "enabled": True,
                "description": "",
                "template": None,
            },
        )

        assert result is None
        mock_get_client.assert_not_called()

    @patch("nautobot_ssot_zabbix.diffsync.models.get_zabbix_client_from_config")
    def test_update_calls_upsert_when_target_is_zabbix(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get_or_create_hostgroup.return_value = "42"
        mock_client.upsert_host.return_value = {"action": "updated", "hostid": "1001"}
        mock_get_client.return_value = mock_client

        host = ZabbixHost(name="test-router-01", ip_address="10.0.0.1", hostgroup="Location-Athens")
        host.adapter = self._make_zabbix_adapter()

        with patch("diffsync.DiffSyncModel.update", return_value=host):
            host.update({"ip_address": "10.0.0.2"})

        mock_client.upsert_host.assert_called_once()
        call_kwargs = mock_client.upsert_host.call_args[1]
        assert call_kwargs["ip"] == "10.0.0.2"

    @patch("nautobot_ssot_zabbix.diffsync.models.get_zabbix_client_from_config")
    def test_delete_calls_delete_host_when_target_is_zabbix(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.delete_host.return_value = {"action": "deleted", "hostid": "1001"}
        mock_get_client.return_value = mock_client

        host = ZabbixHost(name="old-router", zabbix_id="1001")
        host.adapter = self._make_zabbix_adapter()

        with patch("diffsync.DiffSyncModel.delete", return_value=host):
            host.delete()

        mock_client.delete_host.assert_called_once_with(hostname="old-router")

    # --- Zabbix -> Nautobot direction (should NOT write to Zabbix) ---

    @patch("nautobot_ssot_zabbix.diffsync.models.get_zabbix_client_from_config")
    def test_create_does_not_call_zabbix_when_target_is_nautobot(self, mock_get_client):
        adapter = self._make_nautobot_adapter()

        result = ZabbixHost.create(
            adapter=adapter,
            ids={"name": "zabbix-host-01"},
            attrs={
                "ip_address": "10.0.0.5",
                "hostgroup": "Location-Athens",
                "template": None,
                "visible_name": "Zabbix Host 01",
                "enabled": True,
                "description": "From Zabbix",
            },
        )

        assert result is not None
        mock_get_client.assert_not_called()
        adapter.job.logger.info.assert_called()

    @patch("nautobot_ssot_zabbix.diffsync.models.get_zabbix_client_from_config")
    def test_update_does_not_call_zabbix_when_target_is_nautobot(self, mock_get_client):
        host = ZabbixHost(name="zabbix-host-01", ip_address="10.0.0.5")
        host.adapter = self._make_nautobot_adapter()

        with patch("diffsync.DiffSyncModel.update", return_value=host):
            host.update({"ip_address": "10.0.0.6"})

        mock_get_client.assert_not_called()
        host.adapter.job.logger.info.assert_called()

    @patch("nautobot_ssot_zabbix.diffsync.models.get_zabbix_client_from_config")
    def test_delete_does_not_call_zabbix_when_target_is_nautobot(self, mock_get_client):
        host = ZabbixHost(name="zabbix-host-01")
        host.adapter = self._make_nautobot_adapter()

        with patch("diffsync.DiffSyncModel.delete", return_value=host):
            host.delete()

        mock_get_client.assert_not_called()
        host.adapter.job.logger.info.assert_called()
