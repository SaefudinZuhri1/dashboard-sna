"""Halaman Social Network Analysis (SNA) dan identifikasi influencer."""

from __future__ import annotations

from html import escape
from typing import Any

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

from utils.chart_builder import PLATFORM_COLORS, PLATFORM_LABELS
from utils.css_loader import render_data_badge, render_metric_card, render_page_header
from utils.data_loader import load_sna_data, sna_file_exists
from utils.export_utils import export_to_csv, get_export_filename

# Platform dan warna yang digunakan pada seluruh halaman SNA.
PLATFORM_OPTIONS = {
    "Semua Platform": "all",
    "Twitter/X": "twitter",
    "Instagram": "instagram",
    "TikTok": "tiktok",
}
PLATFORM_ORDER = ["twitter", "instagram", "tiktok"]
PLATFORM_GRAPH_COLORS = {
    "twitter": "#1DA1F2",
    "instagram": "#833AB4",
    "tiktok": "#222222",
    "target": "#E53935",
    "unknown": "#64748B",
}
PLATFORM_DISPLAY = {
    "twitter": "Twitter/X",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "target": "Target/Brand",
    "unknown": "Tidak diketahui",
}

# Akun resmi/brand dipisahkan agar tidak menutupi influencer non-brand.
BRAND_ALIASES = {
    "indihome",
    "indihomecare",
    "myindihome",
    "indibiz",
    "indibizid",
    "telkomsel",
    "telkomselcare",
    "telkomindonesia",
    "telkom",
}

REQUIRED_SNA_COLUMNS = {"source", "target", "relationship", "followers", "platform"}


def _is_dark_mode() -> bool:
    """Ambil status mode gelap dari session secara aman."""
    try:
        return bool(st.session_state.get("dark_mode", True))
    except Exception:
        return True


def _normalize_username(value: Any) -> str:
    """Bersihkan username dari spasi, apostrof, dan awalan @."""
    try:
        username = str(value or "").strip().lstrip("'").strip()
        return username.lstrip("@").strip()
    except Exception:
        return ""


def _normalize_platform(value: Any) -> str:
    """Normalisasi nama platform ke twitter, instagram, atau tiktok."""
    try:
        platform = str(value or "").lower().strip()
        aliases = {
            "x": "twitter",
            "twitter/x": "twitter",
            "twitter": "twitter",
            "ig": "instagram",
            "instagram": "instagram",
            "tik tok": "tiktok",
            "tiktok": "tiktok",
        }
        return aliases.get(platform, platform if platform else "unknown")
    except Exception:
        return "unknown"


def _is_brand_account(username: str) -> bool:
    """Tentukan apakah username merupakan akun resmi/brand penelitian."""
    try:
        normalized = "".join(char for char in username.lower() if char.isalnum())
        return normalized in BRAND_ALIASES
    except Exception:
        return False


