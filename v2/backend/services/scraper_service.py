import asyncio
import logging
import re
import sys
import unicodedata
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Callable

from playwright.async_api import async_playwright, Page, Browser
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

CITY_AREAS: dict[str, list[str]] = {
    "mumbai": [
        "Andheri", "Bandra", "Borivali", "Dadar", "Ghatkopar",
        "Goregaon", "Kandivali", "Kurla", "Malad", "Mulund",
        "Powai", "Versova", "Vikhroli", "Vile Parle", "Worli",
        "Colaba", "Fort", "Chembur", "Thane", "Navi Mumbai",
    ],
    "delhi": [
        "Connaught Place", "Dwarka", "Janakpuri", "Karol Bagh",
        "Lajpat Nagar", "Nehru Place", "Rohini", "Saket",
        "South Extension", "Vasant Kunj",
    ],
    "bangalore": [
        "Koramangala", "Indiranagar", "Whitefield", "Jayanagar",
        "Marathahalli", "BTM Layout", "HSR Layout", "Rajajinagar",
        "Yelahanka", "Electronic City",
    ],
    "hyderabad": [
        "Banjara Hills", "Jubilee Hills", "Kukatpally", "LB Nagar",
        "Madhapur", "Secunderabad", "SR Nagar", "Uppal",
    ],
    "chennai": [
        "Anna Nagar", "Adyar", "Chromepet", "Guindy", "Mylapore",
        "Porur", "T Nagar", "Velachery",
    ],
    "pune": [
        "Aundh", "Baner", "Hadapsar", "Hinjawadi", "Kothrud",
        "Shivajinagar", "Viman Nagar", "Wakad",
    ],
    "kolkata": [
        "Behala", "Dum Dum", "Gariahat", "New Town", "Park Street",
        "Salt Lake", "Shyambazar",
    ],
    "ahmedabad": [
        "Bopal", "CG Road", "Maninagar", "Navrangpura",
        "Prahlad Nagar", "Satellite", "Vastrapur",
    ],
    "surat": [
        "Adajan", "Athwa", "Katargam", "Piplod",
        "Rander", "Udhna", "Vesu",
    ],
    "vadodara": [
        "Alkapuri", "Fatehgunj", "Gotri", "Karelibaug",
        "Manjalpur", "Sayajigunj", "Subhanpura",
    ],
}

def _get_area_list(city: str) -> list[str]:
    return CITY_AREAS.get(city.strip().lower(), [])

# Strip leading emoji and other pictographs from the address, which can interfere with geocoding and city extraction.

def _strip_leading_emoji(text: str) -> str:
    return re.sub(
        r"^[\U00002000-\U0001FFFF\U000FE000-\U000FEFFF"
        r"\u2600-\u26FF\u2700-\u27BF\uFE00-\uFE0F\s]+",
        "",
        text,
    ).strip()

def _extract_city_from_address(address: str) -> str:
    if not address:
        return ""
    addr = re.sub(r"\s*,\s*", ", ", address.strip())
    addr_no_pin = re.sub(r",?\s*\d{6}.*$", "", addr).strip().rstrip(",").strip()
    parts = [p.strip() for p in addr_no_pin.split(",") if p.strip()]
    return parts[-1] if parts else ""

def normalize_phone(raw: str) -> str:
    cleaned = re.sub(r"[^\d\+\-\s]", "", raw).strip()
    return re.sub(r"\s{2,}", " ", cleaned)

def _normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return re.sub(r"\s+", " ", text).strip().lower()

def address_matches_location(
    address: str, city: str, state: str, threshold: int = 55
) -> bool:
# Returns True if the address plausibly matches the city and state.
    if not address:
        return True
    addr_norm = _normalize_text(address)
    city_norm = _normalize_text(city)
    state_norm = _normalize_text(state)

    # State-only mode: just confirm state appears somewhere in the address
    if not city_norm and state_norm:
        if state_norm in addr_norm:
            return True
        # fuzzy check for state name
        tokens = addr_norm.split()
        for size in (1, 2):
            for i in range(len(tokens) - size + 1):
                chunk = " ".join(tokens[i : i + size])
                if fuzz.ratio(state_norm, chunk) >= threshold:
                    return True
        return False

    if city_norm in addr_norm or state_norm in addr_norm:
        return True

    # Neighbourhood loop is only needed when NO city is given — if a city was
    # provided, the direct substring check above already caught it or it's
    # genuinely a mismatch.  Skipping this when city is set avoids iterating
    # all area names on every lead.
    if not city_norm:
        for area in _get_area_list(city):
            if _normalize_text(area) in addr_norm:
                return True

    # Fuzzy fallback — catches typos / transliterations in the address
    tokens = addr_norm.split()
    for size in (1, 2, 3):
        for i in range(len(tokens) - size + 1):
            chunk = " ".join(tokens[i : i + size])
            if fuzz.ratio(city_norm, chunk) >= threshold:
                return True
            if state_norm and fuzz.ratio(state_norm, chunk) >= threshold:
                return True
    return False

