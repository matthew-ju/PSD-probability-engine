from __future__ import annotations
from pathlib import Path
from typing import List

from ..common.config import AnalysisConfig
from .io import SeismicPathResolver, PdfDirectoryReader, write_percentiles_csv
from .aggregator import PeriodPowerAggregator
from .visualization import PdfVisualizer

def run_probability_engine(cfg: AnalysisConfig, station_list: List[str] = None) -> None:
    """
    Run the probability engine for the configured settings.
    station_list: Optional override for stations to process.
    """
    resolver = SeismicPathResolver()
    stations = station_list if station_list is not None else cfg.stations
    
    # If stations is empty, we expect the caller to have resolved them 
    # (e.g., via ChannelBuilder) or we skip.
    if not stations:
        print("No stations provided to probability engine.")
        return

    for network in cfg.networks:
        for station in stations:
            # Output directory for this station
            # Save results inside data/probability/ for organization
            prob_data_dir = cfg.out_dir / "data" / "probability" / network / station
            
            for component in cfg.components:
                for location in cfg.locations:
                    if (network == "BK" and location == "S0") or (network == "NC" and location == "20"):
                        continue

                    aggregator = PeriodPowerAggregator()
                    total_files_processed = 0

                    current_year = cfg.start_year
                    while current_year <= cfg.end_year:
                        curr_min_day = cfg.start_day if current_year == cfg.start_year else 1
                        curr_max_day = cfg.end_day if current_year == cfg.end_year else 366

                        try:
                            station_dir = resolver.resolve(
                                cfg.base_dir, network, station, location, component, current_year
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

                    # Ensure directory exists
                    prob_data_dir.mkdir(parents=True, exist_ok=True)

                    aggregator.finalize(total_files_processed)
                    per_period = aggregator.percentiles_all_periods(cfg.percentiles)
                    
                    base_name = f"{station}.{component}.{location}"
                    time_tag = f"{cfg.start_year}.{cfg.start_day}-{cfg.end_year}.{cfg.end_day}"
                    filename = f"{base_name}.{time_tag}.csv"
                    out_path = prob_data_dir / filename
                    
                    plot_limits = {
                        "xlow": 0.02, "xhigh": 100.0, 
                        "ylow": -200.0, "yhigh": -50.0
                    }
                    title = (f"PSD PDF: {network}.{station}.{location}.{component} "
                             f"({cfg.start_year}.{cfg.start_day:03d} - {cfg.end_year}.{cfg.end_day:03d})")
                    
                    viz = PdfVisualizer(title, aggregator)
                    plot_percentiles = [p for p in cfg.percentiles if p in [0.05, 0.10, 0.50]]
                    if not plot_percentiles:
                        plot_percentiles = cfg.percentiles
                    
                    viz.render(plot_percentiles, plot_limits)
                    
                    image_name = out_path.with_suffix(".png")
                    viz.save(str(image_name))
                    write_percentiles_csv(
                        out_path,
                        per_period,
                        cfg.percentiles,
                        total_files=total_files_processed
                    )

                    print(f"  [Engine] Processed {network}.{station}.{location}.{component}: {total_files_processed} files.")

if __name__ == "__main__":
    # This allow running the engine independently if needed
    import sys
    import yaml
    if len(sys.argv) > 1:
        cfg = load_config(Path(sys.argv[1]))
        run_probability_engine(cfg)
