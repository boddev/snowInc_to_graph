# snowInc_to_graph

Converts ServiceNow (SNOW) Incident JSON payloads into a standardized Schema Object and an ExternalItem suitable for graph ingestion, search indexing, or downstream processing.

--  

## Table of contents
- [Overview](#overview)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quickstart](#quickstart)
  - [CLI usage (example)](#cli-usage-example)
  - [Library usage (example)](#library-usage-example)
- [Input format (ServiceNow Incident example)](#input-format-servicenow-incident-example)
- [Output formats](#output-formats)
  - [Schema Object example](#schema-object-example)
  - [ExternalItem example](#externalitem-example)
- [Field mapping](#field-mapping)
- [Configuration](#configuration)
- [Testing](#testing)
- [Development & Contributing](#development--contributing)
- [Troubleshooting](#troubleshooting)
- [Roadmap / Next steps](#roadmap--next-steps)
- [License](#license)
- [Contact](#contact)

## Overview
snowInc_to_graph is a small Python utility and library that:
- Accepts ServiceNow Incident JSON (for example from an export or webhook),
- Normalizes and maps the incident data into an internal "Schema Object" consistent across records,
- Produces an "ExternalItem" wrapper that is ready for ingestion into a graph database, search index, or any system expecting an ExternalItem envelope.

This repository is intended to be used either as:
- a CLI tool for batch conversion of JSON files, or
- a library module that can be imported by other Python services (ETL pipelines, ingestion lambdas, etc.).

## Features
- Deterministic mapping of common SNOW incident fields to a unified schema
- Support for custom mapping configuration (JSON/YAML)
- Output as JSON files (one-to-one conversion) or JSONL for streaming ingestion
- Small, dependency-light implementation so it can be used inside serverless functions

## Requirements
- Python 3.8+
- (Optional) virtualenv or venv for isolation

If the repository contains a `requirements.txt` or `pyproject.toml`, install dependencies from there. (Add those files if missing.)

## Installation
Clone the repository and create a virtual environment:

```bash
git clone https://github.com/boddev/snowInc_to_graph.git
cd snowInc_to_graph
python -m venv .venv
source .venv/bin/activate   # macOS / Linux
.venv\Scripts\activate      # Windows PowerShell
pip install -r requirements.txt   # if present
```

Or install locally for development (if package metadata exists):

```bash
pip install -e .
```

## Quickstart

### CLI usage (example)
(This is a canonical example — adapt commands to actual CLI script names in the repo.)

Convert a single ServiceNow incident file to Schema Object + ExternalItem:

```bash
python -m snowinc_to_graph.cli \
  --input examples/incident_123.json \
  --output examples/out/incident_123-converted.json
```

Batch convert multiple files (JSONL output for ingestion):

```bash
python -m snowinc_to_graph.cli \
  --input-dir examples/raw_incidents/ \
  --output-file examples/out/incidents.jsonl \
  --format jsonl
```

Options (example):
- `--input` - path to input JSON file
- `--input-dir` - directory of JSON files to convert
- `--output` / `--output-file` - path to write converted JSON or JSONL
- `--mapping` - optional custom mapping JSON/YAML
- `--pretty` - pretty-print output JSON

> Note: If a different CLI entrypoint or script name exists in the repo (e.g., `convert.py` or `main.py`), use that instead.

### Library usage (example)
Import and call the conversion function from other Python code:

```python
from snowinc_to_graph.converter import convert_incident, convert_incident_to_externalitem

# load raw ServiceNow incident JSON (dict)
with open("examples/incident_123.json") as f:
    raw = json.load(f)

schema_obj = convert_incident(raw)                # returns normalized schema dict
external_item = convert_incident_to_externalitem(schema_obj, source="servicenow")

# write external_item to disk or send to ingestion
with open("examples/out/incident_123-converted.json", "w") as f:
    json.dump(external_item, f, indent=2)
```

If your codebase uses asynchronous pipelines or message queues, wrapping this call inside a worker is straightforward because the converter is synchronous and pure.

## Input format (ServiceNow Incident example)
The converter expects a JSON object that represents a SNOW Incident record or an array of such records. Below is a simplified example of a SNOW incident JSON:

```json
{
  "sys_id": "c1b2c3d4e5f6",
  "number": "INC0001234",
  "short_description": "User cannot access VPN",
  "description": "The user reports VPN connection failing with error code 123.",
  "caller_id": {
    "value": "6816f79cc0a8016401c5a33be04be441",
    "display_value": "Jane Doe"
  },
  "opened_at": "2025-08-20 12:34:56",
  "closed_at": null,
  "priority": "2 - High",
  "state": "In Progress",
  "assigned_to": {
    "value": "6789abcd",
    "display_value": "IT Support"
  },
  "category": "Network",
  "u_custom_field": "example"
}
```

The converter will accept both nested field structures (display_value + value) and flat fields.

## Output formats

### Schema Object example
The "Schema Object" is a normalized dict that the code uses internally. This ensures consistent field names and types.

Example output:

```json
{
  "id": "c1b2c3d4e5f6",                 // mapped from sys_id
  "source_id": "INC0001234",           // mapped from number
  "title": "User cannot access VPN",   // mapped from short_description
  "description": "The user reports VPN connection failing with error code 123.",
  "reporter": {
    "id": "6816f79cc0a8016401c5a33be04be441",
    "name": "Jane Doe"
  },
  "assignee": {
    "id": "6789abcd",
    "name": "IT Support"
  },
  "priority": "2 - High",
  "status": "In Progress",
  "category": "Network",
  "created_at": "2025-08-20T12:34:56Z",
  "closed_at": null,
  "raw": { /* original SNOW payload preserved (optional) */ }
}
```

Notes:
- Timestamps are normalized to ISO 8601 where possible.
- Unmapped/unknown fields can be preserved under `raw` or dropped depending on configuration.

### ExternalItem example
An ExternalItem is an envelope commonly used for ingestion into downstream systems. Adjust fields to your target's expected schema (e.g., graph nodes, search documents).

Example:

```json
{
  "external_id": "c1b2c3d4e5f6",
  "source": "servicenow",
  "type": "incident",
  "title": "User cannot access VPN",
  "content": "The user reports VPN connection failing with error code 123.",
  "properties": {
    "number": "INC0001234",
    "priority": "2 - High",
    "status": "In Progress",
    "category": "Network",
    "reporter_name": "Jane Doe",
    "assignee_name": "IT Support"
  },
  "created_at": "2025-08-20T12:34:56Z",
  "raw": { /* optional original payload */ }
}
```

Adjust the ExternalItem shape to the destination system (graph DB may want nodes + relationship definitions; search index may want flat document fields).

## Field mapping
A recommended default mapping (ServiceNow -> Schema Object):

- sys_id -> id
- number -> source_id
- short_description -> title
- description -> description
- caller_id.value / caller_id.display_value -> reporter.id / reporter.name
- assigned_to.value / assigned_to.display_value -> assignee.id / assignee.name
- opened_at -> created_at (ISO 8601 normalized)
- closed_at -> closed_at (ISO 8601 normalized)
- priority -> priority
- state -> status
- category -> category
- other fields -> preserved under `raw` or mapped via custom mapping

If your repo supports a mapping file (JSON/YAML), you can provide overrides like:

```json
{
  "mappings": {
    "sys_id": "id",
    "number": "source_id",
    "u_ticket_owner": "properties.ticket_owner"
  }
}
```

## Configuration
- mapping file path (optional): use a JSON or YAML file to override the default mappings.
- timestamp normalization: enable/disable ISO 8601 normalization
- preserve_raw: boolean to copy the original SNOW payload into `raw`

Example CLI flag examples (conceptual):
- `--mapping mapping/custom_map.json`
- `--preserve-raw`
- `--timestamp-utc`

## Testing
If tests are included (e.g., pytest), run:

```bash
pip install -r requirements-dev.txt  # if present
pytest -q
```

Add tests for:
- typical incident conversions
- missing optional fields
- nested field extraction (display_value/value)
- timestamp normalization

## Development & Contributing
Contributions are welcome. Suggested workflow:
1. Fork the repository
2. Create a feature branch: `git checkout -b feat/mapping-config`
3. Implement your changes, add tests
4. Run tests locally
5. Open a pull request with a clear description of the change

Guidelines:
- Follow PEP8 / black formatting
- Write unit tests for any behavior changes
- Update README examples if you add or change CLI flags or public API

## Troubleshooting
- "Dates not parsing": Ensure the input SNOW `opened_at`/`closed_at` are in a recognized format; enable custom parsing or provide a mapping that does not attempt conversion.
- "Missing nested fields": Some SNOW returns compact fields; the converter tries display_value then value then flat key. Extend the mapper for vendor-specific responses.
- "Encoding errors": Ensure input JSON is UTF-8 encoded.

## Roadmap / Next steps
- Add CI (GitHub Actions) to run tests and linting
- Add packaging metadata (pyproject.toml / setup.cfg) for pip installation
- Add streaming mode to convert records from STDIN and emit JSONL to STDOUT
- Add a Dockerfile for containerized conversion jobs
- Add type hints and mypy checks

## License
This repository does not currently include a license. Add a LICENSE file (e.g., MIT) if you plan to make this project open source.

Suggested license header to add to repository:
```
MIT License
Copyright (c) 2025 <Your Name>
```

## Contact
Repository owner: @boddev
- GitHub: https://github.com/boddev

If you want, I can:
- create this README.md in the repository,
- add a basic CLI skeleton or an example converter implementation,
- add a mapping/config example (JSON/YAML),
- create a LICENSE file (MIT) and basic GitHub Actions workflow.

Tell me which of those you'd like me to do next and I will proceed.
