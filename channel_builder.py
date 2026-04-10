from __future__ import annotations

import sys
from itertools import product
from pathlib import Path
from typing import List, Set, Tuple, Dict

from core_models import StationChannel
from config_loader import PlotConfig


class ChannelBuilder:
    def __init__(self, cfg: PlotConfig):
        self.cfg = cfg

    def _load_active_hhz_stations(self) -> List[Tuple[str, str, str]]:
        '''Return (network, station, location) triplets for all active HHZ in channel.summary.day files.
        "active" channel: End time starts with "3000/01/01,00:00:00"
        '''
        all_active: Set[Tuple[str, str, str]] = set()
        
        for network in self.cfg.networks:
            # Resolve path per network: /work/dc6/ftp/pub/doc/{network}.info/{network}.channel.summary.day
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
                        
                        # 1. Network-specific blacklists
                        if (net == "BK" and loc == "S0") or (net == "NC" and loc == "20"):
                            continue

                        # 2. Only consider active sensors
                        if not end_time.startswith("3000/01/01,00:00:00"):
                            continue
                        
                        # 3. Discovery: Use any requested channel to identify active (stat, loc) pairs
                        # Common: HHZ, EHZ, HNZ, etc.
                        if not any(cha.startswith(comp[:2]) for comp in self.cfg.components):
                            continue
                            
                        all_active.add((network, stat, loc))
            except OSError as exc:
                print(f"COULDN'T READ {network}: {summary_path}: {exc}", file=sys.stderr)
        
        return sorted(list(all_active))

    def build_channels(self) -> List[StationChannel]:
        active_triplets = self._load_active_hhz_stations()

        selected_triplets: List[Tuple[str, str, str]] = []

        if self.cfg.stations:
            wanted = set(self.cfg.stations)

            for net, sta, loc in active_triplets:
                if sta in wanted:
                    selected_triplets.append((net, sta, loc))

            found_stats = {s[1] for s in active_triplets}
            missing = wanted - found_stats
            if missing:
                print(f"Warning: stations not found in any active list: {sorted(missing)}")
        else:
            selected_triplets = active_triplets

        if not selected_triplets:
            print("No stations selected.", file=sys.stderr)
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
