"""Configuration des zones concentriques pour l'estimation multi-zones."""

from dataclasses import dataclass


@dataclass
class ZoneConfig:
    """Parametres des 3 zones concentriques exclusives.

    Zone 1 : 0 -> radius_1_km  (la plus proche, poids le plus fort)
    Zone 2 : radius_1_km -> radius_2_km
    Zone 3 : radius_2_km -> radius_3_km
    """
    radius_1_km: float = 1.0
    radius_2_km: float = 2.0
    radius_3_km: float = 3.0
    weight_1: float = 0.60
    weight_2: float = 0.30
    weight_3: float = 0.10
    max_comparables: int = 500

    @property
    def radii_meters(self) -> tuple[float, float, float]:
        """Retourne les rayons en metres."""
        return (
            self.radius_1_km * 1000,
            self.radius_2_km * 1000,
            self.radius_3_km * 1000,
        )

    @property
    def weights(self) -> tuple[float, float, float]:
        """Retourne les poids normalises (somme = 1)."""
        total = self.weight_1 + self.weight_2 + self.weight_3
        if total == 0:
            return (1 / 3, 1 / 3, 1 / 3)
        return (
            self.weight_1 / total,
            self.weight_2 / total,
            self.weight_3 / total,
        )

    def weight_for_zone(self, zone: int) -> float:
        """Retourne le poids brut pour une zone (1, 2 ou 3)."""
        return {1: self.weight_1, 2: self.weight_2, 3: self.weight_3}.get(zone, 0)
