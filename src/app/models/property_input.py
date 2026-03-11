"""Modele de donnees etendu pour la saisie utilisateur."""

from dataclasses import dataclass
from enum import Enum


class PropertyType(str, Enum):
    """Types de biens immobiliers."""

    MAISON = "maison"
    APPARTEMENT = "appartement"
    DUPLEX = "duplex"
    TRIPLEX = "triplex"
    LOFT = "loft"
    HOTEL_PARTICULIER = "hotel_particulier"

    @property
    def dvf_type(self) -> str:
        """Mappe vers le type DVF binaire (maison/appartement)."""
        if self in (PropertyType.MAISON, PropertyType.HOTEL_PARTICULIER):
            return "maison"
        return "appartement"

    @property
    def label(self) -> str:
        labels = {
            "maison": "Maison",
            "appartement": "Appartement",
            "duplex": "Duplex",
            "triplex": "Triplex",
            "loft": "Loft / Atelier",
            "hotel_particulier": "Hotel Particulier",
        }
        return labels[self.value]

    @property
    def icon(self) -> str:
        icons = {
            "maison": "\U0001f3e0",
            "appartement": "\U0001f3e2",
            "duplex": "\U0001f3d8\ufe0f",
            "triplex": "\U0001f3d7\ufe0f",
            "loft": "\U0001f3ed",
            "hotel_particulier": "\U0001f3f0",
        }
        return icons[self.value]


class QualityLevel(str, Enum):
    """Qualite du bien par rapport au quartier."""

    INFERIEURE = "inferieure"
    COMPARABLE = "comparable"
    SUPERIEURE = "superieure"


class ConstructionPeriod(str, Enum):
    """Periode de construction du bien."""

    UNKNOWN = "unknown"
    AVANT_1850 = "avant_1850"
    P1850_1913 = "1850_1913"
    P1914_1947 = "1914_1947"
    P1948_1969 = "1948_1969"
    P1970_1989 = "1970_1989"
    P1990_2005 = "1990_2005"
    APRES_2005 = "apres_2005"


class PropertyCondition(str, Enum):
    """Etat general du bien."""

    A_RENOVER = "a_renover"
    STANDARD = "standard"
    BON_ETAT = "bon_etat"
    REFAIT_A_NEUF = "refait_a_neuf"


@dataclass
class PropertyInput:
    """Description complete du bien saisie via le wizard."""

    # Etape 2 : Type (obligatoire)
    property_type: PropertyType

    # Etape 3 : Informations principales
    surface: float
    nb_pieces: int | None = None
    nb_salles_de_bain: int | None = None
    etage: int | None = None
    nb_etages_immeuble: int | None = None

    # Etape 4 : Caracteristiques (optionnelles)
    ascenseur: bool = False
    balcon: bool = False
    terrasse: bool = False
    cave: bool = False
    parking: bool = False
    chambre_service: bool = False
    vue_exceptionnelle: bool = False
    parties_communes_renovees: bool = False
    ravalement_recent: bool = False

    # Etape 5 : Complements (optionnels)
    construction_period: ConstructionPeriod = ConstructionPeriod.UNKNOWN
    condition: PropertyCondition = PropertyCondition.STANDARD
    quality: QualityLevel = QualityLevel.COMPARABLE

    @property
    def dvf_type_bien(self) -> str:
        """Type attendu par estimate()."""
        return self.property_type.dvf_type

    @property
    def dvf_nb_pieces(self) -> int | None:
        """Nb pieces attendu par estimate()."""
        return self.nb_pieces
