"""Verification d'integrite des fichiers telecharges."""

from pathlib import Path

from src.ingestion.download import compute_sha256, load_manifest, LANDING_DIR


def verify_all() -> dict[str, bool]:
    """Verifie tous les fichiers du manifest. Retourne {filename: ok}."""
    manifest = load_manifest()
    results = {}

    for filename, meta in manifest.items():
        filepath = LANDING_DIR / filename
        if not filepath.exists():
            print(f"[MISSING] {filename}")
            results[filename] = False
            continue

        expected = meta.get("sha256", "")
        if not expected:
            print(f"[NO_HASH] {filename}")
            results[filename] = False
            continue

        actual = compute_sha256(filepath)
        ok = actual == expected
        status = "OK" if ok else "MISMATCH"
        print(f"[{status}] {filename}")
        results[filename] = ok

    total = len(results)
    passed = sum(results.values())
    print(f"\n{passed}/{total} fichiers valides.")
    return results
