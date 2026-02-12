"""Discover council meetings and video URLs from Vernon's eScribe portal."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

ESCRIBE_BASE = "https://pub-vernon.escribemeetings.com"
CALENDAR_ENDPOINT = "/MeetingsCalendarView.aspx/GetCalendarMeetings"
VOD_SERVER = "vod.isilive.ca"


@dataclass
class DiscoveredMeeting:
    escribe_id: str
    title: str
    meeting_type: str
    meeting_date: datetime
    video_url: str | None
    agenda_url: str | None
    minutes_url: str | None


class EScribeScraper:
    """Scrapes the eScribe portal to discover council meetings with video."""

    def __init__(self, portal_url: str = ESCRIBE_BASE):
        self.portal_url = portal_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "VernonChatbot/1.0"})
        self.session.verify = False  # eScribe portal has SSL cert issues

    def discover_meetings(
        self, start_year: int = 2020, end_year: int | None = None
    ) -> list[DiscoveredMeeting]:
        """Discover all meetings with video from the eScribe portal.

        Queries the FullCalendar AJAX endpoint year-by-year.
        """
        if end_year is None:
            end_year = datetime.now().year + 1

        all_meetings: list[DiscoveredMeeting] = []
        seen_ids: set[str] = set()

        for year in range(start_year, end_year + 1):
            start_date = f"{year}-01-01"
            end_date = f"{year}-12-31"
            try:
                meetings = self._fetch_calendar(start_date, end_date)
                for m in meetings:
                    if m.escribe_id not in seen_ids:
                        seen_ids.add(m.escribe_id)
                        all_meetings.append(m)
            except Exception as e:
                logger.warning(f"Failed to fetch meetings for {year}: {e}")

        logger.info(
            f"Discovered {len(all_meetings)} meetings, "
            f"{sum(1 for m in all_meetings if m.video_url)} with video"
        )
        return all_meetings

    def _fetch_calendar(
        self, start_date: str, end_date: str
    ) -> list[DiscoveredMeeting]:
        """Call the eScribe calendar AJAX endpoint."""
        url = f"{self.portal_url}{CALENDAR_ENDPOINT}"
        payload = {
            "calendarStartDate": start_date,
            "calendarEndDate": end_date,
        }

        resp = self.session.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        results: list[DiscoveredMeeting] = []
        for item in data.get("d", []):
            meeting = self._parse_meeting(item)
            if meeting:
                results.append(meeting)

        return results

    def _parse_meeting(self, item: dict) -> DiscoveredMeeting | None:
        """Parse a single meeting entry from the calendar API response."""
        escribe_id = item.get("ID", "")
        if not escribe_id:
            return None

        # Parse date: format is "2025/04/28 08:40:00"
        date_str = item.get("StartDate", "")
        try:
            meeting_date = datetime.strptime(date_str, "%Y/%m/%d %H:%M:%S")
        except (ValueError, TypeError):
            meeting_date = datetime.now()

        # Find video URL in MeetingDocumentLink array
        video_url = None
        agenda_url = None
        minutes_url = None

        for doc in item.get("MeetingDocumentLink", []):
            title = doc.get("Title", "")
            doc_url = doc.get("Url", "")
            doc_type = doc.get("Type", "")

            # Normalize relative URLs
            if doc_url.startswith("./"):
                doc_url = f"{self.portal_url}/{doc_url[2:]}"
            elif doc_url and not doc_url.startswith("http"):
                doc_url = f"{self.portal_url}/{doc_url}"

            if title == "Video" and doc_url:
                video_url = doc_url
            elif doc_type == "Agenda" and doc.get("Format") == ".pdf" and not agenda_url:
                agenda_url = doc_url
            elif doc_type == "PostMinutes" and doc.get("Format") == ".pdf" and not minutes_url:
                minutes_url = doc_url

        return DiscoveredMeeting(
            escribe_id=escribe_id,
            title=item.get("MeetingName", "Unknown Meeting"),
            meeting_type=item.get("MeetingType", "Unknown"),
            meeting_date=meeting_date,
            video_url=video_url,
            agenda_url=agenda_url,
            minutes_url=minutes_url,
        )

    def get_hls_url(self, player_url: str) -> str | None:
        """Extract HLS stream URL from an ISI video player page.

        The player page contains:
          <div id="isi_player" data-client_id="vernon"
               data-file_name="Compact Encoder_REG-CM_2026-02-09-04-33.mp4">

        VOD HLS URL pattern (from isi_player.js + isi_cdn.js):
          nginx_vod_servers = ['vod.isilive.ca']
          If filename has spaces: /nospace/hls/{client_id}/{nospace_name}/index.m3u8
            where nospace_name = filename with spaces replaced by '-_-'
          If no spaces: /hls/{client_id}/{filename}/index.m3u8
        """
        try:
            resp = self.session.get(player_url, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch player page {player_url}: {e}")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        player_div = soup.find("div", id="isi_player")
        if not player_div:
            logger.error(f"No #isi_player div found at {player_url}")
            return None

        client_id = player_div.get("data-client_id", "vernon")
        file_name = player_div.get("data-file_name", "")
        if not file_name:
            logger.error(f"No data-file_name in player div at {player_url}")
            return None

        # Build HLS URL following ISI player logic
        if " " in file_name or "+" in file_name or "%20" in file_name:
            nospace_name = file_name.replace(" ", "-_-").replace("+", "-_-").replace("%20", "-_-")
            hls_url = f"https://{VOD_SERVER}/nospace/hls/{client_id}/{nospace_name}/index.m3u8"
        else:
            hls_url = f"https://{VOD_SERVER}/hls/{client_id}/{file_name}/index.m3u8"

        # Verify the URL is reachable
        try:
            check = self.session.head(hls_url, timeout=10)
            if check.status_code == 200:
                logger.info(f"HLS URL verified: {hls_url}")
                return hls_url
        except Exception:
            pass

        # Try fallback patterns
        fallback_servers = ["cdn1.isilive.ca", "cdn2.isilive.ca"]
        for server in fallback_servers:
            if " " in file_name:
                nospace_name = file_name.replace(" ", "-_-").replace("+", "-_-")
                fallback_url = f"https://{server}/nospace/hls/{client_id}/{nospace_name}/index.m3u8"
            else:
                fallback_url = f"https://{server}/hls/{client_id}/{file_name}/index.m3u8"
            try:
                check = self.session.head(fallback_url, timeout=10)
                if check.status_code == 200:
                    logger.info(f"HLS URL verified (fallback): {fallback_url}")
                    return fallback_url
            except Exception:
                continue

        # Try Wowza pattern as last resort
        wowza_url = f"https://{VOD_SERVER}/vod/_definst_/{client_id}/{file_name}/playlist.m3u8"
        try:
            check = self.session.head(wowza_url, timeout=10)
            if check.status_code == 200:
                logger.info(f"HLS URL verified (Wowza): {wowza_url}")
                return wowza_url
        except Exception:
            pass

        logger.warning(f"Could not verify HLS URL for {file_name}")
        # Return the primary URL anyway — ffmpeg may handle redirects
        if " " in file_name:
            nospace_name = file_name.replace(" ", "-_-").replace("+", "-_-")
            return f"https://{VOD_SERVER}/nospace/hls/{client_id}/{nospace_name}/index.m3u8"
        return f"https://{VOD_SERVER}/hls/{client_id}/{file_name}/index.m3u8"
