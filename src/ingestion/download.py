"""Telechargement des archives DVF+ depuis Cerema Box."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from tqdm import tqdm

from src.config import LANDING_DIR

# Liste des codes departements DVF+
DEPARTEMENTS = [
    "01", "02", "03", "04", "05", "06", "07", "08", "09", "10",
    "11", "12", "13", "14", "15", "16", "17", "18", "19",
    "21", "22", "23", "24", "25", "26", "27", "28", "29",
    "2A", "2B",
    "30", "31", "32", "33", "34", "35", "36", "37", "38", "39",
    "40", "41", "42", "43", "44", "45", "46", "47", "48", "49",
    "50", "51", "52", "53", "54", "55", "56", "58", "59",
    "60", "61", "62", "63", "64", "65", "66",
    "67", "68",  # Alsace-Moselle: peut etre absent de DVF
    "69", "70", "71", "72", "73", "74", "75", "76",
    "77", "78", "79", "80", "81", "82", "83", "84", "85", "86",
    "87", "88", "89", "90", "91", "92", "93", "94", "95",
    "971", "972", "973", "974", "976",
]

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


def download_dvf_plus(
    base_url: str,
    dvf_version: str = "2025-04",
    file_extension: str = ".backup",
    force: bool = False,
):
    """
    Telecharge les archives DVF+ par departement.

    IMPORTANT: Les URLs exactes de Cerema Box ne sont pas stables.
    Ce script suppose que les fichiers sont accessibles via un pattern d'URL.
    Si ce n'est pas le cas, telecharger manuellement depuis:
    https://cerema.box.com/v/dvfplus-opendata

    Args:
        base_url: URL de base pour le telechargement (sans le nom de fichier).
        dvf_version: Version DVF+ (ex: '2025-04').
        file_extension: Extension des fichiers (.backup ou .sql.gz).
        force: Re-telecharger meme si le fichier existe deja.
    """
    manifest = load_manifest()
    LANDING_DIR.mkdir(parents=True, exist_ok=True)

    for dep in DEPARTEMENTS:
        filename = f"dvfplus_{dep}{file_extension}"
        dest = LANDING_DIR / filename
        url = f"{base_url}/{filename}"

        if not force and filename in manifest:
            existing_checksum = manifest[filename].get("sha256", "")
            if dest.exists() and existing_checksum:
                current_checksum = compute_sha256(dest)
                if current_checksum == existing_checksum:
                    print(f"[SKIP] {filename} deja a jour")
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
                "dvf_version": dvf_version,
            }
            save_manifest(manifest)

    print(f"\nTelechargement termine. {len(manifest)} fichiers dans le manifest.")


def list_landing_files() -> list[Path]:
    """Liste les fichiers DVF+ disponibles dans le landing."""
    if not LANDING_DIR.exists():
        return []
    return sorted(
        p for p in LANDING_DIR.iterdir()
        if p.suffix in (".backup", ".gz", ".sql")
    )
