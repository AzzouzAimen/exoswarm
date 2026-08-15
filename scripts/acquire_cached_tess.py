"""One-time acquisition of an official TESS light-curve FITS product.

This script is intentionally manual. It is not imported by the API or science pipeline, and it
never provides a live-network fallback during an investigation.

Structural FITS errors and invalid DATASUM values are fatal. Embedded CHECKSUM values are retained
with explicit validity flags because official SPOC products can preserve invalid header checksums.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from astropy.io import fits

REQUIRED_COLUMNS = {"TIME", "PDCSAP_FLUX", "PDCSAP_FLUX_ERR", "QUALITY"}


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--mast-product-uri", required=True)
    parser.add_argument("--mast-observation-id", required=True)
    parser.add_argument("--official-product-filename", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--provenance-output", required=True, type=Path)
    parser.add_argument("--opaque-target-id", required=True)
    parser.add_argument("--real-target-name", required=True)
    parser.add_argument("--tic-id", required=True)
    parser.add_argument("--sector", required=True, type=int)
    parser.add_argument("--cadence-seconds", required=True, type=float)
    parser.add_argument("--expected-period-days", required=True, type=float)
    parser.add_argument("--expected-duration-hours", required=True, type=float)
    parser.add_argument("--expected-depth-percent", required=True, type=float)
    parser.add_argument("--expected-values-source-url", required=True)
    parser.add_argument("--expected-values-source-description", required=True)
    return parser.parse_args()


def _header_value(primary: fits.Header, table: fits.Header, key: str):
    value = table.get(key)
    return primary.get(key) if value is None else value


def _inspect_fits(path: Path, *, sector: int, cadence_seconds: float) -> dict:
    checksums: list[dict[str, object]] = []
    integrity_warnings: list[str] = []
    with fits.open(path, mode="readonly", memmap=False, checksum=True) as hdus:
        hdus.verify("exception")
        if len(hdus) < 2 or not isinstance(hdus[1], fits.BinTableHDU):
            raise ValueError("FITS extension 1 is not a binary light-curve table")
        primary = hdus[0].header
        table = hdus[1]
        table_header = table.header
        columns = {name.upper() for name in (table.columns.names or [])}
        missing = sorted(REQUIRED_COLUMNS - columns)
        if missing:
            raise ValueError(f"official FITS is missing required columns: {', '.join(missing)}")

        actual_sector = int(_header_value(primary, table_header, "SECTOR") or 0)
        if actual_sector != sector:
            raise ValueError(f"expected sector {sector}, found sector {actual_sector}")
        time_system = str(_header_value(primary, table_header, "TIMESYS") or "").upper()
        if time_system != "TDB":
            raise ValueError(f"expected TDB time system, found {time_system or 'missing'}")
        bjd_reference = float(_header_value(primary, table_header, "BJDREFI") or 0) + float(
            _header_value(primary, table_header, "BJDREFF") or 0
        )
        if bjd_reference != 2_457_000.0:
            raise ValueError(f"expected TESS BTJD reference 2457000.0, found {bjd_reference}")
        actual_cadence_seconds = float(
            _header_value(primary, table_header, "TIMEDEL")
        ) * 86_400.0
        if abs(actual_cadence_seconds - cadence_seconds) > 1.0:
            raise ValueError(
                f"expected approximately {cadence_seconds} s cadence, "
                f"found {actual_cadence_seconds} s"
            )

        for index, hdu in enumerate(hdus):
            checksum_present = "CHECKSUM" in hdu.header
            datasum_present = "DATASUM" in hdu.header
            checksum_valid = bool(hdu.verify_checksum()) if checksum_present else None
            datasum_valid = bool(hdu.verify_datasum()) if datasum_present else None
            if datasum_valid is False:
                raise ValueError(f"FITS DATASUM validation failed for HDU {index}")
            if checksum_valid is False:
                integrity_warnings.append(
                    f"HDU {index} preserves an embedded CHECKSUM that Astropy does not validate"
                )
            checksums.append(
                {
                    "hdu_index": index,
                    "checksum": hdu.header.get("CHECKSUM"),
                    "checksum_valid": checksum_valid,
                    "datasum": hdu.header.get("DATASUM"),
                    "datasum_valid": datasum_valid,
                }
            )

        release_metadata = {
            key: primary.get(key)
            for key in (
                "ORIGIN",
                "DATE",
                "CREATOR",
                "PROCVER",
                "FILEVER",
                "DATA_REL",
                "TIMVERSN",
                "TELESCOP",
                "INSTRUME",
            )
            if primary.get(key) is not None
        }
        return {
            "sector": actual_sector,
            "cadence_seconds": actual_cadence_seconds,
            "time_system": time_system,
            "time_convention": "BTJD = BJD(TDB) - 2457000.0",
            "required_columns": sorted(REQUIRED_COLUMNS),
            "fits_checksums": checksums,
            "integrity_warnings": integrity_warnings,
            "release_metadata": release_metadata,
        }


def main() -> None:
    args = _arguments()
    parsed_source = urlparse(args.source_url)
    if parsed_source.scheme != "https" or parsed_source.hostname not in {
        "archive.stsci.edu",
        "mast.stsci.edu",
    }:
        raise ValueError("source URL must use an official HTTPS MAST host")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.provenance_output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        dir=args.output.parent, prefix=".tess-download-", suffix=".fits", delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
        request = Request(args.source_url, headers={"User-Agent": "ExoSwarm-acquisition/1"})
        try:
            with urlopen(request, timeout=120) as response:
                while chunk := response.read(1024 * 1024):
                    temporary.write(chunk)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    try:
        fits_metadata = _inspect_fits(
            temporary_path,
            sector=args.sector,
            cadence_seconds=args.cadence_seconds,
        )
        source_bytes = temporary_path.read_bytes()
        sha256 = hashlib.sha256(source_bytes).hexdigest()

        previous_provenance = None
        if args.provenance_output.exists():
            previous_provenance = json.loads(
                args.provenance_output.read_text(encoding="utf-8")
            )
            if (
                previous_provenance["cache"]["sha256"] != sha256
                or previous_provenance["mast"]["product_uri"] != args.mast_product_uri
                or previous_provenance["mast"]["observation_id"]
                != args.mast_observation_id
                or previous_provenance["real_target_identity"]["target_name"]
                != args.real_target_name
                or previous_provenance["real_target_identity"]["tic_id"] != args.tic_id
            ):
                raise FileExistsError(
                    f"refusing to replace different provenance: {args.provenance_output}"
                )

        if args.output.exists() and args.output.read_bytes() != source_bytes:
            raise FileExistsError(f"refusing to replace different cached file: {args.output}")
        if not args.output.exists():
            temporary_path.replace(args.output)

        acquired_at = (
            previous_provenance["acquisition"]["acquired_at_utc"]
            if previous_provenance
            else datetime.now(UTC).isoformat()
        )
        provenance = {
            "schema_version": "1",
            "opaque_target_id": args.opaque_target_id,
            "real_target_identity": {
                "target_name": args.real_target_name,
                "tic_id": args.tic_id,
            },
            "mast": {
                "observation_id": args.mast_observation_id,
                "product_uri": args.mast_product_uri,
                "official_product_filename": args.official_product_filename,
                "source_url": args.source_url,
                "product_type": "SPOC calibrated light curve (LC), science, level 3",
                "public_data": True,
            },
            "cache": {
                "path": args.output.as_posix(),
                "sha256": sha256,
                "size_bytes": len(source_bytes),
                **fits_metadata,
            },
            "expected_values": {
                "period_days": args.expected_period_days,
                "duration_hours": args.expected_duration_hours,
                "depth_percent": args.expected_depth_percent,
                "source_url": args.expected_values_source_url,
                "source_description": args.expected_values_source_description,
                "recorded_before_pipeline_evaluation": True,
            },
            "acquisition": {
                "acquired_at_utc": acquired_at,
                "method": "MAST official direct product URL; no API key",
                "reproduction_command": shlex.join(
                    ["uv", "run", "--project", "apps/api", "--extra", "science", "python"]
                    + ["scripts/acquire_cached_tess.py", *sys.argv[1:]]
                ),
                "redistribution_notes": (
                    "Unmodified public NASA/STScI TESS SPOC product. Retain MAST/TESS "
                    "attribution and the official product URI."
                ),
            },
            "forbidden_agent_visible_values": [
                args.real_target_name,
                f"TIC {args.tic_id}",
                args.tic_id,
                args.official_product_filename,
                "confirmed planet",
            ],
        }
        content = json.dumps(provenance, indent=2, sort_keys=True) + "\n"
        args.provenance_output.write_text(content, encoding="utf-8")
        print(f"cached {len(source_bytes)} bytes as sha256:{sha256}")
    finally:
        temporary_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
