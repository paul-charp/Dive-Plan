"""JSON report formatter — machine-readable dive plan document."""

import json

from diveplan.dive.dive_report import DiveReport
from diveplan.dive.formatters import BaseFormatter

__all__ = ["JsonFormatter"]


class JsonFormatter(BaseFormatter):
    """Serialize the whole report to a JSON document.

    Depths in metres, durations in seconds, gases by name with exact
    fractions alongside.
    """

    NAME = "json"

    def __init__(self, *, indent: int | None = 2):
        self.indent = indent

    def format(self, report: DiveReport) -> str:
        """Render the report as a JSON document string."""
        variations = None
        if report.tts_variations is not None:
            variations = {
                "per_meter_s": report.tts_variations.per_meter.total_seconds(),
                "per_minute_s": report.tts_variations.per_minute.total_seconds(),
            }

        document = {
            "model": report.model_name,
            "runtime_s": report.runtime.total_seconds(),
            "max_depth_m": round(report.max_depth.depth_m, 2),
            "segments": [
                {
                    "runtime_s": row.runtime.total_seconds(),
                    "start_depth_m": round(row.start_depth_m, 2),
                    "end_depth_m": round(row.end_depth_m, 2),
                    "duration_s": row.duration.total_seconds(),
                    "gas": {
                        "name": row.gas.name,
                        "fo2": row.gas.fo2,
                        "fhe": row.gas.fhe,
                    },
                    "kind": row.kind,
                }
                for row in report.rows
            ],
            "consumption_l": {
                gas.name: round(litres, 1) for gas, litres in report.consumption_l
            },
            "sac": {
                "bottom_l_min": report.sac_bottom,
                "deco_l_min": report.sac_deco,
                "rock_bottom_factor": report.sac_factor,
            },
            "rock_bottom_l": round(report.rock_bottom_l, 1),
            "cns_percent": round(report.cns, 1),
            "otu": round(report.otus, 1),
            "tts_variations": variations,
        }
        return json.dumps(document, indent=self.indent)
