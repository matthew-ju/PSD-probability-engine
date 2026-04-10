from __future__ import annotations
from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.cm as cm
from matplotlib.lines import Line2D
import plotly.express as px
import pandas as pd
from adjustText import adjust_text

from ..common.models import PSDPoint
from ..common.config import AnalysisConfig

class ComponentPlotter:
    def __init__(self, cfg: AnalysisConfig, network: str) -> None:
        self.cfg = cfg
        self.network = network
        # Results go into data/outputs/psd_summ_results/ for organization
        self.output_dir = cfg.out_dir / "data" / "outputs" / "psd_summ_results" / network
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def plot(self, points: List[PSDPoint]) -> None:
        if not points:
            print("  [Plotter] NO PSD POINTS TO PLOT")
            return
        components = sorted({p.component for p in points})

        mpl_markers = ["d", "o", "s", "^", "v", ">", "<", "p", "*", "h", "H", "D"]
        plotly_symbol_sequence = [
            "diamond", "circle", "square", "triangle-up", "triangle-down", 
            "triangle-right", "triangle-left", "pentagon", "star", "hexagram", 
            "hexagon", "diamond-tall", "diamond-wide", "hourglass", "bowtie",
            "octagon", "cross", "x", "star-triangle-up", "star-triangle-down"
        ]

        for comp in components:
            comp_points = [p for p in points if p.component == comp]
            if not comp_points: continue

            x_vals = [p.psd_x for p in comp_points]
            y_vals = [p.psd_y for p in comp_points]
            labels = [p.station for p in comp_points]
            file_counts = [p.file_count for p in comp_points]
            instruments = [p.instrument for p in comp_points]

            df_raw = pd.DataFrame({
                "Station": labels,
                "Instrument": instruments,
                f"PSD_X_{int(self.cfg.period_x)}s": x_vals,
                f"PSD_Y_{int(self.cfg.period_y)}s": y_vals,
                "Completeness (File Count)": file_counts
            })

            def merge_rows(group):
                group = group.sort_values("Completeness (File Count)", ascending=False)
                stations = group["Station"].tolist()
                counts = group["Completeness (File Count)"].tolist()
                
                station_str = ", ".join(stations)
                if len(stations) > 1:
                    detail_str = "<br>    " + "<br>    ".join(f"{s}: {c} files" for s, c in zip(stations, counts))
                else:
                    detail_str = f"{counts[0]}"
                return pd.Series({
                    "Station": station_str, "Completeness_Detail": detail_str,
                    "Completeness (File Count)": sum(counts) / len(counts)
                })

            col_x, col_y = f"PSD_X_{int(self.cfg.period_x)}s", f"PSD_Y_{int(self.cfg.period_y)}s"
            df = df_raw.groupby([col_x, col_y, "Instrument"]).apply(merge_rows).reset_index()

            coord_agg = df_raw.groupby([col_x, col_y]).agg({
                "Station": lambda x: ", ".join(sorted(set(x))),
                "Instrument": lambda x: ", ".join(sorted(set(x)))
            }).to_dict('index')
            
            df["All_Stations"] = df.apply(lambda r: coord_agg[(r[col_x], r[col_y])]["Station"], axis=1)
            df["All_Instruments"] = df.apply(lambda r: coord_agg[(r[col_x], r[col_y])]["Instrument"], axis=1)

            custom_colors = ['magenta', 'blue', 'cyan', 'lime', 'yellow', 'orange', 'red']
            
            fig = px.scatter(
                df, x=col_x, y=col_y, hover_name="All_Stations",
                color="Completeness (File Count)", symbol="Instrument",
                symbol_sequence=plotly_symbol_sequence, color_continuous_scale=custom_colors,
                custom_data=["Completeness_Detail", "All_Instruments"],
                labels={col_x: f"Power (dB) at {int(self.cfg.period_x)}s", col_y: f"Power (dB) at {int(self.cfg.period_y)}s"},
                title=f"Network: {self.network}, Component: {comp}<br>Stat: {self.cfg.stat} | {self.cfg.start_year}.{self.cfg.start_day:03d}-{self.cfg.end_year}.{self.cfg.end_day:03d}"
            )

            fig.update_traces(
                marker=dict(size=12, opacity=0.75, line=dict(width=1, color='DarkSlateGrey')),
                hovertemplate="<b>%{hovertext}</b><br><br>Instrument: %{customdata[1]}<br>" +
                               "Power at " + str(int(self.cfg.period_x)) + "s: %{x:.2f} dB<br>" +
                               "Power at " + str(int(self.cfg.period_y)) + "s: %{y:.2f} dB<br>" +
                               "File Count: %{customdata[0]}"
            )
            
            fig.update_layout(title_x=0.5, template="plotly_white", margin=dict(b=100))

            # Labeling outliers
            q1_x, q3_x = df[col_x].quantile([0.25, 0.75])
            iqr_x = q3_x - q1_x
            q1_y, q3_y = df[col_y].quantile([0.25, 0.75])
            iqr_y = q3_y - q1_y

            outlier_mask = (df[col_x] < (q1_x - 1.5*iqr_x)) | (df[col_x] > (q3_x + 1.5*iqr_x)) | \
                           (df[col_y] < (q1_y - 1.5*iqr_y)) | (df[col_y] > (q3_y + 1.5*iqr_y))
            explicit_list = set(self.cfg.labeled_stations)
            explicit_mask = df["Station"].apply(lambda s: any(st in explicit_list for st in s.split(", ")))
            
            for _, row in df[outlier_mask | explicit_mask].iterrows():
                fig.add_annotation(x=row[col_x], y=row[col_y], text=f"<b>{row['Station']}</b>", showarrow=True)

            out_base_name = f"{self.cfg.stat}.{self.network}.{comp}.{self.cfg.start_year}.{self.cfg.start_day:03d}-{self.cfg.end_year}.{self.cfg.end_day:03d}"
            html_out_path = self.output_dir / (out_base_name + ".html")
            fig.write_html(str(html_out_path))

            # Matplotlib static plot
            fig_mpl, ax = plt.subplots(figsize=(10, 9))
            unique_instrs = sorted(list(set(instruments)))
            instr_to_marker = {instr: mpl_markers[i % len(mpl_markers)] for i, instr in enumerate(unique_instrs)}
            norm = mcolors.Normalize(vmin=min(file_counts), vmax=max(file_counts))
            cmap_mpl = mcolors.LinearSegmentedColormap.from_list("completeness", custom_colors)

            for instr in unique_instrs:
                mask = [p.instrument == instr for p in comp_points]
                ax.scatter([x for x, m in zip(x_vals, mask) if m], [y for y, m in zip(y_vals, mask) if m], 
                           c=[c for c, m in zip(file_counts, mask) if m], cmap=cmap_mpl, norm=norm,
                           marker=instr_to_marker[instr], label=instr, edgecolors='black', alpha=0.9)

            cbar = fig_mpl.colorbar(cm.ScalarMappable(cmap=cmap_mpl, norm=norm), ax=ax)
            cbar.set_label('File Count')

            texts = [ax.text(x, y, label, fontsize=8) for x, y, label in zip(x_vals, y_vals, labels)]
            adjust_text(texts, ax=ax, arrowprops=dict(arrowstyle="-", color='gray', lw=0.5))

            ax.set_title(f"Network: {self.network}, Component: {comp}\n{self.cfg.stat} | {self.cfg.start_year}.{self.cfg.start_day:03d}-{self.cfg.end_year}.{self.cfg.end_day:03d}")
            ax.set_xlabel(f"Power (dB) at {int(self.cfg.period_x)}s")
            ax.set_ylabel(f"Power (dB) at {int(self.cfg.period_y)}s")
            ax.grid(True, linestyle='--', alpha=0.6)
            
            png_out_path = self.output_dir / (out_base_name + ".png")
            fig_mpl.savefig(png_out_path, dpi=200, bbox_inches='tight')
            plt.close(fig_mpl)

    def save_excel(self, points: List[PSDPoint]) -> None:
        if not points: return
        by_comp: dict[str, list[PSDPoint]] = {}
        for p in points: by_comp.setdefault(p.component, []).append(p)

        out_name = f"{self.cfg.stat}_{self.network}_PSD_{int(self.cfg.period_x)}vs{int(self.cfg.period_y)}.xlsx"
        out_path = self.output_dir / out_name

        with pd.ExcelWriter(out_path) as writer:
            for comp, comp_points in sorted(by_comp.items()):
                df = pd.DataFrame({
                    "Station": [p.station for p in comp_points],
                    f"Power_{int(self.cfg.period_x)}s": [p.psd_x for p in comp_points],
                    f"Power_{int(self.cfg.period_y)}s": [p.psd_y for p in comp_points],
                })
                df.to_excel(writer, sheet_name=comp[:31], index=False)
