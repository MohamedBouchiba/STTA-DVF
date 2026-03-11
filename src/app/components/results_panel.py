"""Panneau de resultats professionnel avec ajustements, Plotly et onglets."""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from src.estimation.estimator import EstimationResult
from src.app.models.property_input import PropertyInput
from src.app.models.adjustments import (
    compute_adjustments,
    CoefficientOverrides,
    AdjustmentBreakdown,
)
from src.app.components.map_view import render_map
from src.app.components.stats_panel import render_stats_chart, render_stats_metrics
from src.app.utils.formatting import (
    format_price,
    format_price_m2,
    format_distance,
    confidence_color,
)
from src.app.utils.css import (
    get_plotly_dark_theme,
    BG_DARK,
    BG_CARD,
    BG_SURFACE,
    GOLD,
    GOLD_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    BORDER,
    SUCCESS,
    DANGER,
)

# Couleurs par zone (coherent avec map_view)
ZONE_COLORS = {1: GOLD, 2: "#58A6FF", 3: "#B0BAC6"}


# ---------------------------------------------------------------------------
# Sous-composants
# ---------------------------------------------------------------------------

def _render_price_card(
    price: float,
    prix_m2: float,
    confidence_level: str,
    confidence_label: str,
    nb_comparables: int,
    niveau_geo: str,
    address_label: str,
):
    """Carte de prix enrichie avec synthese."""
    color = confidence_color(confidence_level)
    bg_map = {"high": "rgba(63,185,80,0.15)", "medium": "rgba(212,168,67,0.15)", "low": "rgba(248,81,73,0.15)"}
    bg_pill = bg_map.get(confidence_level, "rgba(139,148,158,0.15)")

    st.markdown(
        f'<div class="result-card">'
        f'<div class="result-price">{format_price(price)}</div>'
        f'<div class="result-price-m2">soit {format_price_m2(prix_m2)}</div>'
        f'<div class="result-confidence" style="color:{color}; background:{bg_pill}; border:1px solid {color};">'
        f"Confiance {confidence_label}"
        f"</div>"
        f'<div style="margin-top:0.8rem; font-size:0.8rem; color:{TEXT_SECONDARY};">'
        f"{nb_comparables} transactions comparables &middot; {niveau_geo}"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_range(low: float, high: float):
    """Fourchette de prix."""
    st.markdown(
        f'<div class="result-range">'
        f"Fourchette estimee : <b>{format_price(low)}</b> &ndash; <b>{format_price(high)}</b>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_summary(
    result: EstimationResult,
    adj: AdjustmentBreakdown,
    has_adjustments: bool,
):
    """Bloc de synthese : metriques cles + ajustements."""
    rows = (
        f'<div class="summary-row">'
        f'<span class="summary-label">Adresse</span>'
        f'<span class="summary-value">{result.geocoding.label}</span></div>'

        f'<div class="summary-row">'
        f'<span class="summary-label">Prix de base DVF</span>'
        f'<span class="summary-value">{format_price(adj.base_price)}</span></div>'

        f'<div class="summary-row">'
        f'<span class="summary-label">Comparables utilises</span>'
        f'<span class="summary-value">{result.nb_comparables}</span></div>'

        f'<div class="summary-row">'
        f'<span class="summary-label">Perimetre</span>'
        f'<span class="summary-value">{result.niveau_geo}</span></div>'
    )

    if has_adjustments:
        delta = adj.total_multiplier - 1.0
        sign = "+" if delta >= 0 else ""
        rows += (
            f'<div class="summary-row">'
            f'<span class="summary-label">Coefficient d\'ajustement</span>'
            f'<span class="summary-value">{adj.total_multiplier:.1%} ({sign}{delta:.1%})</span></div>'
        )

    st.markdown(
        f'<div class="result-summary">'
        f'<div class="summary-title">Synthese de l\'estimation</div>'
        f"{rows}"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Pilules d'ajustements
    if has_adjustments and adj.explanations:
        pills_html = ""
        for expl in adj.explanations:
            if "+" in expl.split(":")[-1]:
                css_class = "adjustment-pill positive"
            elif "-" in expl.split(":")[-1]:
                css_class = "adjustment-pill negative"
            else:
                css_class = "adjustment-pill"
            pills_html += f'<span class="{css_class}">{expl}</span>'

        st.markdown(
            f'<div style="margin: 0.5rem 0 1rem 0;">{pills_html}</div>',
            unsafe_allow_html=True,
        )


def _render_zone_breakdown(result: EstimationResult):
    """Affiche la repartition par zone (uniquement si multi-zones)."""
    if not result.zone_breakdown or not result.zone_config:
        return

    zc = result.zone_config
    zb = result.zone_breakdown
    total_comp = sum(zb.get(z, {}).get("count", 0) for z in [1, 2, 3])

    zone_labels = {
        1: f"Zone 1 &mdash; 0 a {zc.radius_1_km} km",
        2: f"Zone 2 &mdash; {zc.radius_1_km} a {zc.radius_2_km} km",
        3: f"Zone 3 &mdash; {zc.radius_2_km} a {zc.radius_3_km} km",
    }

    zone_title_colors = {1: GOLD, 2: "#58A6FF", 3: "#B0BAC6"}

    cards_html = ""
    for z in [1, 2, 3]:
        info = zb.get(z, {})
        count = info.get("count", 0)
        median = info.get("median_prix_m2")
        eff_weight = info.get("effective_weight", 0)
        color = zone_title_colors[z]

        median_str = format_price_m2(median) if median else "—"
        weight_str = f"{eff_weight:.0%}" if eff_weight else "0%"
        pct_comp = f"{count / total_comp:.0%}" if total_comp > 0 else "—"

        cards_html += (
            f'<div class="zone-breakdown-card" style="border-top: 3px solid {color};">'
            f'<div class="zb-title" style="color:{color};">{zone_labels[z]}</div>'
            f'<div class="zb-value">{median_str}</div>'
            f'<div class="zb-detail">'
            f'{count} comparables ({pct_comp})<br>'
            f'Poids effectif : <b style="color:{color};">{weight_str}</b>'
            f'</div>'
            f'</div>'
        )

    st.markdown(
        f'<div class="chart-title">Repartition par zone &mdash; {total_comp} comparables</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="zone-breakdown">{cards_html}</div>',
        unsafe_allow_html=True,
    )


def _render_gauge(price: float, low: float, high: float):
    """Jauge Plotly positionnant le prix dans la fourchette."""
    theme = get_plotly_dark_theme()
    spread = (high - low) * 0.20
    gauge_min = max(0, low - spread)
    gauge_max = high + spread

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=price,
        title=dict(
            text="Estimation",
            font=dict(size=14, color=TEXT_SECONDARY),
        ),
        number=dict(
            suffix=" EUR",
            font=dict(size=32, color=GOLD),
            valueformat=",.0f",
        ),
        gauge=dict(
            axis=dict(
                range=[gauge_min, gauge_max],
                tickformat=",.0f",
                tickfont=dict(color=TEXT_SECONDARY, size=11),
                nticks=6,
            ),
            bar=dict(color=GOLD, thickness=0.35),
            bgcolor=BG_CARD,
            borderwidth=1,
            bordercolor=BORDER,
            steps=[
                dict(range=[gauge_min, low], color="rgba(248,81,73,0.15)"),
                dict(range=[low, high], color="rgba(212,168,67,0.15)"),
                dict(range=[high, gauge_max], color="rgba(63,185,80,0.15)"),
            ],
            threshold=dict(
                line=dict(color=GOLD, width=3),
                thickness=0.8,
                value=price,
            ),
        ),
    ))

    fig.update_layout(
        **theme,
        height=300,
        margin=dict(l=40, r=40, t=60, b=40),
    )

    fig.add_annotation(
        x=0.12, y=-0.12, xref="paper", yref="paper",
        text=f"<b>Basse</b><br>{format_price(low)}", showarrow=False,
        font=dict(size=12, color=DANGER),
        align="center",
    )
    fig.add_annotation(
        x=0.88, y=-0.12, xref="paper", yref="paper",
        text=f"<b>Haute</b><br>{format_price(high)}", showarrow=False,
        font=dict(size=12, color=SUCCESS),
        align="center",
    )

    st.plotly_chart(fig, use_container_width=True)


