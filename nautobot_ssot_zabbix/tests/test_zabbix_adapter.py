"""Unit tests for ZabbixRemoteAdapter and ZabbixNautobotAdapter."""

from unittest.mock import MagicMock, patch


class TestZabbixRemoteAdapterLoad:
    """Tests for ZabbixRemoteAdapter.load()."""

    def _make_adapter(self):
        from nautobot_ssot_zabbix.diffsync.adapters import ZabbixRemoteAdapter

        job = MagicMock()
        job.logger = MagicMock()
        return ZabbixRemoteAdapter(job=job, sync=None)

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
        mock_client.get_all_nautobot_hosts.return_value = self._host_fixture()
        mock_get_client.return_value = mock_client

        adapter = self._make_adapter()
        adapter.load()

        host = adapter.get("host", "router-athens-01")
        assert host is not None
        assert host.ip_address == "10.0.1.1"
        assert host.hostgroup == "Location-Athens"
        assert host.template == "Template Net Cisco IOS-XE"
        assert host.enabled is True

    @patch("nautobot_ssot_zabbix.diffsync.adapters.get_zabbix_client_from_config")
    def test_load_empty_zabbix(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get_all_nautobot_hosts.return_value = []
        mock_get_client.return_value = mock_client

        adapter = self._make_adapter()
        adapter.load()

        assert list(adapter.get_all("host")) == []


class TestZabbixHostModel:
    """Tests for ZabbixHost DiffSync model create/update/delete."""

    @patch("nautobot_ssot_zabbix.diffsync.models.get_zabbix_client_from_config")
    def test_create_calls_upsert(self, mock_get_client):
        from nautobot_ssot_zabbix.diffsync.models import ZabbixHost

        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get_or_create_hostgroup.return_value = "42"
        mock_client.get_template_id.return_value = "500"
        mock_client.upsert_host.return_value = {"action": "created", "hostid": "1001"}
        mock_get_client.return_value = mock_client

        adapter = MagicMock()
        adapter.job.logger = MagicMock()
        adapter.type.host = ZabbixHost

        host = ZabbixHost(name="test-router-01")
        host.create(
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

        mock_client.upsert_host.assert_called_once()
        call_kwargs = mock_client.upsert_host.call_args[1]
        assert call_kwargs["hostname"] == "test-router-01"
        assert call_kwargs["ip"] == "10.0.0.1"

    @patch("nautobot_ssot_zabbix.diffsync.models.get_zabbix_client_from_config")
    def test_create_skips_no_ip(self, mock_get_client):
        from nautobot_ssot_zabbix.diffsync.models import ZabbixHost

        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_get_client.return_value = mock_client

        adapter = MagicMock()
        adapter.job.logger = MagicMock()
        adapter.type.host = ZabbixHost

        host = ZabbixHost(name="no-ip-device")
        host.create(
            adapter=adapter,
            ids={"name": "no-ip-device"},
            attrs={"ip_address": None, "hostgroup": "Nautobot-Managed"},
        )

        mock_client.upsert_host.assert_not_called()

    @patch("nautobot_ssot_zabbix.diffsync.models.get_zabbix_client_from_config")
    def test_delete_calls_delete_host(self, mock_get_client):
        from nautobot_ssot_zabbix.diffsync.models import ZabbixHost

        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.delete_host.return_value = {"action": "deleted", "hostid": "1001"}
        mock_get_client.return_value = mock_client

        host = ZabbixHost(name="old-router", zabbix_id="1001")
        # Mock the parent delete to avoid DiffSync state errors
        with patch("diffsync.DiffSyncModel.delete", return_value=host):
            host.delete()

        mock_client.delete_host.assert_called_once_with(hostname="old-router")