def _prepare_sna_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Validasi dan bersihkan data SNA sebelum membangun graf."""
    try:
        if df is None or df.empty:
            return pd.DataFrame(columns=sorted(REQUIRED_SNA_COLUMNS))

        missing = sorted(REQUIRED_SNA_COLUMNS.difference(df.columns))
        if missing:
            raise ValueError(f"Kolom wajib belum tersedia: {', '.join(missing)}")

        work = df.copy()
        work["source"] = work["source"].apply(_normalize_username)
        work["target"] = work["target"].apply(_normalize_username)
        work["relationship"] = (
            work["relationship"].fillna("interaction").astype(str).str.lower().str.strip()
        )
        work["platform"] = work["platform"].apply(_normalize_platform)
        work["followers"] = (
            pd.to_numeric(work["followers"], errors="coerce")
            .fillna(0)
            .clip(lower=0)
            .astype(int)
        )

        invalid = {"", "nan", "none", "null"}
        work = work[
            ~work["source"].str.lower().isin(invalid)
            & ~work["target"].str.lower().isin(invalid)
        ].copy()

        return work.reset_index(drop=True)
    except Exception as exc:
        st.error(f"Gagal menyiapkan data SNA: {exc}")
        return pd.DataFrame(columns=sorted(REQUIRED_SNA_COLUMNS))


@st.cache_data(show_spinner=False)
def _aggregate_edges(df: pd.DataFrame) -> pd.DataFrame:
    """Gabungkan edge berulang dan simpan frekuensinya sebagai weight."""
    try:
        if df is None or df.empty:
            return pd.DataFrame(
                columns=["source", "target", "relationship", "platform", "weight"]
            )

        grouped = (
            df.groupby(["source", "target"], as_index=False, sort=False)
            .agg(
                relationship=("relationship", "first"),
                platform=("platform", "first"),
                weight=("relationship", "size"),
            )
            .reset_index(drop=True)
        )
        grouped["weight"] = pd.to_numeric(grouped["weight"], errors="coerce").fillna(1)
        return grouped
    except Exception as exc:
        st.error(f"Gagal menggabungkan edge SNA: {exc}")
        return pd.DataFrame(
            columns=["source", "target", "relationship", "platform", "weight"]
        )


def _build_node_metadata(df: pd.DataFrame) -> tuple[dict[str, str], dict[str, int]]:
    """Bangun peta platform dan followers untuk setiap node."""
    try:
        if df is None or df.empty:
            return {}, {}

        source_platform = (
            df.groupby("source", sort=False)["platform"].first().astype(str).to_dict()
        )
        target_platform = (
            df.groupby("target", sort=False)["platform"].first().astype(str).to_dict()
        )
        followers_map = (
            df.groupby("source", sort=False)["followers"].max().fillna(0).astype(int).to_dict()
        )

        platform_map = dict(target_platform)
        platform_map.update(source_platform)
        return platform_map, followers_map
    except Exception as exc:
        st.error(f"Gagal membangun metadata node: {exc}")
        return {}, {}


@st.cache_data(show_spinner=False)
def _analyze_network(
    clean_df: pd.DataFrame,
) -> tuple[nx.DiGraph, pd.DataFrame, pd.DataFrame, dict[str, float]]:
    """Bangun DiGraph, hitung metrik jaringan, dan susun tabel node."""
    try:
        graph = nx.DiGraph()
        if clean_df is None or clean_df.empty:
            return graph, pd.DataFrame(), pd.DataFrame(), {
                "total_nodes": 0,
                "total_edges": 0,
                "density": 0.0,
                "avg_degree": 0.0,
            }

        edge_df = _aggregate_edges(clean_df)
        platform_map, followers_map = _build_node_metadata(clean_df)

        for row in edge_df.itertuples(index=False):
            graph.add_edge(
                row.source,
                row.target,
                relationship=row.relationship,
                platform=row.platform,
                weight=int(row.weight),
            )

        degree_centrality = nx.degree_centrality(graph) if graph.number_of_nodes() > 1 else {}
        rows: list[dict[str, Any]] = []
        for username in graph.nodes:
            is_brand = _is_brand_account(username)
            raw_platform = platform_map.get(username, "unknown")
            platform_group = "target" if is_brand else raw_platform
            rows.append(
                {
                    "username": username,
                    "platform": raw_platform,
                    "platform_group": platform_group,
                    "platform_label": PLATFORM_DISPLAY.get(
                        platform_group,
                        str(platform_group).title(),
                    ),
                    "followers": int(followers_map.get(username, 0)),
                    "degree": int(graph.degree(username)),
                    "degree_centrality": float(degree_centrality.get(username, 0.0)),
                    "in_degree": int(graph.in_degree(username)),
                    "out_degree": int(graph.out_degree(username)),
                    "is_brand": bool(is_brand),
                }
            )

        node_df = pd.DataFrame(rows)
        if not node_df.empty:
            node_df = node_df.sort_values(
                ["degree_centrality", "followers", "username"],
                ascending=[False, False, True],
            ).reset_index(drop=True)

        n_nodes = graph.number_of_nodes()
        n_edges = graph.number_of_edges()
        summary = {
            "total_nodes": int(n_nodes),
            "total_edges": int(n_edges),
            "density": float(nx.density(graph)) if n_nodes > 1 else 0.0,
            "avg_degree": (
                float(sum(dict(graph.degree()).values()) / n_nodes) if n_nodes else 0.0
            ),
        }
        return graph, node_df, edge_df, summary
    except Exception as exc:
        st.error(f"Gagal menghitung metrik jaringan: {exc}")
        return nx.DiGraph(), pd.DataFrame(), pd.DataFrame(), {
            "total_nodes": 0,
            "total_edges": 0,
            "density": 0.0,
            "avg_degree": 0.0,
        }


def _apply_plotly_theme(fig: go.Figure, title: str = "") -> go.Figure:
    """Terapkan tema Plotly yang konsisten dengan dashboard."""
    try:
        dark_mode = _is_dark_mode()
        text_color = "#F8FAFC" if dark_mode else "#1F2937"
        muted_color = "#A7B0BF" if dark_mode else "#64748B"
        grid_color = "rgba(167,176,191,0.20)" if dark_mode else "rgba(100,116,139,0.18)"

        fig.update_layout(
            template="plotly_dark" if dark_mode else "plotly_white",
            title={"text": title, "x": 0.0, "xanchor": "left"},
            font={"family": "Inter, Arial, sans-serif", "color": text_color},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin={"l": 35, "r": 20, "t": 60 if title else 30, "b": 45},
            hoverlabel={
                "bgcolor": "#151B26" if dark_mode else "#FFFFFF",
                "font_color": text_color,
            },
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1,
            },
        )
        fig.update_xaxes(
            color=text_color,
            tickfont={"color": muted_color},
            gridcolor=grid_color,
            zeroline=False,
        )
        fig.update_yaxes(
            color=text_color,
            tickfont={"color": muted_color},
            gridcolor=grid_color,
            zeroline=False,
        )
        return fig
    except Exception as exc:
        st.error(f"Gagal menerapkan tema grafik: {exc}")
        return fig


def _render_metric_cards(summary: dict[str, float]) -> None:
    """Tampilkan empat kartu metrik utama jaringan."""
    try:
        columns = st.columns(4)
        cards = [
            (
                "Total Node",
                f"{int(summary.get('total_nodes', 0)):,}".replace(",", "."),
                "Akun unik dalam graf",
                "👤",
            ),
            (
                "Total Edge",
                f"{int(summary.get('total_edges', 0)):,}".replace(",", "."),
                "Relasi unik berarah",
                "🔗",
            ),
            (
                "Density",
                f"{float(summary.get('density', 0.0)):.6f}",
                "Kepadatan koneksi jaringan",
                "🕸️",
            ),
            (
                "Avg Degree",
                f"{float(summary.get('avg_degree', 0.0)):.2f}",
                "Rata-rata koneksi per node",
                "📐",
            ),
        ]
        for column, (title, value, delta, icon) in zip(columns, cards):
            with column:
                render_metric_card(title, value, delta, icon)
    except Exception as exc:
        st.error(f"Gagal menampilkan kartu statistik jaringan: {exc}")


def _display_node_table(df: pd.DataFrame, key: str, height: int = 380) -> None:
    """Tampilkan tabel node dengan format angka yang mudah dibaca."""
    try:
        if df is None or df.empty:
            st.info("Belum ada data akun untuk ditampilkan.")
            return

        table = df.copy()
        rename_map = {
            "username": "Username",
            "platform_label": "Platform",
            "followers": "Followers",
            "degree": "Degree",
            "degree_centrality": "Degree Centrality",
            "in_degree": "In-Degree",
            "out_degree": "Out-Degree",
            "category": "Kategori",
        }
        selected = [column for column in rename_map if column in table.columns]
        table = table[selected].rename(columns=rename_map)

        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
            height=height,
            column_config={
                "Followers": st.column_config.NumberColumn(format="%d"),
                "Degree": st.column_config.NumberColumn(format="%d"),
                "Degree Centrality": st.column_config.NumberColumn(format="%.6f"),
                "In-Degree": st.column_config.NumberColumn(format="%d"),
                "Out-Degree": st.column_config.NumberColumn(format="%d"),
            },
        )
    except Exception as exc:
        st.error(f"Gagal menampilkan tabel akun: {exc}")


def _create_degree_bar_chart(top_degree: pd.DataFrame) -> go.Figure:
    """Buat horizontal bar chart akun dengan degree centrality tertinggi."""
    try:
        if top_degree is None or top_degree.empty:
            return _apply_plotly_theme(go.Figure(), "Top Degree Centrality")

        chart_df = top_degree.sort_values("degree_centrality", ascending=True).copy()
        fig = px.bar(
            chart_df,
            x="degree_centrality",
            y="username",
            orientation="h",
            color="platform_group",
            color_discrete_map=PLATFORM_GRAPH_COLORS,
            labels={
                "degree_centrality": "Degree Centrality",
                "username": "Username",
                "platform_group": "Platform",
            },
            hover_data={
                "degree": True,
                "in_degree": True,
                "out_degree": True,
                "followers": ":,",
            },
        )
        fig.update_layout(showlegend=False, height=430)
        return _apply_plotly_theme(fig, "Top 10 Degree Centrality")
    except Exception as exc:
        st.error(f"Gagal membuat grafik degree centrality: {exc}")
        return _apply_plotly_theme(go.Figure(), "Top Degree Centrality")


def _create_followers_bar_chart(top_followers: pd.DataFrame) -> go.Figure:
    """Buat horizontal bar chart akun dengan followers terbesar."""
    try:
        if top_followers is None or top_followers.empty:
            return _apply_plotly_theme(go.Figure(), "Top Followers")

        chart_df = top_followers.sort_values("followers", ascending=True).copy()
        fig = px.bar(
            chart_df,
            x="followers",
            y="username",
            orientation="h",
            color="platform_group",
            color_discrete_map=PLATFORM_GRAPH_COLORS,
            labels={
                "followers": "Jumlah Followers",
                "username": "Username",
                "platform_group": "Platform",
            },
            hover_data={"degree_centrality": ":.6f", "degree": True},
        )
        fig.update_layout(showlegend=False, height=430)
        fig.update_xaxes(tickformat=",")
        return _apply_plotly_theme(fig, "Top 10 Followers")
    except Exception as exc:
        st.error(f"Gagal membuat grafik followers: {exc}")
        return _apply_plotly_theme(go.Figure(), "Top Followers")


def _create_degree_histogram(node_df: pd.DataFrame) -> go.Figure:
    """Buat histogram distribusi degree seluruh node."""
    try:
        if node_df is None or node_df.empty:
            return _apply_plotly_theme(go.Figure(), "Distribusi Degree")

        fig = px.histogram(
            node_df,
            x="degree",
            nbins=40,
            labels={"degree": "Total Degree", "count": "Jumlah Node"},
            color_discrete_sequence=["#1DA1F2"],
        )
        fig.update_traces(hovertemplate="Degree: %{x}<br>Jumlah node: %{y}<extra></extra>")
        fig.update_layout(height=380, bargap=0.05)
        return _apply_plotly_theme(fig, "Histogram Distribusi Degree")
    except Exception as exc:
        st.error(f"Gagal membuat histogram degree: {exc}")
        return _apply_plotly_theme(go.Figure(), "Distribusi Degree")


def _render_statistics_tab(node_df: pd.DataFrame, summary: dict[str, float]) -> None:
    """Render Tab 1 berisi statistik jaringan dan ranking utama."""
    try:
        _render_metric_cards(summary)
        st.markdown("---")

        top_degree = node_df.head(10).copy() if not node_df.empty else pd.DataFrame()
        left, right = st.columns([1.05, 1.45])
        with left:
            st.subheader("🏆 Top 10 Degree Centrality")
            st.caption(
                "Akun target/brand tetap ditampilkan pada statistik struktur, "
                "tetapi dikeluarkan dari tabel influencer pada Tab 3."
            )
            _display_node_table(top_degree, "sna_top_degree_table", height=420)
        with right:
            st.plotly_chart(
                _create_degree_bar_chart(top_degree),
                use_container_width=True,
                config={"displayModeBar": False},
            )

        st.markdown("---")
        followers_pool = node_df[node_df["followers"] > 0].copy()
        top_followers = followers_pool.nlargest(10, "followers")
        left, right = st.columns([1.05, 1.45])
        with left:
            st.subheader("📣 Top 10 Followers Terbesar")
            st.caption(
                "Followers menunjukkan potensi jangkauan akun, bukan bukti tunggal pengaruh."
            )
            _display_node_table(top_followers, "sna_top_followers_table", height=420)
        with right:
            st.plotly_chart(
                _create_followers_bar_chart(top_followers),
                use_container_width=True,
                config={"displayModeBar": False},
            )

        st.markdown("---")
        st.subheader("📊 Distribusi Degree")
        st.plotly_chart(
            _create_degree_histogram(node_df),
            use_container_width=True,
            config={"displayModeBar": False},
        )
        st.caption(
            "Batang paling tinggi pada degree rendah menandakan banyak akun hanya memiliki "
            "sedikit interaksi langsung, karakter yang umum pada jaringan hub-and-spoke."
        )
    except Exception as exc:
        st.error(f"Gagal menampilkan Tab Statistik Jaringan: {exc}")


def _build_visual_graph(
    edge_df: pd.DataFrame,
    node_df: pd.DataFrame,
    platform: str,
    node_limit: int,
) -> tuple[nx.DiGraph, pd.DataFrame]:
    """Buat subgraf visual berdasarkan platform dan batas jumlah node."""
    try:
        if edge_df is None or edge_df.empty:
            return nx.DiGraph(), pd.DataFrame()

        filtered_edges = edge_df.copy()
        if platform != "all":
            filtered_edges = filtered_edges[filtered_edges["platform"] == platform].copy()
        if filtered_edges.empty:
            return nx.DiGraph(), pd.DataFrame()

        full_graph = nx.DiGraph()
        for row in filtered_edges.itertuples(index=False):
            full_graph.add_edge(
                row.source,
                row.target,
                relationship=row.relationship,
                platform=row.platform,
                weight=int(row.weight),
            )

        degree_cent = (
            nx.degree_centrality(full_graph) if full_graph.number_of_nodes() > 1 else {}
        )
        ranking = sorted(
            full_graph.nodes,
            key=lambda node: (
                _is_brand_account(node),
                degree_cent.get(node, 0.0),
                full_graph.degree(node),
            ),
            reverse=True,
        )
        selected_nodes = ranking[: max(1, int(node_limit))]
        visual_graph = full_graph.subgraph(selected_nodes).copy()

        node_lookup = node_df.set_index("username") if not node_df.empty else pd.DataFrame()
        visual_rows: list[dict[str, Any]] = []
        local_cent = (
            nx.degree_centrality(visual_graph)
            if visual_graph.number_of_nodes() > 1
            else {}
        )
        for username in visual_graph.nodes:
            if not node_lookup.empty and username in node_lookup.index:
                metadata = node_lookup.loc[username]
                platform_group = str(metadata.get("platform_group", "unknown"))
                followers = int(metadata.get("followers", 0))
            else:
                platform_group = "target" if _is_brand_account(username) else platform
                followers = 0

            if _is_brand_account(username):
                platform_group = "target"

            visual_rows.append(
                {
                    "username": username,
                    "platform_group": platform_group,
                    "platform_label": PLATFORM_DISPLAY.get(
                        platform_group,
                        str(platform_group).title(),
                    ),
                    "followers": followers,
                    "degree": int(visual_graph.degree(username)),
                    "degree_centrality": float(local_cent.get(username, 0.0)),
                    "in_degree": int(visual_graph.in_degree(username)),
                    "out_degree": int(visual_graph.out_degree(username)),
                }
            )

        return visual_graph, pd.DataFrame(visual_rows)
    except Exception as exc:
        st.error(f"Gagal menyiapkan subgraf visual: {exc}")
        return nx.DiGraph(), pd.DataFrame()


def _pyvis_html(graph: nx.DiGraph, visual_nodes: pd.DataFrame) -> str:
    """Konversi graf NetworkX menjadi HTML PyVis interaktif."""
    try:
        if graph.number_of_nodes() == 0:
            return ""

        dark_mode = _is_dark_mode()
        background = "#0B1220" if dark_mode else "#FFFFFF"
        font_color = "#F8FAFC" if dark_mode else "#1F2937"
        network = Network(
            height="500px",
            width="100%",
            directed=True,
            bgcolor=background,
            font_color=font_color,
            cdn_resources="in_line",
        )

        node_lookup = visual_nodes.set_index("username")
        max_centrality = max(
            float(visual_nodes["degree_centrality"].max()),
            0.000001,
        )

        for username in graph.nodes:
            row = node_lookup.loc[username]
            centrality = float(row["degree_centrality"])
            relative = centrality / max_centrality
            size = 13 + (relative * 37)
            platform_group = str(row["platform_group"])
            color = PLATFORM_GRAPH_COLORS.get(platform_group, "#64748B")
            label = username if len(username) <= 24 else f"{username[:21]}..."
            title = (
                f"<b>{escape(username)}</b><br>"
                f"Platform: {escape(str(row['platform_label']))}<br>"
                f"Followers: {int(row['followers']):,}<br>"
                f"Degree Centrality: {centrality:.6f}<br>"
                f"In-Degree: {int(row['in_degree'])}<br>"
                f"Out-Degree: {int(row['out_degree'])}"
            )
            network.add_node(
                username,
                label=label,
                title=title,
                color={
                    "background": color,
                    "border": "#E5E7EB" if platform_group == "tiktok" else color,
                    "highlight": {"background": color, "border": "#FFFFFF"},
                },
                size=size,
                borderWidth=2 if platform_group == "target" else 1,
                shape="dot",
                font={"color": font_color, "size": 13},
            )

        for source, target, attributes in graph.edges(data=True):
            weight = int(attributes.get("weight", 1))
            relation = str(attributes.get("relationship", "interaction"))
            network.add_edge(
                source,
                target,
                title=f"Relasi: {escape(relation)}<br>Frekuensi: {weight}",
                value=max(1, min(weight, 8)),
                color={"color": "#94A3B8", "opacity": 0.55},
                arrows="to",
            )

        network.set_options(
            """
            var options = {
              "interaction": {
                "hover": true,
                "tooltipDelay": 120,
                "navigationButtons": true,
                "keyboard": true,
                "hideEdgesOnDrag": true
              },
              "physics": {
                "enabled": true,
                "solver": "forceAtlas2Based",
                "forceAtlas2Based": {
                  "gravitationalConstant": -70,
                  "centralGravity": 0.012,
                  "springLength": 115,
                  "springConstant": 0.07,
                  "damping": 0.55,
                  "avoidOverlap": 0.65
                },
                "stabilization": {
                  "enabled": true,
                  "iterations": 450,
                  "updateInterval": 25,
                  "fit": true
                }
              },
              "edges": {
                "smooth": {"enabled": true, "type": "dynamic"},
                "selectionWidth": 2
              }
            }
            """
        )
        return network.generate_html(notebook=False)
    except Exception as exc:
        raise RuntimeError(f"PyVis gagal membuat HTML graf: {exc}") from exc


def _render_networkx_fallback(graph: nx.DiGraph, visual_nodes: pd.DataFrame) -> None:
    """Render fallback graf statis NetworkX menggunakan Matplotlib."""
    try:
        if graph.number_of_nodes() == 0:
            st.info("Tidak ada node yang dapat divisualisasikan.")
            return

        node_lookup = visual_nodes.set_index("username")
        max_centrality = max(
            float(visual_nodes["degree_centrality"].max()),
            0.000001,
        )
        node_sizes = []
        node_colors = []
        for username in graph.nodes:
            row = node_lookup.loc[username]
            relative = float(row["degree_centrality"]) / max_centrality
            node_sizes.append(220 + relative * 1500)
            node_colors.append(
                PLATFORM_GRAPH_COLORS.get(str(row["platform_group"]), "#64748B")
            )

        fig, ax = plt.subplots(figsize=(14, 8))
        position = nx.spring_layout(graph, seed=42, k=0.75)
        nx.draw_networkx_edges(
            graph,
            position,
            ax=ax,
            arrows=True,
            alpha=0.35,
            width=0.8,
            arrowsize=11,
        )
        nx.draw_networkx_nodes(
            graph,
            position,
            ax=ax,
            node_size=node_sizes,
            node_color=node_colors,
            alpha=0.92,
        )
        labels = {
            username: username if len(username) <= 18 else f"{username[:15]}..."
            for username in graph.nodes
        }
        nx.draw_networkx_labels(graph, position, labels=labels, font_size=7, ax=ax)
        ax.set_axis_off()
        fig.tight_layout()
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    except Exception as exc:
        st.error(f"Fallback NetworkX juga gagal ditampilkan: {exc}")


def _render_graph_legend() -> None:
    """Tampilkan legenda warna node pada visualisasi graf."""
    try:
        items = [
            ("#1DA1F2", "Twitter/X"),
            ("#833AB4", "Instagram"),
            ("#222222", "TikTok"),
            ("#E53935", "Target/Brand"),
        ]
        legend = "".join(
            (
                '<span style="display:inline-flex;align-items:center;gap:6px;'
                'margin:4px 16px 4px 0;font-size:0.88rem;">'
                f'<span style="width:11px;height:11px;border-radius:50%;background:{color};'
                'display:inline-block;border:1px solid rgba(255,255,255,.25);"></span>'
                f"{label}</span>"
            )
            for color, label in items
        )
        st.markdown(
            f'<div style="padding:8px 2px 2px 2px;">{legend}</div>',
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.error(f"Gagal menampilkan legenda graf: {exc}")


def _render_graph_tab(
    edge_df: pd.DataFrame,
    node_df: pd.DataFrame,
    platform: str,
    node_limit: int,
) -> None:
    """Render Tab 2 berisi graf jaringan interaktif PyVis."""
    try:
        st.subheader("🕸️ Peta Jaringan Interaktif")
        st.caption(
            "Arah panah menunjukkan source → target. Geser node untuk mengatur posisi, "
            "scroll untuk zoom, dan arahkan kursor ke node untuk melihat detail."
        )

        graph, visual_nodes = _build_visual_graph(
            edge_df=edge_df,
            node_df=node_df,
            platform=platform,
            node_limit=node_limit,
        )
        if graph.number_of_nodes() == 0:
            st.info("Tidak ada data graf pada filter platform yang dipilih.")
            return

        info_1, info_2, info_3 = st.columns(3)
        info_1.metric("Node Ditampilkan", graph.number_of_nodes())
        info_2.metric("Edge Ditampilkan", graph.number_of_edges())
        info_3.metric(
            "Platform",
            "Semua" if platform == "all" else PLATFORM_LABELS.get(platform, platform.title()),
        )

        try:
            html = _pyvis_html(graph, visual_nodes)
            if not html:
                raise RuntimeError("HTML PyVis kosong.")
            components.html(html, height=525, scrolling=False)
        except Exception as pyvis_exc:
            st.warning(
                "Visualisasi interaktif PyVis tidak berhasil dimuat. "
                "Dashboard menampilkan graf statis sebagai pengganti."
            )
            st.caption(f"Detail teknis: {pyvis_exc}")
            _render_networkx_fallback(graph, visual_nodes)

        _render_graph_legend()
        st.caption(
            "Ukuran node mengikuti degree centrality pada subgraf yang sedang ditampilkan. "
            "Akun target/brand diberi warna merah agar mudah dibedakan."
        )
    except Exception as exc:
        st.error(f"Gagal menampilkan Tab Visualisasi Graf: {exc}")


def _assign_influencer_categories(node_df: pd.DataFrame) -> pd.DataFrame:
    """Tentukan kategori influencer berdasarkan aturan per platform."""
    try:
        if node_df is None or node_df.empty:
            return pd.DataFrame()

        result = node_df[~node_df["is_brand"]].copy()
        result = result[result["platform"].isin(PLATFORM_ORDER)].copy()
        result["category"] = "Akun Partisipan"

        for platform in PLATFORM_ORDER:
            mask = result["platform"] == platform
            subset = result.loc[mask]
            if subset.empty:
                continue

            if platform == "twitter":
                average_degree = float(subset["degree"].mean())
                result.loc[mask & (result["degree"] > average_degree), "category"] = (
                    "Structural Influencer"
                )
            else:
                average_followers = float(subset["followers"].mean())
                result.loc[
                    mask & (result["followers"] > average_followers),
                    "category",
                ] = "Reach Influencer"

        category_priority = {
            "Structural Influencer": 0,
            "Reach Influencer": 0,
            "Akun Partisipan": 1,
        }
        result["_category_order"] = result["category"].map(category_priority).fillna(9)
        result = result.sort_values(
            ["_category_order", "degree_centrality", "followers", "username"],
            ascending=[True, False, False, True],
        ).drop(columns="_category_order")
        return result.reset_index(drop=True)
    except Exception as exc:
        st.error(f"Gagal menentukan kategori influencer: {exc}")
        return pd.DataFrame()


def _filter_influencer_table(influencer_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Filter dan urutkan tabel influencer berdasarkan platform."""
    try:
        if influencer_df is None or influencer_df.empty:
            return pd.DataFrame()

        filtered = influencer_df.copy()
        if platform != "all":
            filtered = filtered[filtered["platform"] == platform].copy()

        if platform == "twitter":
            filtered = filtered.sort_values(
                ["degree_centrality", "followers"], ascending=[False, False]
            )
        elif platform in {"instagram", "tiktok"}:
            filtered = filtered.sort_values(
                ["followers", "degree_centrality"], ascending=[False, False]
            )
        else:
            filtered = filtered.sort_values(
                ["category", "degree_centrality", "followers"],
                ascending=[True, False, False],
            )
        return filtered.reset_index(drop=True)
    except Exception as exc:
        st.error(f"Gagal memfilter tabel influencer: {exc}")
        return pd.DataFrame()


