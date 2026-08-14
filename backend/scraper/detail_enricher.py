"""
Stage 2: Detail Enrichment.

Opens each business's Maps URL in its own page/tab and pulls richer detail
using aria-labels, roles and text relationships (not brittle CSS classes).

One stuck record never freezes the whole pipeline - callers wrap this with
a hard per-record timeout.
"""

import logging
import re
from typing import Optional

from playwright.async_api import (
    Page,
    TimeoutError as PWTimeoutError,
)

from backend.config import NAV_TIMEOUT_MS

from backend.utils.validators import (
    looks_like_rating,
    looks_like_phone,
    looks_like_address,
    looks_like_hours,
    clean_phone,
    extract_pincode,
    is_real_business_website,
    is_google_ad_url,
)

from backend.utils.helpers import (
    normalize_whitespace,
    extract_city_from_address,
)


logger = logging.getLogger(
    "detail_enricher"
)


# =============================================================================
# GENERIC ARIA HELPER
# =============================================================================

async def _get_aria_prefixed(
    page: Page,
    prefix: str,
) -> str:
    """
    Find an element whose aria-label starts with the given prefix.

    Example:
        Address: Shop No 10, Pune

    Returns:
        Shop No 10, Pune
    """

    try:
        el = page.locator(
            f'[aria-label^="{prefix}"]'
        ).first

        if await el.count() == 0:
            return ""

        aria = (
            await el.get_attribute(
                "aria-label"
            )
            or ""
        )

        if aria.startswith(prefix):
            return normalize_whitespace(
                aria[len(prefix):]
            )

        return normalize_whitespace(
            aria
        )

    except Exception:
        return ""


# =============================================================================
# RATING / REVIEW HELPERS
# =============================================================================

def _clean_review_number(
    value: str,
) -> Optional[str]:
    """
    Normalize a review-count value.

    Examples:
        "3,914" -> "3914"
        "(80)"  -> "80"
        "80"    -> "80"
    """

    if not value:
        return None

    value = str(value).strip()

    value = value.strip(
        " \t\r\n()[]{}"
    )

    value = value.replace(
        ",",
        "",
    )

    if not value.isdigit():
        return None

    return value


def _extract_rating_and_reviews_from_text(
    text: str,
):
    """
    Extract rating and review count from ordinary visible text.

    Supported examples:

        4.9 stars 1,245 Reviews
        4.9 1,245 Reviews
        4.9 (1,245)
        4.9 ★★★★★ (80)
    """

    if not text:
        return None, None

    text = normalize_whitespace(
        text
    )

    rating = None
    review_count = None

    # -------------------------------------------------------------------------
    # Pattern 1:
    # 4.9 stars 1,245 Reviews
    # -------------------------------------------------------------------------

    match = re.search(
        r"\b([0-5](?:\.\d)?)\s*stars?\s+([\d,]+)\s+reviews?\b",
        text,
        re.IGNORECASE,
    )

    if match:
        candidate_rating = (
            match.group(1)
        )

        candidate_reviews = (
            match.group(2)
        )

        if looks_like_rating(
            candidate_rating
        ):
            rating = candidate_rating

        review_count = _clean_review_number(
            candidate_reviews
        )

        return rating, review_count

    # -------------------------------------------------------------------------
    # Pattern 2:
    # 4.9 1,245 Reviews
    # -------------------------------------------------------------------------

    match = re.search(
        r"\b([0-5](?:\.\d)?)\s+([\d,]+)\s+reviews?\b",
        text,
        re.IGNORECASE,
    )

    if match:
        candidate_rating = (
            match.group(1)
        )

        candidate_reviews = (
            match.group(2)
        )

        if looks_like_rating(
            candidate_rating
        ):
            rating = candidate_rating

        review_count = _clean_review_number(
            candidate_reviews
        )

        return rating, review_count

    # -------------------------------------------------------------------------
    # Pattern 3:
    # 4.9 (1,245)
    # -------------------------------------------------------------------------

    match = re.search(
        r"\b([0-5](?:\.\d)?)\s*\(\s*([\d,]+)\s*\)",
        text,
    )

    if match:
        candidate_rating = (
            match.group(1)
        )

        candidate_reviews = (
            match.group(2)
        )

        if looks_like_rating(
            candidate_rating
        ):
            rating = candidate_rating

        review_count = _clean_review_number(
            candidate_reviews
        )

        return rating, review_count

    # -------------------------------------------------------------------------
    # Pattern 4:
    # rating followed by star glyphs and "(80)"
    #
    # Example from the screenshot:
    #
    #     4.9 ★★★★★ (80)
    # -------------------------------------------------------------------------

    match = re.search(
        r"\b([0-5](?:\.\d)?)\b"
        r".{0,20}?"
        r"\(\s*([\d,]+)\s*\)",
        text,
        re.DOTALL,
    )

    if match:
        candidate_rating = (
            match.group(1)
        )

        candidate_reviews = (
            match.group(2)
        )

        if looks_like_rating(
            candidate_rating
        ):
            rating = candidate_rating

        review_count = _clean_review_number(
            candidate_reviews
        )

        return rating, review_count

    return rating, review_count