# data models
@dataclass
class Lead:
    name: str = ""
    category: str = ""
    address: str = ""
    city: str = ""
    phone: str = ""
    website: str = ""
    rating: str = ""
    review_count: str = ""
    search_query: str = ""
    location_query: str = ""
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class ScraperFilters:
    min_rating: float = 0.0
    require_phone: bool = False
    require_website: bool = False
    categories: list[str] = field(default_factory=list)

def passes_filters(lead: Lead, filters: ScraperFilters) -> bool:
    if filters.require_phone and not lead.phone:
        return False
    if filters.require_website and not lead.website:
        return False
    if lead.rating:
        try:
            r = float(lead.rating.replace(",", "."))
            if r < filters.min_rating:
                return False
        except ValueError:
            pass
    if filters.categories:
        cat_lower = lead.category.lower()
        if not any(c.lower() in cat_lower for c in filters.categories):
            return False
    return True

# scraper implementation

class GoogleMapsScraper:
    def __init__(
        self,
        max_results: int = 60,
        concurrency: int = 1,
        filters: Optional[ScraperFilters] = None,
        progress_cb: Optional[Callable[[dict], None]] = None,
        expand_large_cities: bool = True,
    ):
        self.max_results = max_results
        self.concurrency = concurrency
        self.filters = filters or ScraperFilters()
        self.progress_cb = progress_cb or (lambda x: None)
        self.expand_large_cities = expand_large_cities
        self._cancelled = False

    def stop(self):
        self._cancelled = True

    def _emit(self, event: str, **kwargs):
        self.progress_cb({"event": event, "ts": datetime.now().isoformat(), **kwargs})

    async def scrape_all(
        self,
        keywords: list[str],
        city: str = "",
        state: str = "",
    ) -> list[Lead]:
        return await asyncio.to_thread(self._run_in_thread, keywords, city, state)

    def _run_in_thread(self, keywords: list[str], city: str, state: str) -> list[Lead]:
        if sys.platform == "win32":
            loop = asyncio.ProactorEventLoop()
        else:
            loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._scrape_all_async(keywords, city, state))
        finally:
            loop.close()

    async def _scrape_all_async(self, keywords: list[str], city: str, state: str) -> list[Lead]:
        queries = self._build_queries(keywords, city, state)
        all_leads: list[Lead] = []
        seen_keys: set[str] = set()

        self._emit("start", total_queries=len(queries))

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                sem = asyncio.Semaphore(self.concurrency)
                tasks = [self._scrape_query(browser, q, city, state, sem) for q in queries]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for batch in results:
                    if isinstance(batch, Exception):
                        logger.warning("Query batch error: %s", batch)
                        continue
                    for lead in batch:
                        name_norm = _normalize_text(lead.name)
                        addr_norm = _normalize_text(lead.address)
                        if lead.phone:
                            key = lead.phone
                        elif name_norm and addr_norm:
                            key = f"{name_norm}|{addr_norm}"
                        elif name_norm:
                            key = name_norm
                        else:
                            continue   # no usable identity, skip
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        all_leads.append(lead)
                        self._emit(
                            "lead_found",
                            name=lead.name,
                            phone=lead.phone,
                            city=lead.city,
                            query=lead.search_query,
                        )
            finally:
                await browser.close()

        self._emit("done", total=len(all_leads))
        return all_leads

    def _build_queries(self, keywords: list[str], city: str, state: str) -> list[str]:
        queries: list[str] = []
        location = " ".join(filter(None, [city, state]))
        areas = _get_area_list(city) if (self.expand_large_cities and not city.strip()) else []

        for kw in keywords:
            kw = kw.strip()
            if not kw:
                continue
            queries.append(f"{kw} in {location}" if location else kw)
            for area in areas:
                area_loc = f"{area}, {location}" if location else area
                queries.append(f"{kw} in {area_loc}")

        return queries

    async def _scrape_query(
        self, browser: Browser, query: str, city: str, state: str, sem: asyncio.Semaphore
    ) -> list[Lead]:
        async with sem:
            if self._cancelled:
                return []
            self._emit("query_start", query=query)
            ctx = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/136.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
                locale="en-US",
            )
            try:
                page = await ctx.new_page()
                leads = await self._scrape_page(page, query, city, state)
                self._emit("query_done", query=query, count=len(leads))
                return leads
            except Exception as exc:
                logger.error("Error scraping '%s': %s", query, exc)
                self._emit("query_error", query=query, error=str(exc))
                return []
            finally:
                await ctx.close()

    _ITEM_SELECTOR_CANDIDATES: list[str] = [
        # Pattern 1 (2024-2025): direct children of feed that have jsaction
        'div[role="feed"] > div > div[jsaction]',
        # Pattern 2: any jsaction div inside feed (looser nesting)
        'div[role="feed"] div[jsaction*="mouseover"]',
        # Pattern 3: anchor tags with a /maps/place/ href — very stable
        'div[role="feed"] a[href*="/maps/place/"]',
        # Pattern 4: aria-label on the card itself
        'div[role="feed"] div[aria-label]',
    ]

    async def _dismiss_consent_popup(self, page: Page) -> None:
        selectors = [
            'button[aria-label*="Accept"]',
            'button[aria-label*="accept"]',
            'form[action*="consent"] button',
            'button:has-text("Accept all")',
            'button:has-text("I agree")',
            '#L2AGLb',          # classic "I agree" button id on google.com
        ]
        for sel in selectors:
            try:
                btn = page.locator(sel)
                if await btn.count() > 0:
                    await btn.first.click(timeout=3_000)
                    logger.debug("Consent popup dismissed via: %s", sel)
                    await page.wait_for_timeout(800)
                    return
            except Exception:
                continue

    async def _resolve_item_locator(self, page: Page) -> str:
