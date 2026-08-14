"""
Central configuration for the Google Maps Lead Intelligence prototype.

This is a local prototype configuration.
All tunable values are kept here so the rest of the project
does not need to hard-code configuration values.
"""

import os
from pathlib import Path


# =============================================================================
# PROJECT PATHS
# =============================================================================

# Project root:
# google-maps-playwright-main/
BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
DATA_RAW_DIR = DATA_DIR / "raw"
DATA_PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"


# Create directories required by the prototype.
# exist_ok=True means this is safe when they already exist.
for directory in (
    DATA_DIR,
    DATA_RAW_DIR,
    DATA_PROCESSED_DIR,
    OUTPUT_DIR,
    LOG_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)


# =============================================================================
# PIPELINE DEFAULTS
# =============================================================================

# Number of concurrent async workers.
DEFAULT_WORKERS = int(
    os.environ.get("DEFAULT_WORKERS", "3")
)

# Default number of businesses to discover.
DEFAULT_TARGET_LEADS = int(
    os.environ.get("DEFAULT_TARGET_LEADS", "20")
)

# Maximum time allowed for the actual enrichment operation of one record.
PER_RECORD_TIMEOUT = int(
    os.environ.get("PER_RECORD_TIMEOUT", "60")
)

# Maximum number of retries for transient failures.
MAX_RETRIES = int(
    os.environ.get("MAX_RETRIES", "2")
)

# Save partial progress after this many completed records.
CHECKPOINT_EVERY = int(
    os.environ.get("CHECKPOINT_EVERY", "5")
)

# Failure statuses eligible for retry.
RETRYABLE_STATUSES = {
    "TIMEOUT",
    "NAVIGATION_ERROR",
    "NETWORK_BLOCKED",
    "CONNECTION_REFUSED",
}


# =============================================================================
# PLAYWRIGHT / GOOGLE MAPS
# =============================================================================

# Run browser headless by default.
# Set HEADLESS=false when debugging visually.
HEADLESS = (
    os.environ.get("HEADLESS", "false").strip().lower() != "false"
)

# Maximum navigation timeout for Playwright.
NAV_TIMEOUT_MS = int(
    os.environ.get("NAV_TIMEOUT_MS", "30000")
)

# Delay between Google Maps result-feed scrolls.
MAPS_SCROLL_PAUSE_MS = int(
    os.environ.get("MAPS_SCROLL_PAUSE_MS", "900")
)

# Stop discovery after this many consecutive scrolls
# fail to produce useful new results.
MAX_SCROLL_ATTEMPTS_WITHOUT_NEW_RESULTS = int(
    os.environ.get(
        "MAX_SCROLL_ATTEMPTS_WITHOUT_NEW_RESULTS",
        "6",
    )
)


# =============================================================================
# WEBSITE ENRICHMENT
# =============================================================================

# Candidate internal pages to inspect.
# The homepage is represented by an empty string.
WEBSITE_PAGES_TO_INSPECT = [
    "",
    "contact",
    "contact-us",
    "about",
    "about-us",
    "team",
    "appointment",
    "locations",
]

# Maximum number of pages inspected for one website.
MAX_PAGES_PER_SITE = int(
    os.environ.get("MAX_PAGES_PER_SITE", "6")
)

# Timeout for an individual website HTTP request.
WEBSITE_REQUEST_TIMEOUT = int(
    os.environ.get("WEBSITE_REQUEST_TIMEOUT", "12")
)


# =============================================================================
# EMAIL VALIDATION
# =============================================================================

# Obvious placeholder/junk email values.
PLACEHOLDER_EMAILS = {
    "info@yourdomain.com",
    "example@example.com",
    "example@mysite.com",
    "test@test.com",
    "name@example.com",
    "youremail@example.com",
    "email@example.com",
    "sample@example.com",
    "user@example.com",
    "test@example.com",
    "demo@example.com",
    "admin@example.com",
    "hello@example.com",
}


# =============================================================================
# SOCIAL PROFILE FILTERING
# =============================================================================

