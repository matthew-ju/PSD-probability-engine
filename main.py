#!/usr/bin/env python3
'''
PSD scatter plot generator using the probability engine.

Usage:
    python main.py config.yml
'''
from __future__ import annotations

import sys
from pathlib import Path

from config_loader import load_config, ConfigError
from channel_builder import ChannelBuilder
from data_integration import CSVReader
from plotter import ComponentPlotter


def main() -> None:
    cfg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("config.yml")

    if not cfg_path.exists():
        print(f"Config file not found: {cfg_path}")
        sys.exit(1)

    try:
        cfg = load_config(cfg_path)
    except ConfigError as exc:
        print(f"Configuration error: {exc}")
        sys.exit(1)

    print(f"Config loaded: {len(cfg.stations)} stations, networks={', '.join(cfg.networks)}, stat={cfg.stat}")
    print(f"Time range: {cfg.start_year}.{cfg.start_day} – {cfg.end_year}.{cfg.end_day}")
    print(f"Periods: {cfg.period_x}s vs {cfg.period_y}s")

    # Step 1: Build channel list
    builder = ChannelBuilder(cfg)
    channels = builder.build_channels()

    if not channels:
        print("No valid channels found. Exiting.")
        sys.exit(0)

    unique_stations = sorted({ch.station for ch in channels})
    print(f"Active stations: {len(unique_stations)}")

    # Step 2: Read precomputed CSVs -> PSDPoints
    print("Reading precomputed probability engine data...")
    reader = CSVReader(cfg)
    all_points = reader.build_points(channels)

    if not all_points:
        print(f"No PSD points generated for {cfg.stat}. Check probability output.")
        sys.exit(0)

    # Step 3: Group by network and Plot
    points_by_net: dict[str, list[PSDPoint]] = {}
    for p in all_points:
        points_by_net.setdefault(p.network, []).append(p)

    for net, net_points in points_by_net.items():
        print(f"\n--- Processing Network: {net} | stat: {cfg.stat} ---")
        print(f"Generated {len(net_points)} PSD points")
        
        plotter = ComponentPlotter(cfg, net)
        plotter.plot(net_points)
        plotter.save_excel(net_points)

    print("\nDone. Results saved to psd_summ_results/")


if __name__ == "__main__":
    main()
