#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path

# Add src to sys.path to allow imports if not installed
sys.path.append(str(Path(__file__).parent / "src"))

from psd_analysis.common.config import load_config, ConfigError
from psd_analysis.common.builders import ChannelBuilder
from psd_analysis.engine.analyzer import run_probability_engine
from psd_analysis.plotter.data_reader import CSVReader
from psd_analysis.plotter.core import ComponentPlotter

def main():
    parser = argparse.ArgumentParser(description="PSD Analysis Pipeline")
    parser.add_argument("config", nargs="?", default="configs/default_config.yml", help="Path to config.yml")
    parser.add_argument("--run-engine", action="store_true", help="Run the probability engine before plotting")
    parser.add_argument("--skip-plots", action="store_true", help="Skip the plotting step")
    
    args = parser.parse_args()
    
    # Pre-checks for config path (fallback to old location if new scripts/configs isn't used yet)
    cfg_path = Path(args.config)
    if not cfg_path.exists() and cfg_path == Path("configs/default_config.yml"):
        cfg_path = Path("config.yml")
    
    try:
        cfg = load_config(cfg_path)
    except ConfigError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    # Step 1: Build channel list (Discovery)
    print(f"--- Starting PSD Analysis | stat={cfg.stat} ---")
    builder = ChannelBuilder(cfg)
    channels = builder.build_channels()
    
    if not channels:
        print("No valid channels discovered. Check your summary files and network settings.")
        sys.exit(0)

    unique_stations = sorted({ch.station for ch in channels})
    print(f"Discovered {len(channels)} channels across {len(unique_stations)} active stations.")

    # Step 2: Probability Engine (Optional)
    if args.run_engine:
        print("\n--- Running Probability Engine ---")
        run_probability_engine(cfg, unique_stations)
    else:
        print("\nSkipping Probability Engine (use --run-engine to recompute data).")

    # Step 3: Plotting
    if args.skip_plots:
        print("\nPlotting skipped as requested.")
        return

    print("\n--- Generating Plots ---")
    reader = CSVReader(cfg)
    all_points = reader.build_points(channels)

    if not all_points:
        print("No PSD data found in probability outputs. Did you run the engine?")
        sys.exit(0)

    # Group by network
    points_by_net = {}
    for p in all_points:
        points_by_net.setdefault(p.network, []).append(p)

    for net, net_points in points_by_net.items():
        print(f"Processing Network: {net} ({len(net_points)} points)")
        plotter = ComponentPlotter(cfg, net)
        plotter.plot(net_points)
        plotter.save_excel(net_points)

    print("\nDone. Results saved to data/outputs/")

if __name__ == "__main__":
    main()