# Google Maps frequently changes its DOM structure. We maintain a list of candidate selectors and pick the one that matches the current page. This makes the scraper more resilient to UI changes.
        for sel in self._ITEM_SELECTOR_CANDIDATES:
            try:
                count = await page.locator(sel).count()
                if count > 0:
                    logger.debug("Item selector resolved: %s (%d elements)", sel, count)
                    return sel
            except Exception:
                continue
        logger.warning("No item selector matched — falling back to candidate 0")
        return self._ITEM_SELECTOR_CANDIDATES[0]

    async def _scrape_page(self, page: Page, query: str, city: str, state: str) -> list[Lead]:
        url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
        await page.goto(url, wait_until="domcontentloaded", timeout=60_000)

        # Consent / cookie popup 
        await self._dismiss_consent_popup(page)

        # Wait for the results feed
        feed_locator = 'div[role="feed"]'
        try:
            await page.wait_for_selector(feed_locator, timeout=20_000)
        except Exception:
            # Debug: log how many feed children exist and save a screenshot
            children = await page.locator(f"{feed_locator} > *").count()
            logger.warning(
                "Feed not found for query '%s'. Feed children visible: %d. "
                "Saving debug screenshot.",
                query, children,
            )
            try:
                safe_name = re.sub(r"[^\w]", "_", query)[:40]
                await page.screenshot(path=f"debug_{safe_name}.png", full_page=False)
            except Exception:
                pass
            return []

        # Determine the best item selector for this page load
        item_locator = await self._resolve_item_locator(page)
        feed = page.locator(feed_locator)

        # Scroll to load more results 
        MAX_SCROLL_ITERS = 30
        NO_CHANGE_TOLERANCE = 3
        stall_count = 0
        prev_count = 0

        for _ in range(MAX_SCROLL_ITERS):
            if self._cancelled:
                break
            listings = await page.locator(item_locator).all()
            curr_count = len(listings)
            if curr_count >= self.max_results:
                break
            if curr_count == prev_count:
                stall_count += 1
                if stall_count >= NO_CHANGE_TOLERANCE:
                    break
            else:
                stall_count = 0
            prev_count = curr_count
            try:
                await feed.evaluate("el => el.scrollBy(0, 2400)")
            except Exception:
                pass
            await page.wait_for_timeout(1_800)

        listings = await page.locator(item_locator).all()
        logger.debug("Total listing cards found for '%s': %d", query, len(listings))

        leads: list[Lead] = []
        for listing in listings[: self.max_results]:
            if self._cancelled:
                break
            lead = await self._extract_listing(page, listing, query, city, state)
            if lead is None:
                continue
            if not passes_filters(lead, self.filters):
                continue
            leads.append(lead)
        return leads

    async def _extract_listing(
        self, page: Page, listing, query: str, city: str, state: str
    ) -> Optional[Lead]:
        expected_name: str = ""
        try:
            lbl = await listing.get_attribute("aria-label", timeout=2_000)
            if lbl:
                expected_name = lbl.strip()
        except Exception:
            pass

        for attempt in range(2):
            try:
                await listing.click()
                if expected_name:
                    prefix = expected_name[:30].lower()
                    try:
                        await page.wait_for_function(
                            """(prefix) => {
                                const h1 = document.querySelector('h1');
                                return h1 && h1.textContent.toLowerCase().includes(prefix);
                            }""",
                            arg=prefix,
                            timeout=8_000,
                        )
                    except Exception:
                        await page.wait_for_selector("h1.DUwDvf, h1", timeout=4_000)
                else:
                    try:
                        await page.wait_for_selector("h1.DUwDvf", timeout=5_000)
                    except Exception:
                        await page.wait_for_selector(
                            'div[role="main"] h1, aside h1, h1', timeout=5_000
                        )
                break
            except Exception:
                if attempt == 1:
                    return None
                await page.wait_for_timeout(800)

        # Safe helpers

        async def safe_text(*selectors: str, timeout: int = 3_000) -> str:
            for sel in selectors:
                try:
                    el = page.locator(sel)
                    if await el.count() > 0:
                        text = (await el.first.inner_text(timeout=timeout)).strip()
                        if text:
                            return text
                except Exception:
                    continue
            return ""

        async def safe_attr(*selectors_and_attr, timeout: int = 3_000) -> str:
            for item in selectors_and_attr:
                if isinstance(item, tuple):
                    sel, attr = item
                else:
                    sel, attr = item, "href"
                try:
                    el = page.locator(sel)
                    if await el.count() > 0:
                        val = await el.first.get_attribute(attr, timeout=timeout)
                        if val and val.strip():
                            return val.strip()
                except Exception:
                    continue
            return ""

        # Name
        name = await safe_text(
            "h1.DUwDvf",                        # classic
            'div[role="main"] h1',              # role-based fallback
            "aside h1",                         # sidebar layout
            "h1",                               # last resort
        )
        if not name:
            return None

        raw_address = await safe_text(
            'button[data-item-id="address"]',
            '[data-item-id="address"]',
            'button[aria-label*="Address"]',
            '[aria-label*="Address"]',
        )
        address = _strip_leading_emoji(raw_address)

        # Phone
        phone_raw = await safe_text(
            'button[data-item-id^="phone"]',
            '[data-item-id^="phone"]',
            'button[aria-label*="Phone"]',
            '[aria-label*="Phone"]',
        )
        phone = normalize_phone(phone_raw)

        # Website
        website = await safe_attr(
            ('a[data-item-id="authority"]', "href"),
            ('[data-item-id="authority"]', "href"),
            ('a[aria-label*="Website"]', "href"),
            ('a[aria-label*="website"]', "href"),
        )
        if website and "google.com" in website:
            website = ""

        # Rating
        # aria-hidden span inside the rating block holds the plain number "4.3"
        rating = await safe_text(
            'div.F7nice span[aria-hidden="true"]',
            'span.ceNzKf[aria-hidden="true"]',      # alternate class seen 2025
            'span[aria-hidden="true"]',
        )
        # Sanity: must look like a number
        if rating and not re.match(r"^\d[\d.,]*$", rating.strip()):
            rating = ""

        # Review count
        review_label = await safe_attr(
            ('div.F7nice span[aria-label]', "aria-label"),
            ('span[aria-label*="review"]', "aria-label"),
            ('span[aria-label*="rating"]', "aria-label"),
        )
        if review_label:
            review_count = re.sub(
                r"\s*(reviews?|ratings?)\s*$", "", review_label, flags=re.IGNORECASE
            ).strip().strip("()")
        else:
            review_count = ""

        # Category
        category = await safe_text(
            "button.DkEaL",                         # classic (pre-2025)
            "div.skqShb span",                      # 2024 layout
            'button[jsaction*="category"]',         # jsaction fallback
            'span.YkuOqf',                          # another known class
        )

        # Location filter
        if (city or state) and address:
            if not address_matches_location(address, city, state):
                logger.debug("Filtered out '%s' — address mismatch", name)
                return None

        extracted_city = _extract_city_from_address(address)

        return Lead(
            name=name,
            category=category,
            address=address,
            city=extracted_city,
            phone=phone,
            website=website,
            rating=rating,
            review_count=review_count,
            search_query=query,
            location_query=f"{city}, {state}".strip(", "),
        )