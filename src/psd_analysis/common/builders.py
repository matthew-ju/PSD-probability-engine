from __future__ import annotations
import sys
from itertools import product
from pathlib import Path
from typing import List, Set, Tuple

from .models import StationChannel
from .config import AnalysisConfig

class ChannelBuilder:
    def __init__(self, cfg: AnalysisConfig):
        self.cfg = cfg

    def _load_active_stations(self) -> List[Tuple[str, str, str]]:
        '''Return (network, station, location) triplets for all active channels in channel.summary.day files.'''
        all_active: Set[Tuple[str, str, str]] = set()
        
        for network in self.cfg.networks:
            summary_path = Path(f"/work/dc6/ftp/pub/doc/{network}.info/{network}.channel.summary.day")

            if not summary_path.exists():
                print(f"Warning: Summary file not found at {summary_path}. Skipping {network}.")
                continue

            try:
                with summary_path.open("r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if not line.strip() or line.startswith("Stat ") or set(line.strip()) == {"-"}:
                            continue
                        parts = line.split()
                        if len(parts) < 7:
                            continue
                        stat, net, cha, loc = parts[0], parts[1], parts[2], parts[3]
                        end_time = parts[6]

                        if net != network:
                            continue
                        
                        # Blacklists
                        if (net == "BK" and loc == "S0") or (net == "NC" and loc == "20"):
                            continue

                        # Only active sensors
                        if not end_time.startswith("3000/01/01,00:00:00"):
                            continue
                        
                        # Use any requested channel to identify active (stat, loc) pairs
                        if not any(cha.startswith(comp[:2]) for comp in self.cfg.components):
                            continue
                            
                        all_active.add((network, stat, loc))
            except OSError as exc:
                print(f"COULDN'T READ {network}: {summary_path}: {exc}", file=sys.stderr)
        
        return sorted(list(all_active))

    def build_channels(self) -> List[StationChannel]:
        active_triplets = self._load_active_stations()
        selected_triplets: List[Tuple[str, str, str]] = []

        if self.cfg.stations:
            wanted = set(self.cfg.stations)
            for net, sta, loc in active_triplets:
                if sta in wanted:
                    selected_triplets.append((net, sta, loc))
        else:
            selected_triplets = active_triplets

        if not selected_triplets:
            return []

        combos = product(selected_triplets, self.cfg.components)
        channels: List[StationChannel] = [
            StationChannel(
                network=net,
                station=sta,
                location=loc,
                component=comp,
                base_dir=self.cfg.base_dir,
            )
            for (net, sta, loc), comp in combos
        ]
        return channels
