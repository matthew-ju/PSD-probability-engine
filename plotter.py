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

from core_models import PSDPoint
from config_loader import PlotConfig


RESULTS_DIR = Path(__file__).resolve().parent / "psd_summ_results"


class ComponentPlotter:
    def __init__(self, cfg: PlotConfig, network: str) -> None:
        self.cfg = cfg
        self.network = network
        self.output_dir = RESULTS_DIR / network
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def plot(self, points: List[PSDPoint]) -> None:
        if not points:
            print("NO PSD POINTS TO PLOT")
            return
        components = sorted({p.component for p in points})

        # Define marker mappings
        mpl_markers = ["d", "o", "s", "^", "v", ">", "<", "p", "*", "h", "H", "D"]
        plotly_markers = [
            "diamond", "circle", "square", "triangle-up", "triangle-down", 
            "triangle-right", "triangle-left", "pentagon", "star", "hexagram", 
            "hexagon", "diamond-tall"
        ]

        for comp in components:
            comp_points = [p for p in points if p.component == comp]
            if not comp_points:
                continue

            x_vals = [p.psd_x for p in comp_points]
            y_vals = [p.psd_y for p in comp_points]
            labels = [p.station for p in comp_points]
            file_counts = [p.file_count for p in comp_points]
            instruments = [p.instrument for p in comp_points]

            # Create a dataframe for interactive plotly tooltips
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
                    "Station": station_str,
                    "Completeness_Detail": detail_str,
                    "Completeness (File Count)": sum(counts) / len(counts)
                })

            # Group stations only if they share coordinates AND instrument
            # This allows distinct symbols for different instruments at the same location
            df = df_raw.groupby(
                [f"PSD_X_{int(self.cfg.period_x)}s", f"PSD_Y_{int(self.cfg.period_y)}s", "Instrument"]
            ).apply(merge_rows).reset_index()

            # Aggregate all stations and instruments at each coordinate for tooltips
            # This ensures that even if stations use different instruments (meaning they are separate traces),
            # hovering over the point shows every station and instrument at that location.
            coord_agg = df_raw.groupby(
                [f"PSD_X_{int(self.cfg.period_x)}s", f"PSD_Y_{int(self.cfg.period_y)}s"]
            ).agg({
                "Station": lambda x: ", ".join(sorted(set(x))),
                "Instrument": lambda x: ", ".join(sorted(set(x)))
            }).to_dict('index')
            
            df["All_Stations"] = df.apply(
                lambda r: coord_agg[(r[f"PSD_X_{int(self.cfg.period_x)}s"], r[f"PSD_Y_{int(self.cfg.period_y)}s"])]["Station"], axis=1
            )
            df["All_Instruments"] = df.apply(
                lambda r: coord_agg[(r[f"PSD_X_{int(self.cfg.period_x)}s"], r[f"PSD_Y_{int(self.cfg.period_y)}s"])]["Instrument"], axis=1
            )

            # Custom discrete colors mapping to continuous scale
            custom_colors = ['magenta', 'blue', 'cyan', 'lime', 'yellow', 'orange', 'red']
            
            # Define a larger variety of symbols for Plotly to avoid repetition
            # Standard Plotly symbols: https://plotly.com/python/marker-style/
            plotly_symbol_sequence = [
                "diamond", "circle", "square", "triangle-up", "triangle-down", 
                "triangle-right", "triangle-left", "pentagon", "star", "hexagram", 
                "hexagon", "diamond-tall", "diamond-wide", "hourglass", "bowtie",
                "octagon", "cross", "x", "star-triangle-up", "star-triangle-down"
            ]

            fig = px.scatter(
                df,
                x=f"PSD_X_{int(self.cfg.period_x)}s",
                y=f"PSD_Y_{int(self.cfg.period_y)}s",
                hover_name="All_Stations",
                color="Completeness (File Count)",
                symbol="Instrument",
                symbol_sequence=plotly_symbol_sequence,
                color_continuous_scale=custom_colors,
                custom_data=["Completeness_Detail", "All_Instruments"],
                labels={
                    f"PSD_X_{int(self.cfg.period_x)}s": f"Power [10log(m²/sec⁴/Hz)] (dB) at {int(self.cfg.period_x)} s",
                    f"PSD_Y_{int(self.cfg.period_y)}s": f"Power [10log(m²/sec⁴/Hz)] (dB) at {int(self.cfg.period_y)} s"
                },
                title=f"Network: {self.network}, Component: {comp}<br>Stat: {self.cfg.stat}  |  {self.cfg.start_year}.{self.cfg.start_day:03d} - {self.cfg.end_year}.{self.cfg.end_day:03d}"
            )

            # Customize marker design and tooltip format
            fig.update_traces(
                marker=dict(size=12, opacity=0.75, line=dict(width=1, color='DarkSlateGrey')),
                hovertemplate="<b>%{hovertext}</b><br><br>" +
                              "Instrument: %{customdata[1]}<br>" +
                               "Power at " + str(int(self.cfg.period_x)) + "s: %{x:.2f} dB<br>" +
                               "Power at " + str(int(self.cfg.period_y)) + "s: %{y:.2f} dB<br>" +
                               "File Count (Completeness): %{customdata[0]}"
            )
            
            # Additional visual cleanup
            fig.update_layout(
                title_x=0.5,
                template="plotly_white",
                coloraxis_colorbar=dict(title="Data Completeness<br>(File Count)", yanchor="top", y=1, x=1.05),
                legend=dict(
                    orientation="h",
                    yanchor="top",
                    y=-0.2, # Position legend below the x-axis
                    xanchor="center",
                    x=0.5,
                    title_text="Instrument"
                ),
                margin=dict(b=100), # Add bottom margin for legend
                hoverlabel=dict(bgcolor="white", font_size=14, font_family="Rockwell")
            )

            # Force specific ticks formatting on plot to match grid
            fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
            fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')

            # --- Labeling logic ---
            # Calculate outliers using Interquartile Range (IQR) implementation
            col_x = f"PSD_X_{int(self.cfg.period_x)}s"
            col_y = f"PSD_Y_{int(self.cfg.period_y)}s"
            
            q1_x, q3_x = df[col_x].quantile([0.25, 0.75])
            iqr_x = q3_x - q1_x
            lower_bound_x = q1_x - (1.5 * iqr_x)
            upper_bound_x = q3_x + (1.5 * iqr_x)

            q1_y, q3_y = df[col_y].quantile([0.25, 0.75])
            iqr_y = q3_y - q1_y
            lower_bound_y = q1_y - (1.5 * iqr_y)
            upper_bound_y = q3_y + (1.5 * iqr_y)

            # True if station falls outside standard IQR bounds, or if explicitly requested in config
            outlier_mask = (
                (df[col_x] < lower_bound_x) | (df[col_x] > upper_bound_x) |
                (df[col_y] < lower_bound_y) | (df[col_y] > upper_bound_y)
            )
            # Use getattr to prevent errors if older configs are dynamically used
            explicit_list = set(getattr(self.cfg, 'labeled_stations', []))
            explicit_mask = df["Station"].apply(lambda s: any(st in explicit_list for st in s.split(", ")))
            
            labeled_df = df[outlier_mask | explicit_mask]
            
            # Map arrows onto explicitly chosen labels and outliers on the plotly figure
            for _, row in labeled_df.iterrows():
                fig.add_annotation(
                    x=row[col_x],
                    y=row[col_y],
                    text=f"<b>{row['Station']}</b>",
                    showarrow=True,
                    arrowhead=2,
                    arrowsize=1,
                    arrowwidth=2,
                    arrowcolor="#333333",
                    ax=20,  # Offset x
                    ay=-30, # Offset y
                    font=dict(size=9, color="black"),
                    bgcolor="white",
                    bordercolor="black",
                    borderwidth=1,
                    opacity=0.9
                )


            # Output naming convention
            # Output naming convention (Location code removed as per user request)
            out_base_name = f"{self.cfg.stat}.{self.network}.{comp}.{self.cfg.start_year}.{self.cfg.start_day:03d}-{self.cfg.end_year}.{self.cfg.end_day:03d}"
            
            # 1. Save interactive plotly figure
            html_out_path = self.output_dir / (out_base_name + ".html")
            try:
                fig.write_html(str(html_out_path))
                print(f"Saved interactive plot: {html_out_path}")
            except OSError as exc:
                print(f"Could not save {html_out_path}: {exc}")
                
            # 2. Re-create and save static matplotlib figure
            colors_mpl_list = ['magenta', 'blue', 'cyan', 'lime', 'yellow', 'orange', 'red']
            cmap_mpl = mcolors.LinearSegmentedColormap.from_list("completeness", colors_mpl_list)
            
            min_files = min(file_counts) if file_counts else 0
            max_files = max(file_counts) if file_counts else 0
            norm = mcolors.Normalize(vmin=min_files, vmax=max_files)

            fig_mpl, ax = plt.subplots(figsize=(10, 9)) # Slightly taller for legend
            
            # Map instruments to markers
            unique_instrs = sorted(list(set(instruments)))
            instr_to_marker = {instr: mpl_markers[i % len(mpl_markers)] for i, instr in enumerate(unique_instrs)}
            
            for instr in unique_instrs:
                mask = [p.instrument == instr for p in comp_points]
                sub_x = [x for x, m in zip(x_vals, mask) if m]
                sub_y = [y for y, m in zip(y_vals, mask) if m]
                sub_counts = [c for c, m in zip(file_counts, mask) if m]
                
                scatter = ax.scatter(sub_x, sub_y, s=80, edgecolors='black',
                                     linewidths=0.5, alpha=0.9, 
                                     c=sub_counts, cmap=cmap_mpl, norm=norm,
                                     marker=instr_to_marker[instr], label=instr)

            # Add colorbar
            sm = cm.ScalarMappable(cmap=cmap_mpl, norm=norm)
            sm.set_array([])
            cbar = fig_mpl.colorbar(sm, ax=ax)
            cbar.set_label('Data Completeness (File Count)')
            
            # Set specific ticks for min, mid, and max
            mid_files = (min_files + max_files) / 2
            cbar.set_ticks([min_files, mid_files, max_files])
            cbar.set_ticklabels([f"{min_files} (Min)", f"{mid_files:.1f} (Mid)", f"{max_files} (Max)"])

            texts = []
            for x, y, label in zip(x_vals, y_vals, labels):
                txt = ax.text(x, y, label, fontsize=8, ha="left", va="center")
                texts.append(txt)

            adjust_text(
                texts,
                ax=ax,
                only_move={"points": "y", "text": "xy"},
                arrowprops=dict(arrowstyle="-", color='gray', lw=0.5),
            )

            ax.set_xlabel(
                f"Power [10log(m²/sec⁴/Hz)] (dB) at {int(self.cfg.period_x)} s",
                fontsize=12,
            )
            ax.set_ylabel(
                f"Power [10log(m²/sec⁴/Hz)] (dB) at {int(self.cfg.period_y)} s",
                fontsize=12,
            )
            ax.set_title(
                f"Network: {self.network}, Component: {comp}\n"
                f"Stat: {self.cfg.stat}  |  {self.cfg.start_year}.{self.cfg.start_day:03d} - {self.cfg.end_year}.{self.cfg.end_day:03d}",
                fontsize=14,
            )
            ax.grid(True, linestyle='--', alpha=0.6)

            # Move legend below the plot with neutral (no data-color) symbols
            legend_elements = [
                Line2D([0], [0], marker=instr_to_marker[instr], color='w', 
                       label=instr, markerfacecolor='lightgray', 
                       markeredgecolor='black', markersize=10, linestyle='None')
                for instr in unique_instrs
            ]
            ax.legend(handles=legend_elements, title="Instrument", loc='upper center', 
                      bbox_to_anchor=(0.5, -0.15), ncol=min(3, len(unique_instrs)), 
                      frameon=True)

            png_out_path = self.output_dir / (out_base_name + ".png")
            try:
                fig_mpl.savefig(png_out_path, dpi=200, bbox_inches='tight')
                print(f"Saved PNG plot: {png_out_path}")
            except OSError as exc:
                print(f"Could not save {png_out_path}: {exc}")
            finally:
                plt.close(fig_mpl)

    def save_excel(self, points: List[PSDPoint]) -> None:
        if not points:
            print("No PSD points for Excel.")
            return

        by_comp: dict[str, list[PSDPoint]] = {}
        for p in points:
            by_comp.setdefault(p.component, []).append(p)

        out_name = (
            f"{self.cfg.stat}_{self.network}_PSD_"
            f"{int(self.cfg.period_x)}vs{int(self.cfg.period_y)}.xlsx"
        )
        out_path = self.output_dir / out_name

        try:
            with pd.ExcelWriter(out_path) as writer:
                for comp, comp_points in sorted(by_comp.items()):
                    if not comp_points:
                        continue
                    df = pd.DataFrame(
                        {
                            "Station": [p.station for p in comp_points],
                            f"Power_{int(self.cfg.period_x)}s": [p.psd_x for p in comp_points],
                            f"Power_{int(self.cfg.period_y)}s": [p.psd_y for p in comp_points],
                        }
                    )
                    sheet_name = comp[:31]
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            print(f"Saved Excel: {out_path}")
        except Exception as e:
            print(f"Failed to save Excel: {e}")
