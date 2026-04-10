from __future__ import annotations
import csv
from datetime import datetime
import numpy as np
from pathlib import Path
from typing import List, Optional, Dict

from ..common.models import PSDPoint, StationChannel
from ..common.config import AnalysisConfig

class CSVReader:
    '''Reads percentile CSV files produced by the probability engine.'''

    def __init__(self, cfg: AnalysisConfig):
        self.cfg = cfg
        self.stat_column = self._resolve_stat_column(cfg.stat)
        self._instrument_cache: Dict[str, str] = {}
        self._load_instruments()

    def _resolve_stat_column(self, stat: str) -> str:
        if stat.lower().startswith("p") and stat[1:].isdigit():
            return stat.lower()
        fallback = {
            "mode": "p50", "mean": "p50", "min": "p1", "max": "p100",
            "q_low": "p25", "q_high": "p75",
        }
        return fallback.get(stat.lower(), "p50")

    def _load_instruments(self):
        cfg_start = datetime.strptime(f"{self.cfg.start_year} {self.cfg.start_day:03d}", "%Y %j")
        cfg_end = datetime.strptime(f"{self.cfg.end_year} {self.cfg.end_day:03d}", "%Y %j")

        for network in self.cfg.networks:
            info_file = Path(f"/work/dc6/ftp/pub/doc/{network}.info/{network}.channel.summary.day")
            if not info_file.exists():
                continue

            try:
                with info_file.open("r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) < 14: continue
                        
                        station, net, channel, location = parts[0], parts[1], parts[2], parts[3]
                        try:
                            row_start = datetime.strptime(parts[5], "%Y/%m/%d,%H:%M:%S")
                            row_end = datetime.strptime(parts[6], "%Y/%m/%d,%H:%M:%S")
                        except ValueError: continue

                        if (row_start <= cfg_end) and (row_end >= cfg_start):
                            instr_full = " ".join(parts[13:])
                            instr = instr_full.split(",")[0].strip()
                            key = f"{net}.{station}.{location}.{channel}"
                            self._instrument_cache[key] = instr
            except Exception: pass

    def _get_instrument(self, ch: StationChannel) -> str:
        key = f"{ch.network}.{ch.station}.{ch.location}.{ch.component}"
        return self._instrument_cache.get(key, "Unknown")

    def _find_csv(self, network: str, station: str, component: str, location: str) -> Optional[Path]:
        '''Find the percentile CSV. Looks in data/probability by default.'''
        station_dir = self.cfg.out_dir / "data" / "probability" / network / station
        if not station_dir.is_dir():
            return None

        time_tag = f"{self.cfg.start_year}.{self.cfg.start_day}-{self.cfg.end_year}.{self.cfg.end_day}"
        
        # 1. Try specific location format
        expected = f"{station}.{component}.{location}.{time_tag}.csv"
        csv_path = station_dir / expected
        if csv_path.exists():
            return csv_path

        # 2. Try location-less format fallback
        expected_no_loc = f"{station}.{component}.{time_tag}.csv"
        csv_path = station_dir / expected_no_loc
        if csv_path.exists():
            return csv_path

        return None

    def _read_data_from_csv(self, csv_path: Path, target_period: float) -> tuple[float, int]:
        target_log = np.log10(target_period)
        periods_log, values, file_count = [], [], 0

        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if self.stat_column not in (reader.fieldnames or []):
                return float("nan"), 0

            for row in reader:
                try:
                    periods_log.append(float(row["period_log10"]))
                    values.append(float(row[self.stat_column]))
                    if "total_files" in row:
                        file_count = int(row["total_files"])
                except (ValueError, KeyError): continue

        if not periods_log: return float("nan"), 0
        idx = int(np.argmin(np.abs(np.array(periods_log) - target_log)))
        return values[idx], file_count

    def build_points(self, channels: List[StationChannel]) -> List[PSDPoint]:
        points: List[PSDPoint] = []
        for ch in channels:
            csv_path = self._find_csv(ch.network, ch.station, ch.component, ch.location)
            if not csv_path: continue

            val_x, files_x = self._read_data_from_csv(csv_path, self.cfg.period_x)
            val_y, _ = self._read_data_from_csv(csv_path, self.cfg.period_y)

            if np.isnan(val_x) or np.isnan(val_y): continue

            points.append(PSDPoint(
                network=ch.network, component=ch.component, station=ch.station,
                instrument=self._get_instrument(ch),
                psd_x=val_x, psd_y=val_y, file_count=files_x
            ))
        return points