def _export_influencer_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Siapkan kolom tabel influencer untuk ekspor CSV."""
    try:
        if df is None or df.empty:
            return pd.DataFrame()
        export_df = df[
            [
                "username",
                "platform_label",
                "followers",
                "degree_centrality",
                "in_degree",
                "out_degree",
                "category",
            ]
        ].copy()
        return export_df.rename(
            columns={
                "username": "Username",
                "platform_label": "Platform",
                "followers": "Followers",
                "degree_centrality": "Degree Centrality",
                "in_degree": "In-Degree",
                "out_degree": "Out-Degree",
                "category": "Kategori",
            }
        )
    except Exception as exc:
        st.error(f"Gagal menyiapkan data ekspor influencer: {exc}")
        return pd.DataFrame()


def _render_influencer_tab(influencer_df: pd.DataFrame) -> None:
    """Render Tab 3 berisi identifikasi influencer dan ekspor CSV."""
    try:
        st.subheader("🌟 Identifikasi Influencer")
        filter_label = st.selectbox(
            "Filter platform influencer",
            options=list(PLATFORM_OPTIONS.keys()),
            index=0,
            key="sna_influencer_platform",
        )
        selected_platform = PLATFORM_OPTIONS[filter_label]
        filtered = _filter_influencer_table(influencer_df, selected_platform)

        if filtered.empty:
            st.info("Tidak ada influencer pada platform yang dipilih.")
            return

        influencer_count = int(
            filtered["category"].isin(
                ["Structural Influencer", "Reach Influencer"]
            ).sum()
        )
        metric_1, metric_2, metric_3 = st.columns(3)
        metric_1.metric("Akun Non-Brand", f"{len(filtered):,}".replace(",", "."))
        metric_2.metric("Teridentifikasi Influencer", influencer_count)
        metric_3.metric(
            "Followers Tertinggi",
            f"{int(filtered['followers'].max()):,}".replace(",", "."),
        )

        st.info(
            "Aturan kategori: Twitter/X menjadi Structural Influencer bila total degree "
            "di atas rata-rata platform. Instagram dan TikTok menjadi Reach Influencer "
            "bila followers di atas rata-rata platform. Akun brand/target tidak dimasukkan."
        )

        _display_node_table(filtered, "sna_influencer_table", height=510)

        export_df = _export_influencer_dataframe(filtered)
        platform_filename = "semua" if selected_platform == "all" else selected_platform
        st.download_button(
            label="⬇️ Export CSV Influencer",
            data=export_to_csv(export_df, "influencer_sna"),
            file_name=get_export_filename(
                "influencer_sna",
                platform=platform_filename,
                ext="csv",
            ),
            mime="text/csv",
            use_container_width=True,
            key="download_sna_influencer_csv",
        )
        st.caption(
            "File CSV mengikuti filter platform yang sedang aktif dan memakai encoding UTF-8."
        )
    except Exception as exc:
        st.error(f"Gagal menampilkan Tab Identifikasi Influencer: {exc}")


def _create_followers_degree_scatter(node_df: pd.DataFrame) -> go.Figure:
    """Buat scatter plot followers terhadap degree centrality."""
    try:
        if node_df is None or node_df.empty:
            return _apply_plotly_theme(go.Figure(), "Followers vs Degree Centrality")

        plot_df = node_df[~node_df["is_brand"]].copy()
        plot_df = plot_df[plot_df["platform"].isin(PLATFORM_ORDER)].copy()
        plot_df["platform_label"] = plot_df["platform"].map(PLATFORM_LABELS)

        fig = px.scatter(
            plot_df,
            x="followers",
            y="degree_centrality",
            color="platform",
            color_discrete_map=PLATFORM_COLORS,
            hover_name="username",
            hover_data={
                "platform_label": True,
                "followers": ":,",
                "degree_centrality": ":.6f",
                "in_degree": True,
                "out_degree": True,
                "platform": False,
            },
            labels={
                "followers": "Jumlah Followers",
                "degree_centrality": "Degree Centrality",
                "platform": "Platform",
                "platform_label": "Platform",
            },
            opacity=0.72,
            render_mode="webgl",
        )
        fig.update_traces(marker={"size": 8, "line": {"width": 0.4, "color": "white"}})
        fig.update_layout(height=520)
        fig.update_xaxes(tickformat=",")
        return _apply_plotly_theme(fig, "Followers vs Degree Centrality")
    except Exception as exc:
        st.error(f"Gagal membuat scatter plot metrik: {exc}")
        return _apply_plotly_theme(go.Figure(), "Followers vs Degree Centrality")


def _render_metric_explanation_tab(node_df: pd.DataFrame) -> None:
    """Render Tab 4 berisi rumus, batasan metrik, dan scatter plot."""
    try:
        st.subheader("📘 Degree Centrality")
        st.latex(r"C_D(v) = \frac{deg(v)}{|V| - 1}")
        st.markdown(
            "**Keterangan:** `deg(v)` adalah jumlah koneksi langsung yang dimiliki node `v`, "
            "sedangkan `|V|` adalah jumlah seluruh node pada jaringan. Pada graf berarah, "
            "degree terdiri dari **in-degree** dan **out-degree**."
        )

        st.markdown("---")
        left, right = st.columns(2)
        with left:
            st.markdown(
                """
                ### Mengapa Closeness tidak digunakan?
                Struktur jaringan penelitian cenderung **hub-and-spoke**. Banyak akun hanya
                terhubung ke akun pusat dan tidak memiliki jalur timbal balik ke seluruh node.
                Karena graf tidak *strongly connected*, banyak pasangan node tidak mempunyai
                jalur terpendek yang representatif. Nilai closeness dapat menjadi nol, seragam,
                atau sulit ditafsirkan untuk identifikasi influencer pada jaringan ini.
                """
            )
        with right:
            st.markdown(
                """
                ### Mengapa Betweenness tidak digunakan?
                Sebagian besar interaksi berlangsung langsung antara pengguna dan akun target.
                Jalur alternatif serta diskusi berantai antar pengguna sangat terbatas, sehingga
                hampir tidak ada node yang konsisten berperan sebagai jembatan. Betweenness
                akhirnya terpusat pada akun target atau bernilai nol pada mayoritas node dan tidak
                memberi informasi tambahan yang kuat untuk ranking influencer.
                """
            )

        st.markdown("---")
        st.subheader("📈 Hubungan Followers dan Degree Centrality")
        st.plotly_chart(
            _create_followers_degree_scatter(node_df),
            use_container_width=True,
            config={"displayModeBar": False},
        )
        st.caption(
            "Titik di kanan memiliki jangkauan followers lebih besar, sedangkan titik lebih tinggi "
            "memiliki posisi struktural lebih kuat. Kedua indikator perlu dibaca bersama, bukan "
            "sebagai hubungan sebab-akibat."
        )
    except Exception as exc:
        st.error(f"Gagal menampilkan Tab Penjelasan Metrik: {exc}")


def _render_sidebar_graph_filters() -> tuple[str, int]:
    """Render filter sidebar khusus visualisasi graf."""
    try:
        st.sidebar.markdown("### 🕸️ Filter Graf SNA")
        platform_label = st.sidebar.selectbox(
            "Platform visualisasi",
            options=list(PLATFORM_OPTIONS.keys()),
            index=0,
            key="sna_graph_platform",
            help="Filter ini hanya memengaruhi graf pada Tab Visualisasi Graf.",
        )
        node_limit = st.sidebar.slider(
            "Jumlah node ditampilkan",
            min_value=20,
            max_value=120,
            value=60,
            step=10,
            key="sna_graph_node_limit",
            help="Semakin banyak node, graf akan semakin padat dan membutuhkan waktu lebih lama.",
        )
        st.sidebar.caption(
            "Filter di atas hanya mengatur visualisasi graf. Statistik dan tabel tetap dihitung "
            "dari seluruh data."
        )
        return PLATFORM_OPTIONS[platform_label], int(node_limit)
    except Exception as exc:
        st.error(f"Gagal menampilkan filter graf: {exc}")
        return "all", 60


def render_sna() -> None:
    """Render halaman utama Social Network Analysis."""
    try:
        render_page_header(
            "🕸️ Social Network Analysis",
            "Struktur jaringan, visualisasi graf, dan identifikasi influencer lintas platform",
        )

        badge_col, note_col = st.columns([1, 5])
        with badge_col:
            render_data_badge(sna_file_exists())
        with note_col:
            st.caption(
                "Sumber: data/sna_data.csv. Jika file tidak tersedia atau gagal dibaca, "
                "dashboard otomatis menggunakan dummy data dari utils/dummy_data.py."
            )

        graph_platform, node_limit = _render_sidebar_graph_filters()

        with st.spinner("Membangun jaringan dan menghitung metrik SNA..."):
            raw_df = load_sna_data()
            clean_df = _prepare_sna_dataframe(raw_df)
            _, node_df, edge_df, summary = _analyze_network(clean_df)

        if clean_df.empty or node_df.empty:
            st.warning(
                "Data SNA belum tersedia atau tidak memiliki kolom yang sesuai. "
                "Periksa file data/sna_data.csv."
            )
            return

        tab_statistics, tab_graph, tab_influencer, tab_metrics = st.tabs(
            [
                "📊 Statistik Jaringan",
                "🕸️ Visualisasi Graf",
                "🌟 Identifikasi Influencer",
                "📘 Penjelasan Metrik",
            ]
        )

        with tab_statistics:
            _render_statistics_tab(node_df, summary)

        with tab_graph:
            _render_graph_tab(edge_df, node_df, graph_platform, node_limit)

        with tab_influencer:
            influencer_df = _assign_influencer_categories(node_df)
            _render_influencer_tab(influencer_df)

        with tab_metrics:
            _render_metric_explanation_tab(node_df)
    except Exception as exc:
        st.error(f"Gagal memuat halaman Social Network Analysis: {exc}")
