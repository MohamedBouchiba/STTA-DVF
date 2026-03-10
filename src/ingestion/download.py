"""Telechargement des CSV DVF geolocalisees depuis Etalab."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from tqdm import tqdm

from src.config import LANDING_DIR, ETALAB_BASE_URL, DVF_YEARS, DVF_DEPARTEMENTS

MANIFEST_PATH = LANDING_DIR / "manifest.json"


def load_manifest() -> dict:
    """Charge le manifest des fichiers telecharges."""
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def save_manifest(manifest: dict):
    """Sauvegarde le manifest."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def compute_sha256(filepath: Path) -> str:
    """Calcule le SHA256 d'un fichier."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def download_file(url: str, dest: Path, chunk_size: int = 8192) -> bool:
    """Telecharge un fichier avec barre de progression."""
    try:
        resp = requests.get(url, stream=True, timeout=300)
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))

        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            with tqdm(total=total, unit="B", unit_scale=True, desc=dest.name) as pbar:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    f.write(chunk)
                    pbar.update(len(chunk))
        return True
    except Exception as e:
        print(f"Erreur telechargement {url}: {e}")
        if dest.exists():
            dest.unlink()
        return False


def get_csv_url(year: int, departement: str) -> str:
    """Construit l'URL de telechargement d'un CSV DVF Etalab."""
    return f"{ETALAB_BASE_URL}/{year}/departements/{departement}.csv.gz"


def download_dvf_etalab(
    years: list[int] | None = None,
    departements: list[str] | None = None,
    force: bool = False,
):
    """
    Telecharge les CSV DVF geolocalisees depuis Etalab.

    Source : https://files.data.gouv.fr/geo-dvf/latest/csv/{YEAR}/departements/{DEPT}.csv.gz

    Args:
        years: Annees a telecharger (defaut: DVF_YEARS).
        departements: Departements a telecharger (defaut: DVF_DEPARTEMENTS).
        force: Re-telecharger meme si le fichier existe deja.
    """
    if years is None:
        years = DVF_YEARS
    if departements is None:
        departements = DVF_DEPARTEMENTS

    manifest = load_manifest()
    LANDING_DIR.mkdir(parents=True, exist_ok=True)

    total_files = len(years) * len(departements)
    downloaded = 0
    skipped = 0
    errors = 0

    for year in years:
        year_dir = LANDING_DIR / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)

        for dep in departements:
            filename = f"{year}/{dep}.csv.gz"
            dest = LANDING_DIR / filename
            url = get_csv_url(year, dep)

            if not force and filename in manifest:
                existing_checksum = manifest[filename].get("sha256", "")
                if dest.exists() and existing_checksum:
                    current_checksum = compute_sha256(dest)
                    if current_checksum == existing_checksum:
                        print(f"[SKIP] {filename} deja a jour")
                        skipped += 1
                        continue

            print(f"[DOWNLOAD] {filename}")
            success = download_file(url, dest)

            if success:
                checksum = compute_sha256(dest)
                manifest[filename] = {
                    "downloaded_at": datetime.now(timezone.utc).isoformat(),
                    "source_url": url,
                    "sha256": checksum,
                    "size_bytes": dest.stat().st_size,
                    "year": year,
                    "departement": dep,
                }
                save_manifest(manifest)
                downloaded += 1
            else:
                errors += 1

    print(f"\nTelechargement termine:")
    print(f"  Telecharges : {downloaded}/{total_files}")
    print(f"  Ignores     : {skipped}")
    print(f"  Erreurs     : {errors}")


def list_landing_files() -> list[Path]:
    """Liste les fichiers CSV DVF disponibles dans le landing."""
    if not LANDING_DIR.exists():
        return []
    return sorted(LANDING_DIR.rglob("*.csv.gz"))