async def _extract_rating_and_review_count(
    page: Page,
):
    """
    Multi-strategy Google Maps rating/review extraction.

    Strategies:

        1. aria-label containing stars/reviews
        2. dedicated review-related elements
        3. visible text around rating
        4. explicit "(80)" style count
    """

    rating = None
    review_count = None

    # =========================================================================
    # STRATEGY 1
    # aria-label containing stars
    # =========================================================================

    try:
        rating_elements = page.locator(
            '[aria-label*="stars" i]'
        )

        count = await rating_elements.count()

        for i in range(count):

            try:
                aria = (
                    await rating_elements
                    .nth(i)
                    .get_attribute(
                        "aria-label"
                    )
                    or ""
                )
            except Exception:
                continue

            if not aria:
                continue

            # -----------------------------------------------------------------
            # Rating
            # -----------------------------------------------------------------

            rating_match = re.search(
                r"\b([0-5](?:\.\d)?)\s*stars?\b",
                aria,
                re.IGNORECASE,
            )

            if (
                rating is None
                and rating_match
            ):
                candidate_rating = (
                    rating_match.group(1)
                )

                if looks_like_rating(
                    candidate_rating
                ):
                    rating = candidate_rating

            # -----------------------------------------------------------------
            # Review count explicitly mentioned
            # -----------------------------------------------------------------

            review_match = re.search(
                r"([\d,]+)\s+reviews?\b",
                aria,
                re.IGNORECASE,
            )

            if review_match:
                candidate_reviews = (
                    _clean_review_number(
                        review_match.group(1)
                    )
                )

                if candidate_reviews is not None:
                    review_count = candidate_reviews

            if (
                rating is not None
                and review_count is not None
            ):
                break

    except Exception:
        pass

    # =========================================================================
    # STRATEGY 2
    # Dedicated review-related elements
    #
    # Google Maps can expose the review count through:
    #   - aria-label containing "reviews"
    #   - links to /reviews
    #   - buttons associated with reviews
    # =========================================================================

    if review_count is None:

        try:

            review_elements = page.locator(
                '[aria-label*="review" i], '
                'a[href*="/reviews"], '
                'button[aria-label*="review" i]'
            )

            count = (
                await review_elements.count()
            )

            for i in range(count):

                try:

                    element = (
                        review_elements
                        .nth(i)
                    )

                    aria = (
                        await element.get_attribute(
                            "aria-label"
                        )
                        or ""
                    )

                    text = ""

                    try:
                        text = (
                            await element.inner_text()
                        )
                    except Exception:
                        pass

                    combined = normalize_whitespace(
                        f"{aria} {text}"
                    )

                    # ---------------------------------------------------------
                    # "1,245 reviews"
                    # ---------------------------------------------------------

                    match = re.search(
                        r"([\d,]+)\s+reviews?\b",
                        combined,
                        re.IGNORECASE,
                    )

                    if match:

                        candidate_reviews = (
                            _clean_review_number(
                                match.group(1)
                            )
                        )

                        if candidate_reviews:
                            review_count = (
                                candidate_reviews
                            )
                            break

                    # ---------------------------------------------------------
                    # "(80)"
                    # ---------------------------------------------------------

                    match = re.search(
                        r"\(\s*([\d,]+)\s*\)",
                        combined,
                    )

                    if match:

                        candidate_reviews = (
                            _clean_review_number(
                                match.group(1)
                            )
                        )

                        if candidate_reviews:
                            review_count = (
                                candidate_reviews
                            )
                            break

                except Exception:
                    continue

        except Exception:
            pass

    # =========================================================================
    # STRATEGY 3
    # Visible body text
    # =========================================================================

    if (
        rating is None
        or review_count is None
    ):

        try:

            body_text = await page.locator(
                "body"
            ).inner_text()

            body_text = normalize_whitespace(
                body_text
            )

            body_rating, body_reviews = (
                _extract_rating_and_reviews_from_text(
                    body_text
                )
            )

            if (
                rating is None
                and body_rating is not None
            ):
                rating = body_rating

            if (
                review_count is None
                and body_reviews is not None
            ):
                review_count = body_reviews

        except Exception:
            pass

    # =========================================================================
    # STRATEGY 4
    # Search dedicated text nodes for "reviews"
    # =========================================================================

    if review_count is None:

        try:

            review_nodes = page.locator(
                "text=/[0-9,]+\\s+reviews?/i"
            )

            node_count = (
                await review_nodes.count()
            )

            for i in range(node_count):

                try:

                    text = normalize_whitespace(
                        await review_nodes
                        .nth(i)
                        .inner_text()
                    )

                except Exception:
                    continue

                match = re.search(
                    r"([\d,]+)\s+reviews?\b",
                    text,
                    re.IGNORECASE,
                )

                if match:

                    candidate_reviews = (
                        _clean_review_number(
                            match.group(1)
                        )
                    )

                    if candidate_reviews:
                        review_count = (
                            candidate_reviews
                        )
                        break

        except Exception:
            pass

    # =========================================================================
    # FINAL SAFETY VALIDATION
    # =========================================================================

    if review_count is not None:

        try:

            review_int = int(
                review_count
            )

            # Review counts should be non-negative and
            # realistically below a very large threshold.
            if (
                review_int < 0
                or review_int > 10_000_000
            ):
                review_count = None

        except Exception:
            review_count = None

    return rating, review_count


