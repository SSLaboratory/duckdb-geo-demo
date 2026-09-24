"""SSRF-safe, size-capped HTTP downloads.

Every hop (including redirects) must resolve only to globally routable addresses.
Residual risk: DNS rebinding between validation and connect is not prevented; the
READ_ONLY mode (the container image default) disables user-supplied URL ingestion.
"""

import asyncio
import ipaddress
from pathlib import Path
from urllib.parse import urlsplit

import httpx

MAX_REDIRECTS = 5
_CHUNK_SIZE = 1024 * 1024
_ALLOWED_SCHEMES = {"http", "https"}


class UnsafeURLError(ValueError):
    pass


class DownloadError(ValueError):
    pass


class DownloadTooLargeError(ValueError):
    pass


async def _resolve(host: str, port: int) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, port)
    return [info[4][0] for info in infos]


def _is_public_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


async def validate_public_url(url: str) -> None:
    try:
        parts = urlsplit(url)
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        raise UnsafeURLError("URL is not valid") from None
    if parts.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeURLError("Only http and https URLs are allowed")
    if not parts.hostname:
        raise UnsafeURLError("URL must include a host")

    try:
        addresses = await _resolve(parts.hostname, port)
    except OSError:
        raise UnsafeURLError("URL host could not be resolved") from None
    if not addresses or not all(_is_public_ip(a) for a in addresses):
        raise UnsafeURLError("URL host is not allowed")


async def download_to_file(
    url: str,
    dest: Path,
    max_bytes: int,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> None:
    headers = {"User-Agent": "duckdb-geo-demo/0.1.0"}
    try:
        async with httpx.AsyncClient(
            follow_redirects=False, timeout=60.0, headers=headers, transport=transport
        ) as client:
            for _ in range(MAX_REDIRECTS + 1):
                await validate_public_url(url)
                async with client.stream("GET", url) as resp:
                    location = resp.headers.get("location")
                    if resp.is_redirect and location:
                        url = str(resp.url.join(location))
                        continue
                    if not resp.is_success:
                        raise DownloadError(
                            f"Download failed: remote returned HTTP {resp.status_code}"
                        )
                    await _write_capped(resp, dest, max_bytes)
                    return
            raise DownloadError("Download failed: too many redirects")
    except httpx.HTTPError:
        dest.unlink(missing_ok=True)
        raise DownloadError("Download failed") from None
    except BaseException:
        dest.unlink(missing_ok=True)
        raise


async def _write_capped(resp: httpx.Response, dest: Path, max_bytes: int) -> None:
    declared = resp.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > max_bytes:
        raise DownloadTooLargeError("Download exceeds MAX_UPLOAD_MB")

    written = 0
    with dest.open("wb") as fh:
        async for chunk in resp.aiter_bytes(_CHUNK_SIZE):
            written += len(chunk)
            if written > max_bytes:
                raise DownloadTooLargeError("Download exceeds MAX_UPLOAD_MB")
            fh.write(chunk)
