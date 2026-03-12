# Nautobot SSoT Zabbix

> **⚠️ Alpha Software**: This project is currently in **alpha** and is under active development. APIs, configuration options, and behavior may change between releases. Use in production environments is not recommended until a stable release is published.

An [SSoT](https://github.com/nautobot/nautobot-app-ssot) app for [Nautobot](https://github.com/nautobot/nautobot) that synchronizes device data between Nautobot and [Zabbix](https://www.zabbix.com/) monitoring.

<p align="center">
  <img src="https://raw.githubusercontent.com/nrtc-ops/nautobot-app-ssot-zabbix/main/docs/images/icon-nautobot-ssot-zabbix.png" class="logo" height="200px">
  <br>
  <a href="https://github.com/nrtc-ops/nautobot-app-ssot-zabbix/actions"><img src="https://github.com/nrtc-ops/nautobot-app-ssot-zabbix/actions/workflows/ci.yml/badge.svg?branch=main"></a>
  <a href="https://pypi.org/project/nautobot-ssot-zabbix/"><img src="https://img.shields.io/pypi/v/nautobot-ssot-zabbix"></a>
  <a href="https://pypi.org/project/nautobot-ssot-zabbix/"><img src="https://img.shields.io/pypi/dm/nautobot-ssot-zabbix"></a>
</p>

## Overview

This app extends the [Nautobot SSoT framework](https://github.com/nautobot/nautobot-app-ssot) to provide bidirectional synchronization between Nautobot devices and Zabbix monitored hosts. It uses the [DiffSync](https://github.com/nautobot/diffsync) library to detect and reconcile differences between the two systems.

### What Gets Synced

For each Nautobot device with an active or staged status and a primary IP, the app syncs:

- **Host name** and **visible name**
- **Primary IP address** for monitoring
- **Host group** (derived from device location, tenant, or configurable mappings)
- **Monitoring template** (derived from device role or a configurable default)
- **Enabled/disabled status**
- **Description** (populated with Nautobot device metadata)
- **Zabbix tags** preserving Nautobot context (source, location, role, device type, tenant, platform)

### Sync Directions

- **Nautobot to Zabbix** (`ZabbixDataTarget`) — Creates, updates, and deletes Zabbix hosts to match Nautobot device inventory. This is the primary sync direction.
- **Zabbix to Nautobot** (`ZabbixDataSource`) — Audits Zabbix hosts tagged with `source=nautobot` back against Nautobot to detect out-of-band drift.

Only Zabbix hosts tagged with `source=nautobot` are managed by this app, so manually created Zabbix hosts are never modified or deleted.

## Requirements

- Nautobot >= 3.0.0
- nautobot-ssot >= 4.0.0
- Python >= 3.10, < 3.13

## Documentation

Full documentation for this App can be found over on the [Nautobot Docs](https://docs.nautobot.com) website:

- [User Guide](https://docs.nautobot.com/projects/ssot-zabbix/en/latest/user/app_overview/) - Overview, Using the App, Getting Started.
- [Administrator Guide](https://docs.nautobot.com/projects/ssot-zabbix/en/latest/admin/install/) - How to Install, Configure, Upgrade, or Uninstall the App.
- [Developer Guide](https://docs.nautobot.com/projects/ssot-zabbix/en/latest/dev/contributing/) - Extending the App, Code Reference, Contribution Guide.
- [Release Notes / Changelog](https://docs.nautobot.com/projects/ssot-zabbix/en/latest/admin/release_notes/).

### Contributing to the Documentation

You can find all the Markdown source for the App documentation under the [`docs`](https://github.com/nrtc-ops/nautobot-app-ssot-zabbix/tree/main/docs) folder in this repository. For simple edits, a Markdown capable editor is sufficient: clone the repository and edit away.

If you need to view the fully-generated documentation site, you can build it with [MkDocs](https://www.mkdocs.org/). A container hosting the documentation can be started using the `invoke` commands (details in the [Development Environment Guide](https://docs.nautobot.com/projects/ssot-zabbix/en/latest/dev/dev_environment/#docker-development-environment)) on [http://localhost:8001](http://localhost:8001). As your changes are saved, they will be automatically rebuilt and any pages currently being viewed will be reloaded in your browser.

## Questions

For any questions or comments, please check the [FAQ](https://docs.nautobot.com/projects/ssot-zabbix/en/latest/user/faq/) first. Feel free to also swing by the [Network to Code Slack](https://networktocode.slack.com/) (channel `#nautobot`), sign up [here](http://slack.networktocode.com/) if you don't have an account.
