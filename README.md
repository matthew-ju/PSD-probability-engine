# Seismology Probability & PSD Analysis

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A high-performance data pipeline for processing, profiling, and visualizing seismic network noise data.

**Seismology Probability & PSD Analysis** quantifies seismic station noise levels across multiple structural periods using raw PDF data, generating detailed Probability Density Function (PDF) heatmaps and cross-network Power Spectral Density (PSD) scatter plots. Built initially for the Berkeley Seismology Lab (BSL) but architected with flexibility in mind to analyze any dynamically structured `PDFanalysis` datasets.

---

## Key Capabilities

- **PDF Heatmap Synthesis**: Aggregates massively distributed daily PSD files to compute high-fidelity structural noise percentile curves (e.g., p5, p50, p95).
- **Network-Wide Comparison**: Generates interactive scatter plots to cleanly compare aggregated multi-period PSD statistics.
- **Dynamic Site Discovery**: Automatically scrapes and cross-references active channel statuses and underlying metadata.
- **Outlier Diagnostics**: Quickly zero in on anomalous stations, faulty sensors, or local noise sources leveraging strict statistical thresholds.

---

## Architecture

The pipeline consists of two primary decoupled components:

1. **Probability Engine (`probability/main.py`)**: 
   - A standalone processing core that parses raw datasets, recursively computes probabilities over thousands of daily files, and exports aggregated percentile arrays (`.csv`) alongside visual heatmaps (`.png`).
2. **Scatter Plot Analyzer (`main.py`)**: 
   - The primary orchestrator. Consumes YAML specifications, drives active channel discovery, queries the Probability Engine, and aggregates scatter visualization to compare localized instrument components.

<details>
<summary><b>View Directory Structure</b></summary>

```text
psd/
├── main.py                  # Unified Pipeline Entry Point
├── src/psd_analysis/        # Core Analysis logic
│   ├── engine/              # Probability engine logic
│   ├── plotter/             # Scatter Plot generation
│   └── common/              # Shared models & discovery
├── configs/                 # YAML Configuration Files
├── scripts/                 # Utility scripts (confirm_filters.py)
└── data/                    # Unified Data Hub
    ├── probability/         # Raw Engine CSVs & Heatmaps
    └── outputs/             # Summary Plots & Excel reports
```
</details>

---

## Installation

```bash
git clone https://github.com/matthew-ju/seismology-probability-analysis.git
cd seismology-probability-analysis
pip install -r requirements.txt
```

*Prerequisite: Python 3.10+ and configured networking access to standardized `PDFanalysis.*.pdf` directory structures.*

---

## Usage Example & Interactive Demo

Run the full pipeline (engine + plotter) for all active stations:

```bash
python3 main.py configs/default_config.yml --run-engine
```

To only run the engine (compute data) without generating summary plots:

```bash
python3 main.py --run-engine --skip-plots
```

**Heatmap Output** (Probability Distribution with over-plotted noise percentiles):
![Probability Distribution — BKS HHZ 2025](./docs/assets/percentiles.BKS.HHZ.2025.1-2025.366.png)

*(Output includes a robust `.csv` numerically mapping `period_log10` to requested interval percentiles)*

If you already have pre-computed CSV data in `data/probability/`, you can generate summary plots immediately:

```bash
python3 main.py
```

This runs the full operational flow, outputting both interactive network-wide HTML graphs and comprehensive Excel matrix reports.

**Scatter Plot Output** (BK Network HHZ, 50s vs 1s noise comparison):
![PSD Scatter Plot — BK HHZ 50s vs 1s](./docs/assets/BK_HHZ_50vs1_p50.png)

*(Stations clustered tightly have identical noise specifications; scattered outliers represent unique or anomalous behaviors)*

### 3. Interactive Visualization

Network-wide outputs from the Scatter Plot Analyzer feature interactive diagnostic capabilities. Watch the demo below to see dynamic exploration of outliers and sensor metadata natively in the browser:



https://github.com/user-attachments/assets/2f2facc7-f8bc-4789-b8f7-aea51e3cce74



---

## Configuration Snippet (`config.yml`)

The analyzer focuses heavily on usability, simplicity, and reproducibility:

```yaml
base_dir: "/ref/dc14/PDF/STATS"
network: ["BK", "NC"]
components: ["HHZ", "HHN", "HHE", "EHZ", "EHN", "EHE"]

period_x: 50       # Target Compare Period (x-axis)
period_y: 1        # Target Compare Period (y-axis)
stat: "p50"        # Aggregate statistic (e.g. median)

# Active Time Constraints
start_year: 2024
end_year: 2025
```

---

*Note: Monolithic legacy architectures (`psd.py` and `probability/probability.py`) are archived for tracking operational history within their respective directories.*
