#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
import sys

import config
from data_io import SeismicPathResolver, PdfDirectoryReader, write_percentiles_csv
from processing import PeriodPowerAggregator
from visualization import PdfVisualizer

def main() -> None:
    """
    Run percentile aggregation for one or more stations/components.

    Directories are constructed as: {root}/{network}.{station}.{location}/{component}/wrk
    Example:                        /ref/dc14/PDF/STATS/BK.BKS.00/HHZ/wrk
    """

    parser = argparse.ArgumentParser(description="Aggregate PDFanalysis probabilities and compute noise percentiles.")
    parser.add_argument(
        "--root",
        type=str,
        default=config.DEFAULT_ROOT,
        help="Root path to PDF/STATS (default: DEFAULT_ROOT).",
    )
    parser.add_argument(
        "--networks", "--network",
        nargs="+",
        default=list(config.DEFAULT_NETWORKS),
        help="Network codes (default: BK NC).",
    )
    parser.add_argument(
        "--locations", "--location",
        nargs="+",
        default=list(config.DEFAULT_LOCATIONS),
        help="Location codes (default: 00 01).",
    )
    parser.add_argument(
        "--stations",
        nargs="+",
        default=list(config.DEFAULT_STATIONS),
        help="List of stations (e.g. THOM BKS).",
    )
    parser.add_argument(
        "--components",
        nargs="+",
        default=list(config.DEFAULT_COMPONENTS),
        help="List of components (e.g. HHZ HHN).",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=config.DEFAULT_START_YEAR,
        help="Start year (inclusive).",
    )
    parser.add_argument(
        "--start-day",
        type=int,
        default=config.DEFAULT_START_DAY,
        help="Start Julian day.",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=config.DEFAULT_END_YEAR,
        help="End year (inclusive).",
    )
    parser.add_argument(
        "--end-day",
        type=int,
        default=config.DEFAULT_END_DAY,
        help="End Julian day.",
    )
    parser.add_argument(
        "--percentiles",
        nargs="+",
        type=float,
        default=config.DEFAULT_PERCENTILES,
        help="Percentiles as fractions (default: 0.05 0.10 0.25).",
    )
    parser.add_argument(
        "--output-prefix",
        type=str,
        default="percentiles",
        help="Prefix for output CSVs. "
        "{prefix}.{station}.{component}.csv",
    )

    args = parser.parse_args()
    resolver = SeismicPathResolver()
    script_dir = Path(__file__).parent.resolve()

    for network in args.networks:
        for station in args.stations:
            # Save results inside the probability/ folder to match project structure
            station_out_dir = script_dir / network / station
            # Only create directory if we actually find data for this station/network combo
            
            for component in args.components:
                for location in args.locations:
                    if (network == "BK" and location == "S0") or (network == "NC" and location == "20"):
                        continue
                    aggregator = PeriodPowerAggregator()
                    total_files_processed = 0

                    current_year = args.start_year
                    while current_year <= args.end_year:
                        curr_min_day = args.start_day if current_year == args.start_year else 1
                        curr_max_day = args.end_day if current_year == args.end_year else 366

                        try:
                            station_dir = resolver.resolve(
                                args.root, network, station, location, component, current_year
                            )
                        except FileNotFoundError:
                            current_year += 1
                            continue

                        reader = PdfDirectoryReader(
                            station_dir,
                            year=current_year,
                            start_day=curr_min_day,
                            end_day=curr_max_day,
                        )

                        if reader.file_count > 0:
                            for rec in reader.iter_records():
                                aggregator.add_record(rec)
                            total_files_processed += reader.file_count
                        
                        current_year += 1

                    if total_files_processed == 0:
                        continue

                    # Now we know we have data, ensure directory exists
                    station_out_dir.mkdir(parents=True, exist_ok=True)

                    aggregator.finalize(total_files_processed)
                    per_period = aggregator.percentiles_all_periods(args.percentiles)
                    
                    # Include location in filename and title so sensors are kept separate
                    base_name = f"{station}.{component}.{location}"
                    time_tag = f"{args.start_year}.{args.start_day}-{args.end_year}.{args.end_day}"
                    filename = f"{base_name}.{time_tag}.csv"
                    out_path = station_out_dir / filename
                    
                    plot_limits = {
                        "xlow": 0.02, "xhigh": 100.0, 
                        "ylow": -200.0, "yhigh": -50.0
                    }
                    title = (f"PSD PDF: {network}.{station}.{location}.{component} "
                             f"({args.start_year}.{args.start_day:03d} - {args.end_year}.{args.end_day:03d})")
                    
                    viz = PdfVisualizer(title, aggregator)
                    # Plot only p5, p10, and p50 by default
                    plot_percentiles = [p for p in args.percentiles if p in [0.05, 0.10, 0.50]]
                    if not plot_percentiles:
                        plot_percentiles = args.percentiles
                    
                    viz.render(plot_percentiles, plot_limits)
                    
                    image_name = out_path.with_suffix(".png")
                    viz.save(str(image_name))
                    write_percentiles_csv(
                        out_path,
                        per_period,
                        args.percentiles,
                        total_files=total_files_processed
                    )

                    print(f"Processed {network}.{station}.{location}.{component}: {total_files_processed} files. Saved to {station_out_dir}")

if __name__ == "__main__":
    main()
