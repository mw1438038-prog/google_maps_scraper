import ipaddress
import logging
import re
import socket
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests.exceptions import InvalidURL


MAX_REDIRECTS = 5
MAX_RESPONSE_BYTES = 1_000_000
READ_CHUNK_SIZE = 16_384

logger = logging.getLogger(__name__)


class _PinnedAddressAdapter(HTTPAdapter):
    def __init__(self, hostname, address, port):
        super().__init__(max_retries=0)
        self.hostname = hostname
        self.address = address
        self.port = port

    def get_connection_with_tls_context(
        self,
        request,
        verify,
        proxies=None,
        cert=None,
    ):
        if proxies and any(proxies.values()):
            raise InvalidURL("Proxies are not supported for website scraping.")

        parsed = urlparse(request.url)
        if parsed.hostname != self.hostname:
            raise InvalidURL("Website hostname changed during the request.")

        host_params, pool_kwargs = self.build_connection_pool_key_attributes(
            request,
            verify,
            cert,
        )
        host_params["host"] = self.address
        host_params["port"] = self.port

        if parsed.scheme == "https":
            pool_kwargs["server_hostname"] = self.hostname
            pool_kwargs["assert_hostname"] = self.hostname

        return self.poolmanager.connection_from_host(
            **host_params,
            pool_kwargs=pool_kwargs,
        )


class WebsiteScraper:
    def __init__(self, timeout=6):
        self.timeout = timeout
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/154.0.0.0 Safari/537.36"
            )
        }

    def _resolve_public_address(self, url):
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        if (
            scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ValueError("Only public HTTP and HTTPS websites are supported.")

        hostname = parsed.hostname.rstrip(".").encode("idna").decode("ascii").lower()
        default_port = 443 if scheme == "https" else 80
        port = parsed.port or default_port
        if port != default_port:
            raise ValueError("Non-standard website ports are not supported.")

        try:
            address = ipaddress.ip_address(hostname)
            addresses = [address]
        except ValueError:
            records = socket.getaddrinfo(
                hostname,
                port,
                type=socket.SOCK_STREAM,
            )
            addresses = [
                ipaddress.ip_address(record[4][0].split("%", 1)[0])
                for record in records
            ]

        if not addresses or any(not address.is_global for address in addresses):
            raise ValueError("Website must resolve only to public IP addresses.")

        return hostname, addresses[0].compressed, port

    def _fetch_page(self, website):
        if len(website) > 2048:
            raise ValueError("Website URL is too long.")

        if not website.startswith(("http://", "https://")):
            website = "https://" + website

        deadline = time.monotonic() + self.timeout
        current_url = website

        with requests.Session() as session:
            session.trust_env = False

            for redirect_count in range(MAX_REDIRECTS + 1):
                hostname, address, port = self._resolve_public_address(
                    current_url
                )
                parsed = urlparse(current_url)
                session.mount(
                    f"{parsed.scheme.lower()}://",
                    _PinnedAddressAdapter(hostname, address, port),
                )

                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise requests.Timeout("Website request exceeded its time limit.")

                host_header = f"[{hostname}]" if ":" in hostname else hostname
                request_headers = dict(self.headers)
                request_headers["Host"] = host_header

                with session.get(
                    current_url,
                    headers=request_headers,
                    timeout=(min(2, remaining), min(2, remaining)),
                    allow_redirects=False,
                    stream=True,
                ) as response:
                    if response.is_redirect or response.is_permanent_redirect:
                        location = response.headers.get("Location")
                        if not location or redirect_count >= MAX_REDIRECTS:
                            raise ValueError("Website redirect limit was reached.")
                        current_url = urljoin(current_url, location)
                        continue

                    response.raise_for_status()
                    content_type = response.headers.get(
                        "Content-Type",
                        "",
                    ).lower()
                    if content_type and not (
                        content_type.startswith("text/html")
                        or content_type.startswith("application/xhtml+xml")
                    ):
                        return "", response.url

                    content_length = response.headers.get("Content-Length")
                    if content_length and int(content_length) > MAX_RESPONSE_BYTES:
                        raise ValueError("Website response is too large.")

                    body = bytearray()
                    for chunk in response.iter_content(READ_CHUNK_SIZE):
                        if time.monotonic() >= deadline:
                            raise requests.Timeout(
                                "Website request exceeded its time limit."
                            )
                        body.extend(chunk)
                        if len(body) > MAX_RESPONSE_BYTES:
                            raise ValueError("Website response is too large.")

                    encoding = response.encoding or "utf-8"
                    try:
                        page = body.decode(encoding, errors="replace")
                    except LookupError:
                        page = body.decode("utf-8", errors="replace")
                    return page, response.url

        raise ValueError("Website redirect limit was reached.")

    def scrape(self, website):
        result = {
            "email": "",
            "facebook": "",
            "instagram": "",
            "linkedin": "",
            "twitter": "",
            "other_social": "",
        }

        if not website:
            return result

        try:
            page, page_url = self._fetch_page(str(website).strip())
        except (requests.RequestException, OSError, ValueError) as error:
            logger.info(
                "Website enrichment request failed: %s",
                type(error).__name__,
            )
            return result

        if not page:
            return result

        soup = BeautifulSoup(page, "html.parser")
        emails = set()

        for link in soup.select('a[href^="mailto:"]'):
            email = link.get("href", "")
            email = email[len("mailto:"):].split("?")[0].strip()
            if self.is_valid_email(email):
                emails.add(email)

        for email in re.findall(
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            page,
        ):
            if self.is_valid_email(email):
                emails.add(email)

        result["email"] = ", ".join(sorted(emails))
        social_links = []
        social_domains = {
            "facebook.com": "facebook",
            "instagram.com": "instagram",
            "linkedin.com": "linkedin",
            "twitter.com": "twitter",
            "x.com": "twitter",
        }
        other_social_domains = {
            "youtube.com",
            "tiktok.com",
            "pinterest.com",
            "threads.net",
        }

        for link in soup.find_all("a", href=True):
            full_url = urljoin(page_url, link.get("href", "").strip())
            parsed = urlparse(full_url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                continue

            link_host = parsed.hostname.rstrip(".").lower()
            matching_domain = next(
                (
                    domain
                    for domain in social_domains
                    if link_host == domain or link_host.endswith(f".{domain}")
                ),
                None,
            )
            if matching_domain:
                field = social_domains[matching_domain]
                if not result[field]:
                    result[field] = full_url
            elif any(
                link_host == domain or link_host.endswith(f".{domain}")
                for domain in other_social_domains
            ):
                social_links.append(full_url)

        result["other_social"] = ", ".join(dict.fromkeys(social_links))
        return result

    def is_valid_email(self, email):
        if not email:
            return False

        email = email.lower().strip()
        blocked = ("example.com", "example.org", "test.com", "domain.com")
        if any(domain in email for domain in blocked):
            return False

        pattern = (
            r"^[A-Za-z0-9._%+-]+"
            r"@[A-Za-z0-9.-]+\."
            r"[A-Za-z]{2,}$"
        )
        return bool(re.match(pattern, email))
