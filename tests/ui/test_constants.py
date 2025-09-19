"""Test constants for UI tests - centralized configuration"""

# =============================================================================
# TIMEOUTS
# =============================================================================

# Maximum wait timeout for all UI tests (5 seconds)
MAX_WAIT_MS = 5000

# Minimal wait for UI transitions that can't be avoided
MINIMAL_WAIT_MS = 100

# Server startup timeout (30 seconds total)
SERVER_STARTUP_TIMEOUT_SECONDS = 30
SERVER_STARTUP_RETRY_DELAY = 1

# =============================================================================
# VIEWPORTS
# =============================================================================

# Standard desktop viewport
DESKTOP_VIEWPORT = {"width": 1400, "height": 900}

# Standard mobile viewport (iPhone 12 Pro)
MOBILE_VIEWPORT = {"width": 390, "height": 844}

# Alternative desktop size for compatibility
DESKTOP_VIEWPORT_ALT = {"width": 1200, "height": 800}

# Alternative mobile size for compatibility
MOBILE_VIEWPORT_ALT = {"width": 375, "height": 667}

# =============================================================================
# COMMON SELECTORS
# =============================================================================

# Feed item selectors
DESKTOP_FEED_ITEMS = "li[data-testid='feed-item']"
MOBILE_FEED_ITEMS = "li[data-testid='feed-item']"
ANY_FEED_ITEMS = "li[data-testid='feed-item'], li[data-testid='feed-item']"

# Layout selectors
DESKTOP_LAYOUT = "#app-root"
MOBILE_LAYOUT = "#app-root"
ANY_LAYOUT = "#app-root, #app-root"

# Navigation selectors
DESKTOP_ICON_BAR = "#icon-bar"
MOBILE_ICON_BAR = "#icon-bar"
ANY_ICON_BAR = "#icon-bar, #icon-bar"

# Content areas
DESKTOP_FEEDS_CONTENT = "#desktop-feeds-content"
MOBILE_SIDEBAR = "#feeds"
MAIN_CONTENT = "#main-content"
APP_ROOT = '[data-testid="app-root"]'

# Item detail views
DESKTOP_ITEM_DETAIL = "#desktop-item-detail"
MOBILE_ITEM_DETAIL = "#mobile-item-detail"
ANY_ITEM_DETAIL = "#desktop-item-detail, #mobile-item-detail"

# =============================================================================
# TEST DATA
# =============================================================================

# Safe test feed URLs that won't cause external dependencies
TEST_FEED_URL_SAFE = "https://httpbin.org/xml"
TEST_FEED_URL_INVALID = "not-a-url"

# =============================================================================
# RETRY CONFIGURATION
# =============================================================================

# Maximum retries for flaky operations
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1

# Page load retries for CI environments
PAGE_LOAD_MAX_RETRIES = 10
PAGE_LOAD_RETRY_DELAY = 3