# =============================================================================
# MAIN DETAIL ENRICHMENT
# =============================================================================

async def enrich_business_detail(
    page: Page,
    maps_url: str,
) -> dict:
    """
    Navigate to maps_url on the given page and extract detail fields.

    Returns a dict always containing:
        detail_status
        detail_error

    plus whatever fields could be extracted.
    """

    detail = {
        "full_address": "",
        "phone_raw": "",
        "phone": "",
        "website": "",
        "hours": "",
        "rating": "",
        "review_count": "",
        "city": "",
        "pincode": "",
        "detail_status": "SUCCESS",
        "detail_error": "",
    }

    # =========================================================================
    # NAVIGATION
    # =========================================================================

    try:

        await page.goto(
            maps_url,
            wait_until="domcontentloaded",
            timeout=NAV_TIMEOUT_MS,
        )

    except PWTimeoutError:

        detail[
            "detail_status"
        ] = "TIMEOUT"

        return detail

    except Exception as exc:

        msg = str(exc).lower()

        detail[
            "detail_status"
        ] = _classify_nav_error(
            msg
        )

        detail[
            "detail_error"
        ] = str(exc)[:200]

        return detail

    # =========================================================================
    # WAIT FOR BUSINESS DETAIL
    # =========================================================================

    try:

        await page.wait_for_selector(
            "h1",
            timeout=NAV_TIMEOUT_MS,
        )

    except PWTimeoutError:

        detail[
            "detail_status"
        ] = "TIMEOUT"

        return detail

    partial = False

    # =========================================================================
    # ADDRESS
    # =========================================================================

    try:

        addr = await _get_aria_prefixed(
            page,
            "Address: ",
        )

        if (
            addr
            and looks_like_address(
                addr
            )
        ):

            detail[
                "full_address"
            ] = addr

            detail[
                "city"
            ] = extract_city_from_address(
                addr
            )

            detail[
                "pincode"
            ] = extract_pincode(
                addr
            )

        else:

            partial = True

    except Exception:

        partial = True

    # =========================================================================
    # PHONE
    # =========================================================================

    try:

        phone_label = (
            await _get_aria_prefixed(
                page,
                "Phone: ",
            )
        )

        phone_val = phone_label

        if not phone_val:

            tel_link = page.locator(
                'a[href^="tel:"]'
            ).first

            if await tel_link.count() > 0:

                href = (
                    await tel_link.get_attribute(
                        "href"
                    )
                    or ""
                )

                phone_val = href.replace(
                    "tel:",
                    "",
                )

        if (
            phone_val
            and looks_like_phone(
                phone_val
            )
        ):

            detail[
                "phone_raw"
            ] = phone_val

            detail[
                "phone"
            ] = clean_phone(
                phone_val
            )

        else:

            partial = True

    except Exception:

        partial = True

    # =========================================================================
    # WEBSITE
    # =========================================================================

    try:

        site_el = page.locator(
            'a[data-item-id="authority"], '
            'a[aria-label^="Website: "]'
        ).first

        if await site_el.count() > 0:

            href = (
                await site_el.get_attribute(
                    "href"
                )
            )

            if (
                href
                and is_real_business_website(
                    href
                )
                and not is_google_ad_url(
                    href
                )
            ):

                detail[
                    "website"
                ] = href

    except Exception:

        pass

    # =========================================================================
    # RATING / REVIEW COUNT
    # =========================================================================

    try:

        (
            rating,
            review_count,
        ) = await _extract_rating_and_review_count(
            page
        )

        if rating is not None:

            detail[
                "rating"
            ] = rating

        if review_count is not None:

            detail[
                "review_count"
            ] = review_count

    except Exception as exc:

        logger.debug(
            "Rating/review extraction failed: %s",
            exc,
        )

    # =========================================================================
    # HOURS
    # =========================================================================

    try:

        hours_el = page.locator(
            '[aria-label*="Hide open hours" i], '
            '[aria-label*="hours" i]'
        ).first

        if await hours_el.count() > 0:

            hours_text = normalize_whitespace(
                await hours_el.get_attribute(
                    "aria-label"
                )
                or ""
            )

            if (
                hours_text
                and looks_like_hours(
                    hours_text
                )
            ):

                detail[
                    "hours"
                ] = hours_text

    except Exception:

        pass

    # =========================================================================
    # FINAL STATUS
    # =========================================================================

    if (
        partial
        and detail[
            "detail_status"
        ] == "SUCCESS"
    ):

        detail[
            "detail_status"
        ] = "PARTIAL"

    return detail


# =============================================================================
# NAVIGATION ERROR CLASSIFICATION
# =============================================================================

def _classify_nav_error(
    msg: str,
) -> str:

    if (
        "err_name_not_resolved"
        in msg
        or "dns"
        in msg
    ):

        return "DNS_ERROR"

    if (
        "err_connection_refused"
        in msg
    ):

        return "CONNECTION_REFUSED"

    if (
        "err_blocked"
        in msg
        or "net::err_blocked_by_client"
        in msg
    ):

        return "NETWORK_BLOCKED"

    if "timeout" in msg:

        return "TIMEOUT"

    return "NAVIGATION_ERROR"