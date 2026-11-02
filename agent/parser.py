import ipaddress
import socket
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests


def is_safe_url(url):
    """Reject unsupported schemes and non-public network addresses."""
    try:
        parsed = urlparse(url)

        if parsed.scheme not in {"http", "https"}:
            return False

        if not parsed.hostname or parsed.username or parsed.password:
            return False

        addresses = socket.getaddrinfo(
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )

        return bool(addresses) and all(
            ipaddress.ip_address(address[4][0]).is_global
            for address in addresses
        )
    except (ValueError, OSError):
        return False


def _clean_text(value):
    if pd.isna(value):
        return ""
    return " ".join(str(value).split())


def _normalize_records(rows, source):
    records = []
    warnings = []
    seen = set()

    for row in rows:
        brand = _clean_text(row.get("brand", ""))

        if not brand:
            continue

        key = brand.casefold()
        if key in seen:
            continue

        seen.add(key)
        records.append({
            "brand": brand,
            "website": _clean_text(row.get("website", "")) or None,
            "category": _clean_text(row.get("category", "")) or "unknown",
            "source_url": _clean_text(row.get("source_url", "")) or source,
            "input_source": source,
        })

    if not records:
        warnings.append("No brand records were extracted.")

    return records, warnings


def parse_input_file(file_path):
    """Read CSV or XLSX and return (brand_records, warnings)."""
    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")

    suffix = path.suffix.lower()

    if suffix == ".csv":
        frame = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    elif suffix == ".xlsx":
        frame = pd.read_excel(path, dtype=str)
    else:
        raise ValueError("Supported input formats are .csv and .xlsx.")

    frame.columns = [
        str(column).strip().casefold()
        for column in frame.columns
    ]

    if frame.columns.duplicated().any():
        raise ValueError("Input contains duplicate column names.")

    aliases = ("brand", "brand_name", "company", "exhibitor")
    brand_column = next(
        (column for column in aliases if column in frame.columns),
        None,
    )

    if brand_column is None:
        raise ValueError(
            "Input requires a brand, brand_name, company, "
            "or exhibitor column."
        )

    if brand_column != "brand":
        frame = frame.rename(columns={brand_column: "brand"})

    return _normalize_records(
        frame.fillna("").to_dict(orient="records"),
        str(path),
    )


def parse_exhibitor_directory_url(url, limit=50):
    """Extract explicit exhibitor-name elements from static HTML."""
    if limit <= 0:
        raise ValueError("limit must be a positive integer.")

    current_url = url

    # Validate every redirect destination before requesting it.
    with requests.Session() as session:
        session.trust_env = False

        for _ in range(6):
            if not is_safe_url(current_url):
                raise ValueError(
                    f"URL is not a permitted public HTTP(S) address: "
                    f"{current_url}"
                )

            with session.get(
                current_url,
                timeout=(5, 20),
                allow_redirects=False,
                stream=True,
            ) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("Location")
                    if not location:
                        raise ValueError("Redirect has no destination.")
                    current_url = urljoin(current_url, location)
                    continue

                response.raise_for_status()

                content_type = response.headers.get(
                    "Content-Type", ""
                ).lower()
                if not any(
                    kind in content_type
                    for kind in ("text/html", "application/xhtml+xml")
                ):
                    raise ValueError("Directory URL must return HTML.")

                content = bytearray()
                for chunk in response.iter_content(chunk_size=16384):
                    content.extend(chunk)
                    if len(content) > 5_000_000:
                        raise ValueError("Directory page exceeds 5 MB.")

                html = bytes(content)
                break
        else:
            raise ValueError("Too many redirects.")

    soup = BeautifulSoup(html, "html.parser")

    for element in soup(["script", "style", "nav", "footer", "header"]):
        element.decompose()

    # Intentionally conservative: generic navigation links are not brands.
    selectors = (
        ".exhibitor-name, .exhibitor__name, "
        ".exhibitor-title, .exhibitor__title, "
        "[data-exhibitor-name]"
    )

    rows = []
    for element in soup.select(selectors):
        brand = (
            element.get("data-exhibitor-name")
            or element.get_text(" ", strip=True)
        )
        rows.append({
            "brand": brand,
            "category": "unknown",
            "source_url": current_url,
        })

    records, warnings = _normalize_records(rows, url)

    if not records:
        warnings.append(
            "No supported exhibitor-name elements found. "
            "Export the directory to CSV/XLSX or add a site-specific "
            "selector. JavaScript pages and access challenges "
            "are not supported."
        )

    if len(records) > limit:
        records = records[:limit]
        warnings.append(f"Brand list limited to {limit} records.")

    warnings.append(
        "Static directory extraction covers one page only; "
        "check completeness against the source."
    )

    return records, warnings