# URLs/patterns that should not be considered useful business profiles.
IGNORED_SOCIAL_PATTERNS = [
    "facebook.com/profile.php",
    "facebook.com/sharer",
    "facebook.com/share",
    "instagram.com/accounts",
    "instagram.com/explore",
    "twitter.com/intent",
    "twitter.com/share",
    "x.com/intent",
    "x.com/share",
    "linkedin.com/sharing",
    "linkedin.com/sharearticle",
]


# =============================================================================
# DIRECTORY DETECTION
# =============================================================================

# Domains that may represent external business directories/profiles.
KNOWN_DIRECTORY_DOMAINS = [
    "practo.com",
    "justdial.com",
    "sulekha.com",
    "indiamart.com",
    "yelp.com",
    "yellowpages.com",
    "tripadvisor.com",
    "urbanpro.com",
    "zomato.com",
    "swiggy.com",
    "healthgrades.com",
    "zocdoc.com",
]


# =============================================================================
# LEAD SCORING
# =============================================================================

# Transparent prototype scoring.
SCORING = {
    "phone": 20,
    "email_validated": 25,
    "email_confidence_high": 10,
    "email_confidence_medium": 5,
    "website": 10,
    "instagram": 5,
    "facebook": 5,
    "linkedin": 8,
    "twitter": 3,
    "youtube": 3,
    "full_address": 5,
    "rating_45_plus": 5,
    "three_plus_contact_routes": 5,
}

MAX_SCORE = 100


# Score bands:
# (minimum_score, maximum_score, grade, label)
GRADE_BANDS = [
    (85, 100, "A", "High-value"),
    (70, 84, "B", "Good"),
    (50, 69, "C", "Partial"),
    (0, 49, "D", "Needs enrichment"),
]


# =============================================================================
# API / CORS
# =============================================================================

API_HOST = os.environ.get(
    "API_HOST",
    "127.0.0.1",
)

API_PORT = int(
    os.environ.get(
        "API_PORT",
        "8000",
    )
)

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


# =============================================================================
# PIPELINE OUTPUT FILES
# =============================================================================

RAW_RESULTS_FILE = DATA_RAW_DIR / "discovered_leads.json"
PROCESSED_RESULTS_FILE = DATA_PROCESSED_DIR / "processed_leads.json"

PARTIAL_RESULTS_FILE = OUTPUT_DIR / "leads_partial.json"

FINAL_JSON_FILE = OUTPUT_DIR / "leads.json"
FINAL_CSV_FILE = OUTPUT_DIR / "leads.csv"
FINAL_EXCEL_FILE = OUTPUT_DIR / "leads.xlsx"
SUMMARY_FILE = OUTPUT_DIR / "summary.json"

LOG_FILE = LOG_DIR / "pipeline.log"


# =============================================================================
# HELPER FUNCTION
# =============================================================================

def get_config_summary() -> dict:
    """
    Return the important runtime configuration.

    Useful for debugging and displaying configuration
    information in logs without exposing environment secrets.
    """
    return {
        "base_dir": str(BASE_DIR),
        "data_raw_dir": str(DATA_RAW_DIR),
        "data_processed_dir": str(DATA_PROCESSED_DIR),
        "output_dir": str(OUTPUT_DIR),
        "log_dir": str(LOG_DIR),
        "default_workers": DEFAULT_WORKERS,
        "default_target_leads": DEFAULT_TARGET_LEADS,
        "per_record_timeout": PER_RECORD_TIMEOUT,
        "max_retries": MAX_RETRIES,
        "checkpoint_every": CHECKPOINT_EVERY,
        "headless": HEADLESS,
        "nav_timeout_ms": NAV_TIMEOUT_MS,
        "maps_scroll_pause_ms": MAPS_SCROLL_PAUSE_MS,
        "max_scroll_attempts_without_new_results": (
            MAX_SCROLL_ATTEMPTS_WITHOUT_NEW_RESULTS
        ),
        "max_pages_per_site": MAX_PAGES_PER_SITE,
        "website_request_timeout": WEBSITE_REQUEST_TIMEOUT,
        "api_host": API_HOST,
        "api_port": API_PORT,
        "cors_origins": CORS_ORIGINS,
    }