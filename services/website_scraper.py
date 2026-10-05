import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


class WebsiteScraper:

    def __init__(self, timeout=10):
        self.timeout = timeout

        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/154.0.0.0 Safari/537.36"
            )
        }

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

        if not website.startswith(("http://", "https://")):
            website = "https://" + website

        try:
            response = requests.get(
                website,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=True,
            )

            response.raise_for_status()

        except requests.RequestException:
            return result

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        # ==========================================
        # EMAILS
        # ==========================================

        emails = set()

        # mailto links
        for link in soup.select('a[href^="mailto:"]'):
            email = link.get("href", "")
            email = email.replace("mailto:", "").split("?")[0].strip()

            if self.is_valid_email(email):
                emails.add(email)

        # Emails inside page text/source
        found_emails = re.findall(
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            response.text,
        )

        for email in found_emails:
            if self.is_valid_email(email):
                emails.add(email)

        result["email"] = ", ".join(sorted(emails))

        # ==========================================
        # SOCIAL MEDIA
        # ==========================================

        social_links = []

        for link in soup.find_all("a", href=True):

            href = link.get("href", "").strip()

            if not href:
                continue

            full_url = urljoin(
                response.url,
                href
            )

            lower_url = full_url.lower()

            # Facebook
            if "facebook.com" in lower_url:
                if not result["facebook"]:
                    result["facebook"] = full_url

            # Instagram
            elif "instagram.com" in lower_url:
                if not result["instagram"]:
                    result["instagram"] = full_url

            # LinkedIn
            elif "linkedin.com" in lower_url:
                if not result["linkedin"]:
                    result["linkedin"] = full_url

            # Twitter / X
            elif (
                "twitter.com" in lower_url
                or "x.com" in lower_url
            ):
                if not result["twitter"]:
                    result["twitter"] = full_url

            # Other social websites
            elif any(
                social in lower_url
                for social in [
                    "youtube.com",
                    "tiktok.com",
                    "pinterest.com",
                    "threads.net",
                ]
            ):
                social_links.append(full_url)

        # Remove duplicate links
        social_links = list(dict.fromkeys(social_links))

        result["other_social"] = ", ".join(
            social_links
        )

        return result

    # ==========================================
    # EMAIL VALIDATION
    # ==========================================

    def is_valid_email(self, email):

        if not email:
            return False

        email = email.lower().strip()

        # Ignore obvious fake/example emails
        blocked = [
            "example.com",
            "example.org",
            "test.com",
            "domain.com",
        ]

        if any(
            blocked_domain in email
            for blocked_domain in blocked
        ):
            return False

        pattern = (
            r"^[A-Za-z0-9._%+-]+"
            r"@[A-Za-z0-9.-]+\."
            r"[A-Za-z]{2,}$"
        )

        return bool(
            re.match(pattern, email)
        )