'''
Runs the probability engine (as a subprocess) for the configured stations/components,
then reads the output CSV files to extract PSD values at target periods.
'''
from __future__ import annotations

import csv
import sys
from datetime import datetime
import numpy as np
from pathlib import Path
from typing import List, Optional, Dict

from core_models import PSDPoint, StationChannel
from config_loader import PlotConfig


PROBABILITY_DIR = Path(__file__).resolve().parent / "probability"


class CSVReader:
    '''Reads percentile CSV files produced by the probability engine.'''

    def __init__(self, cfg: PlotConfig):
        self.cfg = cfg
        self.stat_column = self._resolve_stat_column(cfg.stat)
        self._instrument_cache: Dict[str, str] = {}
        self._load_instruments()

    def _resolve_stat_column(self, stat: str) -> str:
        '''Convert stat name to CSV column name.
        "p99" -> "p99", "p1" -> "p1", "mode" -> "p50" (fallback)
        '''
        if stat.lower().startswith("p") and stat[1:].isdigit():
            return stat.lower()
        # Fallback mapping for legacy stat names
        fallback = {
            "mode": "p50",
            "mean": "p50",
            "min": "p1",
            "max": "p100",
            "q_low": "p25",
            "q_high": "p75",
        }
        mapped = fallback.get(stat.lower())
        if mapped:
            print(f"  Mapping legacy stat '{stat}' -> CSV column '{mapped}'")
            return mapped
        print(f"  Warning: Unknown stat '{stat}', defaulting to 'p50'")
        return "p50"

    def _load_instruments(self):
        '''Load instrument info from .info files for all configured networks.'''
        cfg_start = datetime.strptime(f"{self.cfg.start_year} {self.cfg.start_day:03d}", "%Y %j")
        cfg_end = datetime.strptime(f"{self.cfg.end_year} {self.cfg.end_day:03d}", "%Y %j")

        for network in self.cfg.networks:
            info_file = Path(f"/work/dc6/ftp/pub/doc/{network}.info/{network}.channel.summary.day")
            if not info_file.exists():
                print(f"  Warning: Info file not found: {info_file}")
                continue

            try:
                with info_file.open("r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) < 14:
                            continue
                        
                        station = parts[0]
                        net = parts[1]
                        channel = parts[2]
                        location = parts[3]
                        
                        # Date format: 2023/12/28,17:14:00
                        try:
                            row_start = datetime.strptime(parts[5], "%Y/%m/%d,%H:%M:%S")
                            row_end = datetime.strptime(parts[6], "%Y/%m/%d,%H:%M:%S")
                        except ValueError:
                            continue

                        # Overlap check
                        if (row_start <= cfg_end) and (row_end >= cfg_start):
                            # Extract instrument (14th column, first part before comma)
                            instr_full = " ".join(parts[13:]) # Handle spaces in instrument info
                            instr = instr_full.split(",")[0].strip()
                            
                            key = f"{net}.{station}.{location}.{channel}"
                            self._instrument_cache[key] = instr
            except Exception as e:
                print(f"  Error reading info file for {network}: {e}")

    def _get_instrument(self, ch: StationChannel) -> str:
        key = f"{ch.network}.{ch.station}.{ch.location}.{ch.component}"
        return self._instrument_cache.get(key, "Unknown")

    def _find_csv(self, network: str, station: str, component: str, location: str) -> Optional[Path]:
        '''Find the percentile CSV for a station+component. Now tries location-less format first.'''
        station_dir = PROBABILITY_DIR / network / station
        if not station_dir.is_dir():
            return None

        time_tag = f"{self.cfg.start_year}.{self.cfg.start_day}-{self.cfg.end_year}.{self.cfg.end_day}"
        
        # 1. Try location-less format (new combined format)
        expected_new = f"{station}.{component}.{time_tag}.csv"
        csv_path = station_dir / expected_new
        if csv_path.exists():
            return csv_path

        # 2. Try specific location format (legacy/specific)
        expected_old = f"{station}.{component}.{location}.{time_tag}.csv"
        csv_path = station_dir / expected_old
        if csv_path.exists():
            return csv_path

        # Fallback: find any matching CSV (new format pattern)
        pattern_new = f"{station}.{component}.*.csv"
        matches = sorted(station_dir.glob(pattern_new))
        if matches:
            # Filter matches to avoid picking files with location codes if possible
            new_matches = [m for m in matches if len(m.name.split(".")) == 5] # sta.comp.start.end.csv
            if new_matches:
                return new_matches[-1]
            return matches[-1]
        return None

    def _read_data_from_csv(self, csv_path: Path, target_period: float) -> tuple[float, int]:
        '''Read the stat column value at the row closest to target_period, and file count.'''
        target_log = np.log10(target_period)

        periods_log = []
        values = []
        file_count = 0

        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            if self.stat_column not in fieldnames:
                print(f"  Warning: column '{self.stat_column}' not in {csv_path.name}. Available: {fieldnames}")
                return float("nan"), 0

            for row in reader:
                try:
                    p_log = float(row["period_log10"])
                    val = float(row[self.stat_column])
                    periods_log.append(p_log)
                    values.append(val)
                    # total_files is the same for all rows in this CSV
                    if "total_files" in row:
                        file_count = int(row["total_files"])
                except (ValueError, KeyError):
                    continue

        if not periods_log:
            return float("nan"), 0

        arr = np.array(periods_log)
        idx = int(np.argmin(np.abs(arr - target_log)))
        return values[idx], file_count

    def build_points(self, channels: List[StationChannel]) -> List[PSDPoint]:
        points: List[PSDPoint] = []

        for ch in channels:
            csv_path = self._find_csv(ch.network, ch.station, ch.component, ch.location)
            if csv_path is None:
                print(f"  No CSV found for {ch.station}.{ch.component}.{ch.location}, skipping")
                continue

            val_x, files_x = self._read_data_from_csv(csv_path, self.cfg.period_x)
            val_y, files_y = self._read_data_from_csv(csv_path, self.cfg.period_y)

            if np.isnan(val_x) or np.isnan(val_y):
                print(f"  Warning: NaN value for {ch.station}.{ch.component}, skipping")
                continue

            points.append(PSDPoint(
                network=ch.network,
                component=ch.component,
                station=ch.station,
                instrument=self._get_instrument(ch),
                psd_x=val_x,
                psd_y=val_y,
                file_count=files_x # Assuming x and y have same file count from same CSV
            ))

        return points
