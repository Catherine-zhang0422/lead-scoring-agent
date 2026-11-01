import ipaddress
from urllib.parse import urlparse
import pandas as pd
import requests
from bs4 import BeautifulSoup


def is_safe_url(url: str) -> bool:
    """Validates that a URL does not point to localhost, private networks, or metadata endpoints."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False

        if hostname in ("localhost", "127.0.0.1", "::1", "metadata.google.internal"):
            return False

        try:
            ip = ipaddress.ip_address(hostname)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
            ):
                return False
        except ValueError:
            if hostname.endswith(".local") or hostname.endswith(".internal"):
                return False

        return True
    except Exception:
        return False


def parse_input_file(file_path: str) -> tuple[list[dict], list[str]]:
    """Deterministically parses CSV or Excel files, mapping columns and deduplicating."""
    warnings = []
    records = []

    try:
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        elif file_path.endswith((".xlsx", ".xls")):
            df = pd.read_excel(file_path)
        else:
            raise ValueError(
                "Unsupported file format. Please provide CSV or Excel (.xlsx/.xls)."
            )
    except Exception as e:
        raise ValueError(f"Failed to read input file {file_path}: {e}")

    col_map = {}
    for col in df.columns:
        col_lower = str(col).strip().lower()
        if col_lower in ["brand", "brand_name", "company", "exhibitor"]:
            col_map[col] = "brand"
        elif col_lower in ["website", "site", "url", "homepage"]:
            col_map[col] = "website"
        elif col_lower in ["category", "sector", "industry"]:
            col_map[col] = "category"
        elif col_lower in ["source_url", "source"]:
            col_map[col] = "source_url"

    df = df.rename(columns=col_map)

    if "brand" not in df.columns:
        raise ValueError(
            "Input file missing required 'brand' column (or brand_name/company/exhibitor)."
        )

    for opt_col in ["website", "category", "source_url"]:
        if opt_col not in df.columns:
            df[opt_col] = None

    seen_brands = set()
    for _, row in df.iterrows():
        raw_brand = row["brand"]
        if pd.isna(raw_brand):
            continue
        display_name = str(raw_brand).strip()
        normalized_key = display_name.lower()

        if not normalized_key:
            continue

        if normalized_key in seen_brands:
            warnings.append(f"Duplicate brand ignored: '{display_name}'")
            continue

        seen_brands.add(normalized_key)

        website = (
            str(row["website"]).strip()
            if pd.notna(row["website"])
            and str(row["website"]).strip().lower() != "nan"
            else None
        )
        if website and not is_safe_url(website):
            warnings.append(
                f"Unsafe or invalid website URL blocked for brand '{display_name}': {website}"
            )
            website = None

        category = (
            str(row["category"]).strip()
            if pd.notna(row["category"])
            and str(row["category"]).strip().lower() != "nan"
            else "unknown"
        )
        source_url = (
            str(row["source_url"]).strip()
            if pd.notna(row["source_url"])
            and str(row["source_url"]).strip().lower() != "nan"
            else file_path
        )

        records.append(
            {
                "brand": display_name,
                "website": website,
                "category": category,
                "source_url": source_url,
            }
        )

    return records, warnings


def parse_exhibitor_directory_url(url: str, limit: int = 50) -> tuple[list[dict], list[str]]:
    """Fetches a directory URL, extracts candidate brands and links with safety and limits."""
    warnings = []
    records = []

    if not is_safe_url(url):
        raise ValueError(f"URL failed security validation: {url}")

    try:
        headers = {"User-Agent": "TradeShowLeadScoringAgent/1.0"}
        resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        if resp.status_code != 200:
            raise ValueError(f"HTTP status {resp.status_code} received from URL.")

        if not is_safe_url(resp.url):
            raise ValueError("Redirected to an unsafe or internal network URL.")

        soup = BeautifulSoup(resp.text, "html.parser")

        candidates = []
        for item in soup.find_all(["li", "div", "a"], class_=lambda x: x and any(c in str(x).lower() for c in ["exhibitor", "brand", "company", "directory"])):
            text = item.get_text(strip=True)
            if 2 <= len(text) <= 60:
                link = item.find("a")
                href = link.get("href") if link else None
                candidates.append((text, href))

        if not candidates:
            for a in soup.find_all("a", href=True):
                text = a.get_text(strip=True)
                if 2 <= len(text) <= 50 and not text.lower().startswith(("http", "www", "read", "more")):
                    candidates.append((text, a["href"]))

        seen = set()
        for name, href in candidates:
            if len(records) >= limit:
                warnings.append(f"Reached maximum brand extraction limit ({limit}).")
                break
            norm = name.lower()
            if norm in seen:
                continue
            seen.add(norm)

            site = href if href and is_safe_url(href) else None
            records.append(
                {
                    "brand": name,
                    "website": site,
                    "category": "unknown",
                    "source_url": url,
                }
            )

        if not records:
            warnings.append(
                "Static HTML parser extracted 0 brands. The directory may rely heavily on JavaScript rendering or CAPTCHAs. Consider providing a CSV/Excel file instead."
            )

    except Exception as e:
        warnings.append(
            f"Failed to parse directory URL due to network or parsing limitation: {e}. Consider providing a CSV/Excel file."
        )

    return records, warnings