def _render_scatter(result: EstimationResult, estimated_prix_m2: float, surface: float):
    """Nuage de points prix/m2 vs surface, colore par zone si disponible."""
    if result.nb_comparables == 0:
        return

    df = result.comparables
    if "surface" not in df.columns or "prix_m2" not in df.columns:
        return

    theme = get_plotly_dark_theme()
    fig = go.Figure()

    has_zones = result.zone_config is not None and "zone" in df.columns

    # Ligne horizontale mediane prix/m2
    median_prix = float(df["prix_m2"].median())
    fig.add_hline(
        y=median_prix,
        line=dict(color=GOLD_MUTED, width=1, dash="dash"),
        annotation=dict(
            text=f"Mediane : {median_prix:,.0f} EUR/m\u00b2",
            font=dict(size=11, color=GOLD_MUTED),
            xanchor="left",
        ),
    )

    # Ligne verticale surface recherchee
    fig.add_vline(
        x=surface,
        line=dict(color=GOLD_MUTED, width=1, dash="dot"),
    )

    zone_sizes = {1: 10, 2: 8, 3: 6}

    if has_zones:
        for z in [3, 2, 1]:  # Dessiner Z3 en dessous, Z1 au-dessus
            zone_df = df[df["zone"] == z]
            if len(zone_df) == 0:
                continue
            zc = result.zone_config
            if z == 1:
                zone_label = f"Zone 1 (0-{zc.radius_1_km} km) &middot; {len(zone_df)}"
            elif z == 2:
                zone_label = f"Zone 2 ({zc.radius_1_km}-{zc.radius_2_km} km) &middot; {len(zone_df)}"
            else:
                zone_label = f"Zone 3 ({zc.radius_2_km}-{zc.radius_3_km} km) &middot; {len(zone_df)}"

            hover_texts = []
            for _, row in zone_df.iterrows():
                dist = format_distance(row.get("distance_m"))
                addr = row.get("adresse", "")
                addr_line = f"{addr}<br>" if addr else ""
                hover_texts.append(
                    f"<b>{row.get('nom_commune', '')}</b><br>"
                    f"{addr_line}"
                    f"Zone {z} &middot; {dist}<br>"
                    f"Surface: {row['surface']:.0f} m\u00b2<br>"
                    f"Prix/m\u00b2: {row['prix_m2']:,.0f} EUR<br>"
                    f"Prix: {row['valeur_fonciere']:,.0f} EUR<br>"
                    f"Date: {row['date_mutation']}"
                )

            fig.add_trace(go.Scatter(
                x=zone_df["surface"],
                y=zone_df["prix_m2"],
                mode="markers",
                marker=dict(
                    size=zone_sizes[z],
                    color=ZONE_COLORS[z],
                    line=dict(width=1, color="rgba(255,255,255,0.3)"),
                    opacity=0.9 if z == 1 else 0.75,
                ),
                text=hover_texts,
                hovertemplate="%{text}<extra></extra>",
                name=zone_label,
            ))
    else:
        fig.add_trace(go.Scatter(
            x=df["surface"],
            y=df["prix_m2"],
            mode="markers",
            marker=dict(
                size=9,
                color=df["prix_m2"],
                colorscale=[[0, SUCCESS], [0.5, GOLD_MUTED], [1, DANGER]],
                showscale=True,
                colorbar=dict(
                    title=dict(text="Prix/m\u00b2", font=dict(color=TEXT_SECONDARY, size=11)),
                    tickfont=dict(color=TEXT_SECONDARY, size=10),
                    thickness=12,
                    len=0.6,
                ),
                line=dict(width=1, color=BORDER),
            ),
            text=df.get("nom_commune", pd.Series(dtype=str)),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Surface: %{x:.0f} m\u00b2<br>"
                "Prix/m\u00b2: %{y:,.0f} EUR"
                "<extra></extra>"
            ),
            name="Comparables",
        ))

    # Marqueur estimation (etoile doree, toujours au premier plan)
    fig.add_trace(go.Scatter(
        x=[surface],
        y=[estimated_prix_m2],
        mode="markers",
        marker=dict(
            size=18, color=GOLD, symbol="star",
            line=dict(width=2, color=BG_DARK),
        ),
        showlegend=True,
        name=f"Estimation ({estimated_prix_m2:,.0f} EUR/m\u00b2)",
        hovertemplate=(
            "<b>Votre estimation</b><br>"
            f"Surface: {surface:.0f} m\u00b2<br>"
            f"Prix/m\u00b2: {estimated_prix_m2:,.0f} EUR"
            "<extra></extra>"
        ),
    ))

    fig.update_layout(**theme)
    fig.update_layout(
        xaxis=dict(
            title=dict(text="Surface (m\u00b2)", font=dict(size=12, color=TEXT_SECONDARY)),
            gridcolor=BORDER,
            zerolinecolor=BORDER,
            ticksuffix=" m\u00b2",
            tickfont=dict(size=10),
        ),
        yaxis=dict(
            title=dict(text="Prix/m\u00b2 (EUR)", font=dict(size=12, color=TEXT_SECONDARY)),
            gridcolor=BORDER,
            zerolinecolor=BORDER,
            tickformat=",",
            ticksuffix=" \u20ac",
            tickfont=dict(size=10),
        ),
        showlegend=True,
        legend=dict(
            font=dict(size=11, color=TEXT_PRIMARY),
            bgcolor="rgba(22,27,34,0.85)",
            bordercolor=BORDER,
            borderwidth=1,
            yanchor="top",
            y=0.99,
            xanchor="right",
            x=0.99,
        ),
        height=420,
        margin=dict(l=70, r=20, t=30, b=55),
        hoverlabel=dict(
            bgcolor=BG_CARD,
            bordercolor=BORDER,
            font=dict(color=TEXT_PRIMARY, size=12),
        ),
    )

    st.markdown(
        '<div class="chart-title">Distribution des prix/m\u00b2 par surface</div>',
        unsafe_allow_html=True,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_comparables_table(result: EstimationResult):
    """Tableau formate des comparables enrichi avec zone, distance et annee."""
    if len(result.comparables) == 0:
        st.caption("Aucun comparable disponible.")
        return

    has_zones = "zone" in result.comparables.columns
    has_distance = "distance_m" in result.comparables.columns

    # Construire la liste des colonnes a afficher
    cols_to_show = []
    if has_zones:
        cols_to_show.append("zone")
    if has_distance:
        cols_to_show.append("distance_m")
    cols_to_show.extend([
        "date_mutation", "adresse", "code_postal", "nom_commune",
        "surface", "nb_pieces", "valeur_fonciere", "prix_m2",
    ])

    available = [c for c in cols_to_show if c in result.comparables.columns]
    display_df = result.comparables[available].copy()

    # Ajouter la colonne Annee
    if "date_mutation" in display_df.columns:
        display_df.insert(
            display_df.columns.get_loc("date_mutation") + 1,
            "annee",
            pd.to_datetime(display_df["date_mutation"]).dt.year,
        )

    col_names = {
        "zone": "Zone",
        "distance_m": "Distance",
        "date_mutation": "Date",
        "annee": "Annee",
        "adresse": "Adresse",
        "code_postal": "CP",
        "nom_commune": "Commune",
        "valeur_fonciere": "Prix",
        "surface": "Surface",
        "nb_pieces": "Pieces",
        "prix_m2": "Prix/m\u00b2",
    }
    display_df.rename(columns={c: col_names.get(c, c) for c in display_df.columns}, inplace=True)

    # Formatage
    if "Zone" in display_df.columns:
        display_df["Zone"] = display_df["Zone"].apply(lambda x: f"Z{int(x)}" if pd.notna(x) else "—")
    if "Distance" in display_df.columns:
        display_df["Distance"] = display_df["Distance"].apply(
            lambda x: format_distance(x) if pd.notna(x) else "—"
        )
    if "Date" in display_df.columns:
        display_df["Date"] = display_df["Date"].astype(str)
    if "Prix" in display_df.columns:
        display_df["Prix"] = display_df["Prix"].apply(lambda x: format_price(x))
    if "Surface" in display_df.columns:
        display_df["Surface"] = display_df["Surface"].apply(lambda x: f"{x:.0f} m\u00b2")
    if "Prix/m\u00b2" in display_df.columns:
        display_df["Prix/m\u00b2"] = display_df["Prix/m\u00b2"].apply(lambda x: format_price_m2(x))

    st.dataframe(display_df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Composant principal
# ---------------------------------------------------------------------------

def render_results(
    result: EstimationResult,
    prop: PropertyInput,
    overrides: CoefficientOverrides | None = None,
):
    """
    Affiche les resultats avec rendu professionnel.

    Onglets : Synthese / Carte / Evolution / Comparables
    """
    if result.nb_comparables == 0:
        st.error(
            "Estimation impossible : aucune transaction comparable trouvee dans la zone."
        )
        return

    base_price = result.prix_total_estime

    # Calcul des ajustements
    adj = compute_adjustments(prop, base_price, overrides)
    has_adjustments = abs(adj.total_multiplier - 1.0) > 0.001

    # Prix final
    final_price = adj.adjusted_price if has_adjustments else base_price
    final_prix_m2 = final_price / prop.surface if prop.surface > 0 else 0

    # Fourchette
    if result.confidence.low_estimate > 0:
        mult = adj.total_multiplier if has_adjustments else 1.0
        low = round(result.confidence.low_estimate * mult)
        high = round(result.confidence.high_estimate * mult)
    else:
        low = round(final_price * 0.85)
        high = round(final_price * 1.15)

    # -- Carte de prix --
    _render_price_card(
        final_price,
        final_prix_m2,
        result.confidence.level,
        result.confidence.level_label,
        result.nb_comparables,
        result.niveau_geo,
        result.geocoding.label,
    )
    _render_range(low, high)

    # -- Resume synthese --
    _render_summary(result, adj, has_adjustments)

    # -- Onglets --
    tab_synthese, tab_carte, tab_evolution, tab_comparables = st.tabs(
        ["Synthese", "Carte", "Evolution", "Comparables"]
    )

    with tab_synthese:
        _render_gauge(final_price, low, high)
        _render_zone_breakdown(result)
        st.markdown(f'<div class="section-divider"></div>', unsafe_allow_html=True)
        _render_scatter(result, final_prix_m2, prop.surface)

    with tab_carte:
        render_map(result)

    with tab_evolution:
        render_stats_chart(result)
        render_stats_metrics(result)

    with tab_comparables:
        st.markdown(
            f'<div class="chart-title">{result.nb_comparables} transactions comparables</div>',
            unsafe_allow_html=True,
        )
        _render_comparables_table(result)

    # Disclaimer
    st.markdown(
        '<div class="adjustment-note">'
        "<strong>Note :</strong> Les ajustements de caracteristiques sont des "
        "estimations statistiques basees sur les tendances du marche. "
        "Le prix DVF de base repose sur les transactions reelles "
        "enregistrees par les notaires."
        "</div>",
        unsafe_allow_html=True,
    )
