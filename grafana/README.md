# ADP Observability — Grafana + Prometheus

Pre-configured observability stack for the ADP demo runner.

## Option A: Homebrew (macOS, no Docker required)

```bash
brew install grafana prometheus
```

Start Prometheus and Grafana (run from the `adp_paths/` project root):

```bash
prometheus --config.file=grafana/prometheus.yml &
brew services start grafana
```

Open [http://localhost:3000](http://localhost:3000) — login `admin` / `admin`.

Then add the data source and import the dashboard:

1. Go to **Connections → Data sources → Add data source**
2. Select **Prometheus**, set URL to `http://localhost:9090`, click **Save & test**
3. Go to **Dashboards → Import**, upload `grafana/dashboards/adp-dashboard.json`

To stop:

```bash
brew services stop grafana
# Kill the Prometheus process (or use Ctrl-C if running in foreground)
pkill prometheus
```

## Option B: Docker Compose

Requires Docker Desktop (or Docker Engine) to be running.

```bash
cd grafana
docker compose up -d
```

Open [http://localhost:3000](http://localhost:3000) — login `admin` / `admin`.

The data source and dashboard are auto-provisioned. No manual setup needed.

To stop:

```bash
docker compose down
```

Add `-v` to also remove stored data:

```bash
docker compose down -v
```

## Dashboard

The **ADP Platform Observability** dashboard has three sections:

| Section | Metrics |
|---------|---------|
| **L01 Pipeline Telemetry** | Pipeline runs (pass/fail), stage runs by name, dispatch cycle duration |
| **L02 Dispatch Work** | Work items assigned by type/agent, escalations, queue depth |
| **L03 GOVERNANCE Events** | Governance events by action/path, governance denials |

## Exporting Telemetry

Run the demo with `--export-telemetry` to produce files Prometheus can scrape:

```bash
python -m src.cli --simulate --export-telemetry ./telemetry
```

This writes four files to `./telemetry/`:

- `traces.json` — OpenTelemetry-compatible spans
- `metrics.json` — All counters, gauges, histograms
- `logs.json` — Structured JSON log entries
- `prometheus.txt` — Prometheus text exposition format

## Architecture Mapping

```
L01 Tooling       → pipeline_runs, pipeline_stage_runs (counters)
L02 Path Defs     → dispatch_assignments, dispatch_escalations (counters)
                     dispatch_queue_size (gauge)
                     dispatch_cycle_duration_ms (histogram)
L03 GOVERNANCE    → governance_events (counter, by action + path)
                     dispatch_governance_denials (counter)
```
