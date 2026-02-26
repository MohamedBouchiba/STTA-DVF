"""Utilitaires de formatage pour l'affichage."""


def format_price(amount: float) -> str:
    """Formate un prix en euros. Ex: 250000 -> '250 000 EUR'."""
    if amount == 0:
        return "N/A"
    return f"{amount:,.0f} EUR".replace(",", " ")


def format_price_m2(amount: float) -> str:
    """Formate un prix au m2. Ex: 4500.50 -> '4 501 EUR/m2'."""
    if amount == 0:
        return "N/A"
    return f"{amount:,.0f} EUR/m\u00b2".replace(",", " ")


def format_surface(surface: float) -> str:
    """Formate une surface. Ex: 65.5 -> '65,5 m2'."""
    return f"{surface:,.1f} m\u00b2".replace(",", " ").replace(".", ",")


def format_percentage(value: float | None) -> str:
    """Formate un pourcentage. Ex: 5.23 -> '+5,2%'."""
    if value is None:
        return "N/A"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%".replace(".", ",")


def confidence_color(level: str) -> str:
    """Retourne la couleur CSS pour un niveau de confiance."""
    return {
        "high": "#28a745",    # vert
        "medium": "#ffc107",  # jaune
        "low": "#dc3545",     # rouge
    }.get(level, "#6c757d")
