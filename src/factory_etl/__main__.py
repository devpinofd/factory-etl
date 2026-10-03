"""Entry point: `python -m factory_etl`."""

from __future__ import annotations

import datetime
import json
import sys

print(
    json.dumps(
        {
            "event": "process_start",
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        }
    ),
    file=sys.stderr,
)

from factory_etl.cli import app  # noqa: E402

if __name__ == "__main__":
    app()
