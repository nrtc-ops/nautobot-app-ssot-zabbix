"""Unit tests for CustomOrderingDiff."""

from diffsync.enum import DiffSyncActions

from nautobot_ssot_zabbix.diff import CustomOrderingDiff


class TestCustomOrderingDiff:
    """Verify that deletions are deferred to run last."""

    def test_creates_before_deletes(self):
        diff = CustomOrderingDiff()

        create_child = type("Child", (), {"action": DiffSyncActions.CREATE, "keys": {}})()
        delete_child = type("Child", (), {"action": DiffSyncActions.DELETE, "keys": {}})()

        diff.children = {
            "host": {
                "router-new": create_child,
                "router-old": delete_child,
            }
        }

        children = list(diff.get_children())
        # CREATE should come before DELETE
        actions = [c.action for c in children]
        assert actions.index(DiffSyncActions.CREATE) < actions.index(DiffSyncActions.DELETE)
