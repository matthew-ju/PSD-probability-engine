from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional
import yaml

class ConfigError(Exception):
    '''when the configuration from YAML is invalid'''

@dataclass(frozen=True)
class AnalysisConfig:
    base_dir: Path
    networks: List[str]
    stations: List[str]
    components: List[str]
    period_x: float
    period_y: float
    stat: str                        # e.g. "p99", "p50"
    out_dir: Path
    start_year: int
    end_year: int
    start_day: int
    end_day: int
    percentiles: List[float]
    labeled_stations: List[str]
    locations: List[str] = field(default_factory=lambda: ["00", "01"])

def _parse_list(raw_val: Any) -> List[str]:
    if isinstance(raw_val, list):
        return [str(s).strip() for s in raw_val if str(s).strip()]
    if isinstance(raw_val, str):
        return [s.strip() for s in raw_val.split(",") if s.strip()]
    return []

def load_config(path: Path) -> AnalysisConfig:
    if not path.exists():
        raise ConfigError(f"YAML file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"Error reading YAML file: {exc}") from exc

    # Basic defaults/fallback
    networks_raw = raw.get("networks", raw.get("network", ["BK", "NC"]))
    networks = _parse_list(networks_raw)
    
    stations = _parse_list(raw.get("stations", []))
    components = _parse_list(raw.get("components", ["HHZ", "HHN", "HHE", "HNZ", "HNN", "HNE", "EHZ", "EHN", "EHE"]))
    locations = _parse_list(raw.get("locations", ["00", "01"]))

    return AnalysisConfig(
        base_dir=Path(str(raw.get("base_dir", "/ref/dc14/PDF/STATS"))),
        networks=networks,
        stations=stations,
        components=components,
        locations=locations,
        period_x=float(raw.get("period_x", 50.0)),
        period_y=float(raw.get("period_y", 1.0)),
        stat=str(raw.get("stat", "p50")),
        out_dir=Path(str(raw.get("out_dir", "."))),
        start_year=int(raw.get("start_year", 2024)),
        end_year=int(raw.get("end_year", 2025)),
        start_day=int(raw.get("start_day", 1)),
        end_day=int(raw.get("end_day", 366)),
        percentiles=raw.get("percentiles", [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99, 1.0]),
        labeled_stations=_parse_list(raw.get("labeled_stations", [])),
    )
