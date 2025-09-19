"""RSS Reader built with FastHTML and MonsterUI - with auto-reload enabled"""

from fasthtml.common import *
from monsterui.all import *
import uuid
from datetime import datetime, timezone
import os
import time
import mistletoe
from bs4 import BeautifulSoup
import asyncio
import re
import logging
from .models import (
    SessionModel, FeedModel, FeedItemModel, UserItemModel, FolderModel,
    init_db, get_db, MINIMAL_MODE
)
from .feed_parser import FeedParser, setup_default_feeds
from .background_worker import initialize_worker_system, shutdown_worker_system
from . import background_worker
from dateutil.relativedelta import relativedelta
import contextlib

# Set up logging
logger = logging.getLogger(__name__)

# Create FastHTML app instance
app = FastHTML()

# Initialize database and setup default feeds if needed
init_db()

# Default feeds will be set up by background worker on first startup

# =============================================================================
# ARCHITECTURAL DECISIONS
# =============================================================================
# This app uses different HTMX targets for mobile and desktop BY DESIGN:
#
# MOBILE (Single-column, full-screen navigation):
#   - Target: #main-content (entire content area swaps)
#   - Navigation: List view ↔ Article view (full replacement)
#   - Tabs: Use HTMX to preserve header state
#   - Scroll: URL-based state preservation for custom containers
#
# DESKTOP (Three-column email interface):
#   - Targets: #desktop-feeds-content (middle), #desktop-item-detail (right)
#   - Navigation: Columns update independently
#   - Tabs: Regular links (full page navigation acceptable)
#   - Scroll: Standard browser scroll in each column
#
# This is NOT accidental complexity - it reflects fundamental UX differences:
# - Mobile users expect full-screen immersion and simple back navigation
# - Desktop users expect persistent context and multi-column efficiency
# =============================================================================

# =============================================================================
# CONFIGURATION - All decisions and constants visible here
# =============================================================================

class Targets:
    """HTMX update targets - what gets swapped"""
    MOBILE_CONTENT = '#main-content'
    DESKTOP_FEEDS = '#desktop-feeds-content'
    DESKTOP_DETAIL = '#desktop-item-detail'

class ElementIDs:
    """DOM element identifiers"""
    SIDEBAR = 'sidebar'

class Styling:
    """CSS classes for layouts and components"""
    FEED_ITEM_BASE = 'relative rounded-lg border border-border p-3 text-sm hover:bg-secondary space-y-2 cursor-pointer'
    FEED_ITEM_READ = 'bg-muted tag-read'
    FEED_ITEM_UNREAD = 'tag-unread'
    SIDEBAR_DESKTOP = 'col-span-1 h-screen overflow-y-auto border-r px-2'
    SIDEBAR_ITEM = 'hover:bg-secondary p-4 block'

# =============================================================================
# DATA PREPARATION LAYER - Centralized data fetching and preparation
# =============================================================================

class PageData:
    """Centralized data preparation - acknowledges mobile/desktop differences"""
    def __init__(self, session_id, feed_id=None, unread=True, page=1):
        self.session_id = session_id
        self.feed_id = feed_id
        self.unread = unread
        self.page = page
        
        # FETCH ALL DATA ONCE
        self.items = FeedItemModel.get_items_for_user(session_id, feed_id, unread, page)
        self.feeds = FeedModel.get_user_feeds(session_id)
        self.folders = FolderModel.get_folders(session_id)
        self.feed_name = self._get_feed_name()
        self.total_pages = self._calculate_total_pages()
    
    def _get_feed_name(self):
        """Get current feed name for display"""
        if self.feed_id:
            # Use optimized single-row query instead of searching in collection
            return FeedModel.get_feed_name_for_user(self.session_id, self.feed_id) or "Unknown Feed"
        return "All Feeds"
    
    def _calculate_total_pages(self):
        """Calculate pagination info"""
        # Use same logic as FeedsContent for consistency
        with get_db() as conn:
            count_query = """
                SELECT COUNT(*)
                FROM feed_items fi
                JOIN feeds f ON fi.feed_id = f.id
                JOIN user_feeds uf ON f.id = uf.feed_id AND uf.session_id = ?
                LEFT JOIN user_items ui ON fi.id = ui.item_id AND ui.session_id = ?
            """
            count_params = [self.session_id, self.session_id]
            
            if self.feed_id:
                count_query += " WHERE fi.feed_id = ?"
                count_params.append(self.feed_id)
            
            if self.unread:
                count_query += " AND " if self.feed_id else " WHERE "
                count_query += "COALESCE(ui.is_read, 0) = 0"
            
            total_items = conn.execute(count_query, count_params).fetchone()[0]
            page_size = 20  # Match FeedItemModel.get_items_for_user
            return (total_items + page_size - 1) // page_size if total_items else 1

# =============================================================================
# MOBILE/DESKTOP FRAGMENT HANDLERS - Explicit separation of layout concerns
# =============================================================================

# Removed: Old MobileHandlers class - using unified layout now

# Removed: Old DesktopHandlers class - using unified layout now

# Removed: Old HTMX routing functions - using unified layout now

def three_pane_layout(data):
    """Unified three-pane layout for all viewports"""
    feed_name = data.feed_name if hasattr(data, 'feed_name') else "All Feeds"

    # Mobile header bar (visible only on mobile)
    header_bar = Div(
        cls="lg:hidden fixed top-0 left-0 right-0 bg-background border-b p-4 z-40",
        id="mobile-header"
    )(
        Div(cls="flex items-center justify-between")(
            # Hamburger menu button
            Button(
                UkIcon('menu'),
                cls="p-3 rounded border hover:bg-secondary min-h-[44px] min-w-[44px]",
                onclick="document.getElementById('app-root').setAttribute('data-drawer','open')",
                data_testid="open-feeds"
            ),
            # Feed name/title
            H1(feed_name, cls="text-lg font-semibold"),
            # Back button (visible only when detail has content)
            Button(
                UkIcon('arrow-left'),
                hx_get="/",
                hx_target="#detail",
                hx_swap="innerHTML",
                cls="lg:hidden p-3 rounded border hover:bg-secondary min-h-[44px] min-w-[44px]",
                data_testid="back-button",
                style="display: none;",  # Hidden by default, shown via CSS when detail has content
                id="back-button"
            )
        )
    )

    # Overlay for mobile sidebar (click to close)
    overlay = Div(
        cls="fixed inset-0 bg-black/50 z-40 lg:hidden",
        onclick="document.getElementById('app-root').removeAttribute('data-drawer')",
        style="display: none;",  # Shown when data-drawer="open"
        id="sidebar-overlay"
    )

    return Div(
        id="app-root",
        data_testid="app-root",
        cls="grid min-h-dvh lg:grid-cols-[18rem_1fr_1.25fr] lg:grid-rows-1 grid-rows-[auto_1fr]"
    )(
        header_bar,
        overlay,
        # Feeds sidebar (left)
        Aside(
            id="feeds",
            data_testid="feeds",
            cls="hidden lg:block lg:overflow-y-auto border-r"
        )(
            FeedsSidebar(data.session_id)
        ),
        # Summary list (middle)
        Section(
            id="summary",
            data_testid="summary",
            cls="overflow-y-auto"
        )(
            FeedsContent(data.session_id, data.feed_id, data.unread, data.page, data=data)
        ),
        # Detail view (right)
        Article(
            id="detail",
            data_testid="detail",
            cls="hidden lg:block overflow-y-auto"
        )(
            Div(cls="placeholder")  # Empty placeholder initially
        )
    )

# Removed: mobile_chrome function - using unified layout now

# Removed: old mobile_layout and desktop_layout functions - using unified layout now

def viewport_styles():
    """Global styles for viewport management with unified layout"""
    return Style("""
    @layer utilities {
        /* Dynamic viewport units instead of forced body fixed */
        .min-h-dvh {
            min-height: 100dvh;
        }

        /* Mobile-specific rules (max-width: 1023px) */
        @media (max-width: 1023px) {
            /* Mobile default: show Summary, hide Detail */
            #detail {
                display: none !important;
            }

            /* When detail has content (not just placeholder), hide Summary and show Detail */
            #app-root:has(#detail > :not(.placeholder)) #summary {
                display: none !important;
            }
            #app-root:has(#detail > :not(.placeholder)) #detail {
                display: block !important;
            }

            /* Show back button when detail has content */
            #app-root:has(#detail > :not(.placeholder)) #back-button {
                display: block !important;
            }

            /* Off-canvas sidebar (closed by default) */
            #feeds {
                position: fixed !important;
                top: 0;
                left: 0;
                bottom: 0;
                width: 18rem;
                transform: translateX(-100%);
                transition: transform 0.3s ease;
                background: var(--background);
                z-index: 50;
                display: block !important; /* Override the lg:hidden class */
            }

            /* Open sidebar when data-drawer="open" */
            #app-root[data-drawer="open"] #feeds {
                transform: translateX(0);
            }

            /* Show overlay when drawer is open */
            #app-root[data-drawer="open"] #sidebar-overlay {
                display: block !important;
            }

            /* Mobile layout adjustments */
            #app-root {
                grid-template-rows: auto 1fr !important;
                grid-template-columns: 1fr !important;
            }

            /* Mobile header spacing */
            #summary, #detail {
                padding-top: 5rem; /* Space for fixed header */
            }
        }

        /* Desktop-specific rules (min-width: 1024px) */
        @media (min-width: 1024px) {
            /* Desktop: all three panes visible */
            #feeds {
                position: static !important;
                transform: none !important;
                display: block !important;
            }

            #summary {
                display: block !important;
            }

            #detail {
                display: block !important;
            }

            /* Hide mobile-only elements */
            #mobile-header, #sidebar-overlay, #back-button {
                display: none !important;
            }
        }
    }

    /* Text wrapping and overflow prevention */
    .prose, .prose * {
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
        word-break: break-word !important;
        max-width: 100% !important;
        box-sizing: border-box !important;
    }

    /* Prevent horizontal scrolling on mobile */
    @media (max-width: 1024px) {
        * {
            max-width: 100vw !important;
            overflow-x: hidden !important;
        }
    }
    """)

def create_tab_container(feed_name, feed_id, unread_only):
    """Create All Posts/Unread tabs with layout-appropriate attributes

    Mobile needs HTMX attributes to preserve persistent header during navigation.
    Desktop can use regular links since the three-column layout persists.
    """
    # Build base URL for navigation
    url_params = []
    if feed_id:
        url_params.append(f"feed_id={feed_id}")
    base_url = "/?" + "&".join(url_params) if url_params else "/"
    
    # Common tab structure with conditional HTMX attributes
    return TabContainer(
        Li(A("All Posts", 
             href=f"{base_url}{'&' if url_params else '?'}unread=0" if base_url != "/" else "/?unread=0",
             role='button'),
           cls='uk-active' if not unread_only else ''),
        Li(A("Unread",
             href=base_url if base_url != "/" else "/",
             role='button'),
           cls='uk-active' if unread_only else ''),
        alt=True, cls='ml-auto max-w-40'
    )

# Removed: prepare_item_data function - using simplified item fetching in routes

# Removed: old htmx_item_response and full_page_item_response functions

# Removed: old item response and layout functions - using unified layout now

# Timing middleware for performance monitoring
def timing_middleware(req, sess):
    """Add timing info to requests"""
    req.scope['start_time'] = time.time()

def after_middleware(req, response):
    """Log request timing with timestamps"""
    if 'start_time' in req.scope:
        duration = (time.time() - req.scope['start_time']) * 1000  # Convert to ms
        path = req.scope.get('path', 'unknown')
        method = req.scope.get('method', 'unknown')
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        print(f"[{timestamp}] TIMING: {method} {path} - {duration:.2f}ms")
    return response

# Beforeware for session management
def before(req, sess):
    """Initialize session and ensure user is subscribed to feeds"""
    session_id = sess.get('session_id')
    
    if not session_id:
        session_id = str(uuid.uuid4())
        sess['session_id'] = session_id
        SessionModel.create_session(session_id)
        print(f"DEBUG: Created new session: {session_id}")
        should_subscribe = True
    else:
        print(f"DEBUG: Using existing session: {session_id}")
        # Check if session has any subscriptions
        user_feeds = FeedModel.get_user_feeds(session_id)
        should_subscribe = len(user_feeds) == 0
    
    # Subscribe to ALL existing feeds if needed
    if should_subscribe:
        with get_db() as conn:
            all_feeds = [dict(row) for row in conn.execute("SELECT * FROM feeds").fetchall()]
            print(f"DEBUG: Found {len(all_feeds)} feeds to subscribe to")
            for feed in all_feeds:
                try:
                    SessionModel.subscribe_to_feed(session_id, feed['id'])
                    print(f"DEBUG: Subscribed to feed {feed['id']}: {feed['title']}")
                except Exception as e:
                    print(f"DEBUG: Subscription error for feed {feed['id']}: {str(e)}")
                    # Re-raise critical errors, only catch known duplicates
                    if "UNIQUE constraint failed" not in str(e):
                        raise
    
    # INVARIANT: Every session MUST see items (no exceptions)
    user_items = FeedItemModel.get_items_for_user(session_id, feed_id=None, unread_only=False, page=1)
    
    if len(user_items) == 0:
        import traceback
        import json
        
        # Gather ALL diagnostic SQL
        with get_db() as conn:
            diagnostics = {}
            
            # 1. Basic counts
            diagnostics['feeds_count'] = conn.execute("SELECT COUNT(*) FROM feeds").fetchone()[0]
            diagnostics['items_count'] = conn.execute("SELECT COUNT(*) FROM feed_items").fetchone()[0]
            diagnostics['user_feeds_count'] = conn.execute(
                "SELECT COUNT(*) FROM user_feeds WHERE session_id = ?", (session_id,)
            ).fetchone()[0]
            
            # 2. Sample feeds
            diagnostics['sample_feeds'] = [dict(row) for row in conn.execute(
                "SELECT id, url, title FROM feeds LIMIT 5"
            ).fetchall()]
            
            # 3. Sample items
            diagnostics['sample_items'] = [dict(row) for row in conn.execute(
                "SELECT id, feed_id, title FROM feed_items LIMIT 5"
            ).fetchall()]
            
            # 4. User's subscriptions
            diagnostics['user_subscriptions'] = [dict(row) for row in conn.execute(
                "SELECT * FROM user_feeds WHERE session_id = ? LIMIT 5", (session_id,)
            ).fetchall()]
            
            # 5. The EXACT query that's failing
            failing_sql = """
                SELECT fi.*, f.title as feed_title, 
                       COALESCE(ui.is_read, 0) as is_read,
                       COALESCE(ui.starred, 0) as starred,
                       fo.name as folder_name
                FROM feed_items fi
                JOIN feeds f ON fi.feed_id = f.id
                JOIN user_feeds uf ON f.id = uf.feed_id AND uf.session_id = ?
                LEFT JOIN user_items ui ON fi.id = ui.item_id AND ui.session_id = ?
                LEFT JOIN folders fo ON ui.folder_id = fo.id
                ORDER BY fi.published DESC LIMIT 20
            """
            
            diagnostics['failing_query_result'] = [dict(row) for row in conn.execute(
                failing_sql, (session_id, session_id)
            ).fetchall()]
            
            # 6. Check each JOIN step
            diagnostics['step1_feed_items'] = conn.execute(
                "SELECT COUNT(*) FROM feed_items"
            ).fetchone()[0]
            
            diagnostics['step2_with_feeds'] = conn.execute(
                "SELECT COUNT(*) FROM feed_items fi JOIN feeds f ON fi.feed_id = f.id"
            ).fetchone()[0]
            
            diagnostics['step3_with_user_feeds'] = conn.execute(
                "SELECT COUNT(*) FROM feed_items fi "
                "JOIN feeds f ON fi.feed_id = f.id "
                "JOIN user_feeds uf ON f.id = uf.feed_id AND uf.session_id = ?",
                (session_id,)
            ).fetchone()[0]
        
        # Create HTML error page
        error_html = Html(
            Head(
                Title("500 - Invariant Violation"),
                Style("""
                    body { font-family: monospace; padding: 20px; background: #1a1a1a; color: #ff6b6b; }
                    h1 { color: #ff0000; border-bottom: 3px solid #ff0000; padding-bottom: 10px; }
                    h2 { color: #ff9999; margin-top: 30px; }
                    pre { background: #2a2a2a; padding: 15px; border-left: 4px solid #ff6b6b; 
                          overflow-x: auto; color: #e0e0e0; }
                    details { margin: 20px 0; }
                    summary { cursor: pointer; color: #ff9999; font-weight: bold; padding: 10px;
                             background: #2a2a2a; }
                    .error-box { background: #330000; border: 2px solid #ff0000; padding: 20px;
                                margin: 20px 0; }
                    .metric { display: inline-block; margin: 10px 20px 10px 0; }
                    .metric-label { color: #888; }
                    .metric-value { color: #fff; font-size: 1.2em; font-weight: bold; }
                """)
            ),
            Body(
                H1("🚨 INVARIANT VIOLATION: User MUST See Items"),
                
                Div(
                    H2("Critical Failure"),
                    Div(
                        f"Session {session_id} sees 0 items but this should be impossible!",
                        cls="error-box"
                    ),
                    
                    H2("Database State"),
                    Div(
                        Div(Span("Total Feeds: ", cls="metric-label"), 
                            Span(str(diagnostics['feeds_count']), cls="metric-value"), cls="metric"),
                        Div(Span("Total Items: ", cls="metric-label"), 
                            Span(str(diagnostics['items_count']), cls="metric-value"), cls="metric"),
                        Div(Span("User Subscriptions: ", cls="metric-label"), 
                            Span(str(diagnostics['user_feeds_count']), cls="metric-value"), cls="metric"),
                    ),
                    
                    Details(
                        Summary("Sample Feeds"),
                        Pre(json.dumps(diagnostics['sample_feeds'], indent=2))
                    ),
                    
                    Details(
                        Summary("Sample Items"),
                        Pre(json.dumps(diagnostics['sample_items'], indent=2))
                    ),
                    
                    Details(
                        Summary("User Subscriptions"),
                        Pre(json.dumps(diagnostics['user_subscriptions'], indent=2))
                    ),
                    
                    H2("SQL Join Breakdown"),
                    Pre(f"""Step 1 - feed_items table: {diagnostics['step1_feed_items']} rows
Step 2 - JOIN with feeds: {diagnostics['step2_with_feeds']} rows
Step 3 - JOIN with user_feeds (session={session_id}): {diagnostics['step3_with_user_feeds']} rows"""),
                    
                    Details(
                        Summary("Failing SQL Query"),
                        Pre(failing_sql),
                        Pre(f"Parameters: ('{session_id}', '{session_id}')"),
                        Pre(f"Result: {json.dumps(diagnostics['failing_query_result'], indent=2)}")
                    ),
                    
                    Details(
                        Summary("Stack Trace"),
                        Pre(''.join(traceback.format_stack()))
                    )
                )
            )
        )
        
        # Log to console as well
        logger.error(f"INVARIANT VIOLATION: Session {session_id} sees 0 items!")
        
        # Return proper HTML response with 500 status code
        # NOTE: We're in middleware, not a route handler, so we must return a raw HTTP response.
        # Route handlers can return FastHTML objects directly (FastHTML auto-converts them),
        # but middleware runs before FastHTML's response pipeline, so we need HTMLResponse.
        # Use to_xml() to convert FastHTML object to actual HTML string.
        return HTMLResponse(to_xml(error_html), status_code=500)
    
    # Store in request scope for easy access
    req.scope['session_id'] = session_id

# Lifespan event handler for background worker
@contextlib.asynccontextmanager
async def lifespan(app):
    """Handle app startup and shutdown with background worker"""
    if MINIMAL_MODE:
        print("FastHTML app starting in MINIMAL MODE...")
        print("⚡ Using pre-populated seed database (no network calls, no background worker)")
    else:
        print("FastHTML app starting up...")
        
        # Add default feeds BEFORE worker initialization so they get queued
        print("Adding default feeds to database...")
        setup_default_feeds(minimal_mode=False)
        
        # Initialize background worker after feeds exist
        initialize_worker_system()
        print("Background worker system initialized")
    
    yield  # App is running
    
    # Shutdown: Clean up background worker only if not in minimal mode
    if not MINIMAL_MODE:
        print("Shutting down background worker...")
        shutdown_worker_system()
    print("FastHTML app shutdown complete")

# FastHTML app with session support and lifespan
app, rt = fast_app(
    title="RSS Reader",
    hdrs=Theme.blue.headers() + [
        Script("""
        htmx.logAll();
        htmx.config.includeIndicatorStyles = false;
        
        // Scroll restoration for unified layout
        htmx.on('htmx:afterSwap', function(evt) {
            // Handle pagination - reset scroll to top for summary updates
            if (evt.detail.target && evt.detail.target.id === 'summary') {
                setTimeout(() => {
                    const summary = document.getElementById('summary');
                    if (summary) {
                        summary.scrollTop = 0;
                    }
                }, 50);
            }

            // Handle detail updates (article view)
            if (evt.detail.target && evt.detail.target.id === 'detail') {
                // Reset detail scroll to top when new article loads
                setTimeout(() => {
                    const detail = document.getElementById('detail');
                    if (detail) {
                        detail.scrollTop = 0;
                    }
                }, 50);
            }
        });
        
        // Mobile sidebar auto-close now handled via hx-on:click on individual feed links
        
        // Form targeting now handled via hx-on:htmx:config-request on individual forms
        
        // Body class management now handled in scroll restoration handler above
        
        """),
        Style("""
        .htmx-indicator { display: none; }
        .htmx-request .htmx-indicator { display: flex; }
        
        /* Hide mobile persistent header when body has article-view class */
        body.article-view #mobile-persistent-header {
            display: none !important;
        }
        
        /* Fix mobile navigation button state transitions */
        #mobile-nav-button {
            transition: all 0.2s ease-in-out !important;
            background-color: transparent !important;
            color: inherit !important;
        }
        
        #mobile-nav-button:hover {
            background-color: hsl(var(--secondary)) !important;
            color: inherit !important;
        }
        
        /* Ensure clean state reset on button swap */
        #mobile-nav-button:not(:hover):not(:active):not(:focus) {
            background-color: transparent !important;
            color: inherit !important;
        }
        
        """)
    ],
    live=True,
    debug=True,
    before=[timing_middleware, before],
    after=after_middleware,
    lifespan=lifespan
)

def process_urls_in_content(content):
    """Replace plain URLs with compact emoji links and copy functionality"""
    if not content:
        return content
    
    # URL regex pattern - matches http/https URLs
    url_pattern = r'(?<!href=["\'])(?<!src=["\'])(https?://[^\s<>"\']+)'
    
    def replace_url(match):
        url = match.group(1)
        # Create compact inline components with emojis
        link_component = Span(
            A(
                "🔗",
                href=url,
                target='_blank',
                rel='noopener noreferrer',
                cls='text-blue-600 hover:text-blue-800 no-underline',
                title='Open link'
            ),
            Button(
                "📋",
                onclick=f"navigator.clipboard.writeText('{url}'); this.innerHTML='✅'; setTimeout(() => this.innerHTML='📋', 1000)",
                cls='ml-1 text-blue-600 hover:text-blue-800 bg-transparent border-0 p-0 cursor-pointer',
                title='Copy URL',
                style='line-height: inherit; height: auto; font-size: inherit;'
            ),
            cls='inline-flex items-center gap-1',
            style='line-height: inherit; height: auto;'
        )
        return str(link_component)
    
    # Replace URLs that aren't already in HTML tags
    processed_content = re.sub(url_pattern, replace_url, content)
    return processed_content

def smart_truncate_html(text, max_length=150):
    """Smart truncation that counts only visible text, preserves images regardless of URL length
    
    Strategy:
    1. Convert markdown to HTML first (ALWAYS)
    2. Parse with BeautifulSoup
    3. Count only VISIBLE text characters (exclude image URLs, HTML attributes)
    4. Preserve ALL images regardless of URL length
    5. Truncate text content when visible text limit reached
    """
    if not text:
        return 'No content available'
    
    # ALWAYS convert markdown to HTML first
    html_content = mistletoe.markdown(text)
    
    # Parse with BeautifulSoup for proper element handling
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extract all images first - these are always preserved
    images = soup.find_all('img')
    
    # Get visible text length (excluding images)
    visible_text = soup.get_text()
    
    # If visible text is within limit, return full content
    if len(visible_text) <= max_length:
        return html_content
    
    # Need to truncate: build result with images + truncated text
    result_elements = []
    visible_char_count = 0
    
    # Process each top-level element
    for element in soup.children:
        if hasattr(element, 'name'):  # It's a tag
            if element.name == 'img':
                # Always include images, don't count toward text limit
                result_elements.append(str(element))
            elif element.find('img'):
                # Element contains image - preserve the whole element
                result_elements.append(str(element))
            else:
                # Text-based element - check if we can fit it
                element_text = element.get_text()
                element_text_length = len(element_text)
                
                if visible_char_count + element_text_length <= max_length:
                    # Fits completely
                    result_elements.append(str(element))
                    visible_char_count += element_text_length
                else:
                    # Need to truncate this element
                    remaining_chars = max_length - visible_char_count
                    if remaining_chars > 20:  # Only add if meaningful text remains
                        truncated_text = element_text[:remaining_chars].rsplit(' ', 1)[0] + '...'
                        
                        # Create new element with truncated text
                        new_element = soup.new_tag(element.name)
                        new_element.string = truncated_text
                        
                        # Copy attributes
                        for attr_name, attr_value in element.attrs.items():
                            new_element[attr_name] = attr_value
                            
                        result_elements.append(str(new_element))
                    break
        else:
            # Direct text node
            text_content = str(element).strip()
            if text_content:
                text_length = len(text_content)
                if visible_char_count + text_length <= max_length:
                    result_elements.append(text_content)
                    visible_char_count += text_length
                else:
                    # Truncate text node
                    remaining_chars = max_length - visible_char_count
                    if remaining_chars > 10:
                        truncated = text_content[:remaining_chars].rsplit(' ', 1)[0] + '...'
                        result_elements.append(truncated)
                    break
    
    return ''.join(result_elements)

def human_time_diff(dt):
    """Convert datetime to human readable relative time"""
    if not dt:
        return "Unknown"
    
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except:
            return "Unknown"
    
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    diff = now - dt
    
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "Just now"

def FeedSidebarItem(feed, count=""):
    """Create sidebar item for feed"""
    last_updated = human_time_diff(feed.get('last_updated'))

    # Handle Unknown timestamp gracefully
    update_text = last_updated if last_updated != "Unknown" else "never updated"

    return Li(
        A(
            DivLAligned(
                UkIcon('rss', cls="flex-none"),
                Span(feed['title'] or 'Untitled Feed'),
                P(f"updated {update_text}", cls="text-xs text-muted"),
                cls="gap-3"
            ),
            href=f"/?feed_id={feed['id']}",
            hx_get=f"/?feed_id={feed['id']}",
            hx_target="#summary",
            hx_push_url="true",
            cls=Styling.SIDEBAR_ITEM,
            onclick="if (window.innerWidth < 1024) { document.getElementById('app-root').removeAttribute('data-drawer'); }"
        )
    )

def FeedsSidebar(session_id):
    """Create feeds sidebar for unified layout"""
    feeds = FeedModel.get_user_feeds(session_id)
    folders = FolderModel.get_folders(session_id)

    return Ul(
        Li(
            DivFullySpaced(
                H3("Feeds"),
                Button(
                    UkIcon('refresh-cw'),
                    hx_post="/api/session/reset",
                    hx_swap="none",
                    cls="p-1 hover:bg-secondary rounded",
                    title="Reset all session data",
                    hx_confirm="Are you sure? This will clear all your subscriptions and settings."
                )
            ),
            cls='p-3'
        ),
        Li(
            Form(
                DivLAligned(
                    Input(
                        placeholder="Enter RSS URL",
                        name="new_feed_url",  # This maps to FastHTML function parameter
                        cls="flex-1 mr-2 add-feed-input"
                    ),
                    Button(
                        UkIcon('plus'),
                        cls="px-2 add-feed-button",
                        type="submit"
                    )
                ),
                hx_post="/api/feed/add",
                hx_target="#feeds",  # Unified target
                hx_swap="innerHTML",
                cls="add-feed-form"
            ),
            cls='p-4'
        ),
        Li(
            A(
                DivLAligned(
                    UkIcon('globe', cls="flex-none"),
                    Span("All Feeds"),
                    P("", cls="text-xs text-muted"),
                    cls="gap-3"
                ),
                href="/",
                hx_get="/",
                hx_target="#summary",
                hx_push_url="true",
                cls="hover:bg-secondary p-4 block",
                onclick="if (window.innerWidth < 1024) { document.getElementById('app-root').removeAttribute('data-drawer'); }"
            )
        ),
        Div(cls="feeds-list")(*[FeedSidebarItem(feed) for feed in feeds]),
        Li(Hr()),
        Li(H4("Folders"), cls='p-3'),
        *[Li(
            A(
                DivLAligned(
                    UkIcon('folder', cls="flex-none"),
                    Span(folder['name']),
                    cls="gap-3"
                ),
                href=f"/?folder_id={folder['id']}",
                cls="hover:bg-secondary p-4 block"
            )
        ) for folder in folders],
        Li(
            Button(
                UkIcon('plus'),
                " Add Folder",
                hx_post="/api/folder/add",
                hx_prompt="Folder name:",
                cls="w-full text-left p-4 hover:bg-secondary add-folder-button"
            )
        ),
        cls='mt-3'
    )

def FeedItem(item, unread_view=False, feed_id=None, page=1):
    """Feed item component with unified targeting"""
    cls_base = Styling.FEED_ITEM_BASE
    is_read = item.get('is_read', 0) == 1

    read_bg = Styling.FEED_ITEM_READ if is_read else Styling.FEED_ITEM_UNREAD
    cls = f"{cls_base} {read_bg}"

    # Build item URL with feed context preserved
    item_url = f"/item/{item['id']}?unread_view={unread_view}"
    if feed_id:
        item_url += f"&feed_id={feed_id}"
    if page > 1:
        item_url += f"&page={page}"

    # Unified targeting - always target #detail
    attrs = {
        "cls": cls,
        "id": f"feed-item-{item['id']}",
        "data_testid": "feed-item",
        "data_unread": "true" if not is_read else "false",
        "hx_get": item_url,
        "hx_target": "#detail",
        "hx_trigger": "click",
        "hx_push_url": "true"
    }
    
    return Li(
        # Title row with blue dot
        DivFullySpaced(
            Strong(item['title']) if not is_read else Span(item['title']),  # Bold for unread, normal for read
            Span(cls='flex h-2 w-2 rounded-full bg-blue-600') if not item.get('is_read', 0) else ''
        ),
        # Source and time row - source left, time right
        DivFullySpaced(
            Small(item.get('feed_title', 'Unknown Feed'), cls=TextPresets.muted_sm),
            Time(human_time_diff(item.get('published')), cls='text-xs text-muted-foreground')
        ),
        # Summary with smart HTML truncation that preserves images
        Div(
            NotStr(
                smart_truncate_html(item.get('description', ''), max_length=300) 
                if item.get('description') 
                else 'No summary available'
            ), 
            cls='text-sm text-muted-foreground mt-2 prose prose-sm max-w-none'
        ),
        # Optional folder label
        DivLAligned(
            *([Label(A(item.get('folder_name', 'General'), href='#'), 
                    cls='uk-label-primary')] if item.get('folder_name') else [])
        ),
        **attrs
    )

def FeedsList(items, unread_view=False, feed_id=None, page=1):
    """Create list of feed items"""
    return Ul(cls='js-filter space-y-2 p-4 pt-0')(*[FeedItem(item, unread_view, feed_id, page) for item in items])

# Removed: MobilePersistentHeader function - not used in unified layout

def FeedsContent(session_id, feed_id=None, unread_only=False, page=1, data=None):
    """Create main feeds content area with pagination

    Args:
        data: Optional PageData object with pre-fetched data. If provided, avoids duplicate DB queries.
    """
    if data:
        # Use pre-fetched data from PageData (Step 3: avoid duplicate queries)
        paginated_items = data.items
        total_pages = data.total_pages
        # Calculate total_items for pagination display 
        with get_db() as conn:
            count_query = """
                SELECT COUNT(*)
                FROM feed_items fi
                JOIN feeds f ON fi.feed_id = f.id
                JOIN user_feeds uf ON f.id = uf.feed_id AND uf.session_id = ?
                LEFT JOIN user_items ui ON fi.id = ui.item_id AND ui.session_id = ?
            """
            count_params = [session_id, session_id]
            
            if feed_id:
                count_query += " WHERE fi.feed_id = ?"
                count_params.append(feed_id)
            
            if unread_only:
                count_query += " AND " if feed_id else " WHERE "
                count_query += "COALESCE(ui.is_read, 0) = 0"
            
            total_items = conn.execute(count_query, count_params).fetchone()[0]
        print(f"DEBUG: FeedsContent using pre-fetched data: {len(paginated_items)} items, {total_pages} pages")
    else:
        # Fallback: fetch data directly (for routes not yet updated to use PageData)
        page_size = 20
        paginated_items = FeedItemModel.get_items_for_user(session_id, feed_id, unread_only, page, page_size)
        print(f"DEBUG: FeedsContent got {len(paginated_items)} items for session {session_id} (page {page})")
        
        # Calculate total pages by getting total count
        with get_db() as conn:
            count_query = """
                SELECT COUNT(*)
                FROM feed_items fi
                JOIN feeds f ON fi.feed_id = f.id
                JOIN user_feeds uf ON f.id = uf.feed_id AND uf.session_id = ?
                LEFT JOIN user_items ui ON fi.id = ui.item_id AND ui.session_id = ?
            """
            count_params = [session_id, session_id]
            
            if feed_id:
                count_query += " WHERE fi.feed_id = ?"
                count_params.append(feed_id)
            
            if unread_only:
                count_query += " AND " if feed_id else " WHERE "
                count_query += "COALESCE(ui.is_read, 0) = 0"
            
            total_items = conn.execute(count_query, count_params).fetchone()[0]
            total_pages = (total_items + page_size - 1) // page_size if total_items else 1
    
    print(f"🔍 FeedsContent() - using unified layout")
    
    # Simple header logic for desktop only
    if feed_id:
        feed_name = FeedModel.get_feed_name_for_user(session_id, feed_id) or "Unknown Feed"
    else:
        feed_name = "All Feeds"
    
    # Build URL parameters for pagination (excluding unread for tab navigation)
    url_params = []
    if feed_id:
        url_params.append(f"feed_id={feed_id}")
    
    # Base URL for tab navigation (without unread parameter)
    base_url = "/?" + "&".join(url_params) if url_params else "/"
    
    def pagination_footer():
        """Create pagination footer using MonsterUI pattern"""
        if total_pages <= 1:
            return ""  # No pagination needed
        
        # Navigation URLs
        first_url = f"{base_url}{'&' if url_params else '?'}page=1" if base_url != "/" else "/?page=1"
        prev_url = f"{base_url}{'&' if url_params else '?'}page={max(1, page-1)}" if base_url != "/" else f"/?page={max(1, page-1)}"
        next_url = f"{base_url}{'&' if url_params else '?'}page={min(total_pages, page+1)}" if base_url != "/" else f"/?page={min(total_pages, page+1)}"
        last_url = f"{base_url}{'&' if url_params else '?'}page={total_pages}" if base_url != "/" else f"/?page={total_pages}"
        
        def _create_pagination_button(icon, url, target):
            """Helper to create a single pagination button"""
            return Button(
                UkIcon(icon),
                hx_get=url,
                hx_target=target,
                hx_push_url="true",
                cls="p-2 rounded border hover:bg-secondary"
            )

        # Unified target - always #summary
        target = "#summary"

        return Div(cls='p-4 border-t')(
            DivFullySpaced(
                DivCentered(f'Page {page} of {total_pages}', cls=TextT.sm),
                DivLAligned(
                    # Unified responsive pagination buttons
                    _create_pagination_button('chevrons-left', first_url, target),
                    _create_pagination_button('chevron-left', prev_url, target),
                    _create_pagination_button('chevron-right', next_url, target),
                    _create_pagination_button('chevrons-right', last_url, target),
                    cls='space-x-1'
                )
            )
        )
    
    # Unified layout for both mobile and desktop - same simple content structure
    # Feed name now shown in chrome, not in content area
    content_elements = [
        FeedsList(paginated_items, unread_only, feed_id, page) if paginated_items else Div(P("No posts available"), cls='p-4 text-center text-muted-foreground'),
        pagination_footer()
    ]
    
    return Div(cls='p-0', id="feeds-list-container", uk_filter="target: .js-filter")(
        *content_elements
    )

# Removed: MobileSidebar function - using unified off-canvas drawer now

# Removed: UnifiedChrome and MobileHeader functions - not used in unified layout


def ItemDetailView(item):
    """Create item detail view - back button now handled by header"""
    if not item:
        return Container(
            P("Select a post to read", cls='text-center text-muted-foreground p-8'),
            id="item-detail"
        )
    
    # Action icons - only show star, folder, and mark unread
    action_icons = [
        ('star' if not item.get('starred', 0) else 'star-fill', 'Star' if not item.get('starred', 0) else 'Unstar'),
        ('folder', 'Move to folder'),
        ('mail', 'Mark unread' if item.get('is_read', 0) else 'Mark read')
    ]
    
    # Back button now handled by mobile header, not in detail view
    
    return Container(
        DivFullySpaced(
            DivLAligned(
                *[UkIcon(
                    icon, 
                    uk_tooltip=tooltip,
                    hx_post=f"/api/item/{item['id']}/{'star' if 'star' in tooltip.lower() else 'folder' if 'folder' in tooltip.lower() else 'read'}",
                    hx_target=Targets.MOBILE_CONTENT,
                    cls='cursor-pointer hover:text-blue-600'
                ) for icon, tooltip in action_icons],
                cls='space-x-2'
            ),
            DivLAligned(
                A("Open Link", href=item['link'], target="_blank", 
                  cls='text-blue-600 hover:underline')
            ),
            cls='mx-4 mb-4'
        ),
        DivLAligned(
            Span(item.get('feed_title', 'Unknown')[:2], 
                 cls='flex h-10 w-10 items-center justify-center rounded-full bg-muted'),
            Div(
                Strong(item['title']),
                DivLAligned(
                    P('From:'),
                    A(item.get('feed_title', 'Unknown Feed'), href='#'),
                    cls='space-x-1'
                ),
                P(Time(human_time_diff(item.get('published')))),
                cls='space-y-1' + TextT.sm
            ),
            cls='m-4 space-x-4'
        ),
        DividerLine(),
        Div(
            NotStr(process_urls_in_content(mistletoe.markdown(item.get('content') or item.get('description') or 'No content available'))),
            cls=TextT.sm + 'p-4 prose max-w-none break-words overflow-wrap-anywhere'
        ),
        id="item-detail"
    )

@rt('/')
def index(htmx, sess, feed_id: int = None, unread: bool = True, folder_id: int = None, page: int = 1, _scroll: int = None):
    """Main page with unified responsive design"""
    session_id = sess.get('session_id')

    # Use centralized data preparation
    data = PageData(session_id, feed_id, unread, page)

    # Queue user's feeds for background updating (skip in minimal mode)
    if not MINIMAL_MODE and background_worker.queue_manager:
        try:
            background_worker.queue_manager.queue_user_feeds(session_id)
            print(f"DEBUG: Queued user feeds for background update")
        except Exception as e:
            print(f"WARNING: Could not queue user feeds: {str(e)}")

    # HTMX fragment updates
    if htmx and getattr(htmx, 'request', None):
        # Return updated summary list for pagination/filtering
        if getattr(htmx, 'target', None) == 'summary':
            return FeedsContent(data.session_id, data.feed_id, data.unread, data.page, data=data)
        # Clear detail to show summary (for back button)
        elif getattr(htmx, 'target', None) == 'detail':
            return Div(cls="placeholder")

    # Full page with unified layout
    return (three_pane_layout(data), viewport_styles())

@rt('/item/{item_id}')
def show_item(item_id: int, htmx, sess, unread_view: bool = False, feed_id: int = None, page: int = 1, _scroll: int = None):
    """Item detail route - returns detail fragment with list item update"""
    session_id = sess.get('session_id')

    # Get the item before marking as read
    item = FeedItemModel.get_item_for_user(session_id, item_id)

    if not item:
        return Div(
            P("Item not found", cls='text-center text-muted-foreground p-8'),
            cls='m-4'
        )

    # Check if item was unread before marking as read
    was_unread = not item.get('is_read', 0)

    # Mark as read
    if item:
        UserItemModel.mark_read_and_get_item(session_id, item_id, True)
        # Refresh item data to get updated read status
        item = FeedItemModel.get_item_for_user(session_id, item_id)

    # If item was unread, return both detail view and updated list item
    if was_unread:
        # Create updated list item with no blue dot
        updated_item = Li(
            # Title row with no blue dot (read state)
            DivFullySpaced(
                Span(item['title']),  # No bold for read items
                # No blue dot for read items
            ),
            # Source and time row
            DivFullySpaced(
                Small(item.get('feed_title', 'Unknown Feed'), cls='text-sm text-gray-500'),
                Time(human_time_diff(item.get('published')), cls='text-xs text-muted-foreground')
            ),
            # Summary
            Div(
                NotStr(
                    smart_truncate_html(item.get('description', ''), max_length=300)
                    if item.get('description')
                    else 'No summary available'
                ),
                cls='text-sm text-muted-foreground mt-2 prose prose-sm max-w-none'
            ),
            cls=f"{Styling.FEED_ITEM_BASE} {Styling.FEED_ITEM_READ}",
            id=f"feed-item-{item['id']}",
            data_testid="feed-item",
            data_unread="false",
            hx_get=f"/item/{item['id']}?unread_view={unread_view}" + (f"&feed_id={feed_id}" if feed_id else ""),
            hx_target="#detail",
            hx_trigger="click",
            hx_push_url="true",
            hx_swap_oob="true"
        )

        return (ItemDetailView(item), updated_item)
    else:
        # Item was already read, just return detail view
        return ItemDetailView(item)

@rt('/api/feed/add')
def add_feed(htmx, sess, new_feed_url: str = ""):
    """Add new feed"""
    session_id = sess.get('session_id')
    if not session_id:
        print(f"ERROR: add_feed called without session_id")
        return Div("Session error", cls='text-red-500 p-4')
    
    url = new_feed_url.strip()
    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"[{timestamp}] DEBUG: add_feed called with URL='{url}', session_id='{session_id}' [FIXED_VERSION]")
    
    # Determine if request is from mobile or desktop based on target
    hx_target = getattr(htmx, 'target', '') if htmx else ''
    print(f"[{timestamp}] DEBUG: HX-Target header: '{hx_target}'")
    
    if not url:
        return Div("Please enter a URL", cls='text-red-500 p-4')
    
    # Check if user is already subscribed to this feed
    existing_feed = FeedModel.user_has_feed_url(session_id, url)
    
    if existing_feed:
        return Div(f"Already subscribed to: {existing_feed['title']}", 
                  cls='text-yellow-600 p-4')
    
    try:
        # FAST: Create feed record only (follow setup_default_feeds pattern)
        if not FeedModel.feed_exists_by_url(url):
            feed_id = FeedModel.create_feed(url, "Loading...")
            print(f"DEBUG: Created feed record {feed_id} for {url}")
        else:
            # Feed exists, get the ID
            with get_db() as conn:
                feed_id = conn.execute("SELECT id FROM feeds WHERE url = ?", (url,)).fetchone()[0]
            print(f"DEBUG: Feed already exists with ID {feed_id}")
        
        # Subscribe user to the feed
        try:
            SessionModel.subscribe_to_feed(session_id, feed_id)
            print(f"SUCCESS: User subscribed to feed {feed_id}")
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                print(f"DEBUG: User already subscribed to feed {feed_id}")
            else:
                raise
        
        # Queue for immediate background processing (skip in minimal mode)
        if not MINIMAL_MODE and background_worker.queue_manager:
            feed_data = {
                'id': feed_id,
                'url': url,
                'title': 'Loading...',
                'last_updated': None,
                'etag': None,
                'last_modified': None
            }
            # Use put_nowait for sync context (non-blocking)
            try:
                background_worker.queue_manager.worker.queue.put_nowait(feed_data)
                print(f"SUCCESS: Feed {feed_id} queued immediately for background processing")
            except Exception as e:
                print(f"WARNING: Could not queue feed immediately: {str(e)}")
                print(f"Feed {feed_id} will be picked up by background worker automatically")
        elif MINIMAL_MODE:
            print(f"MINIMAL_MODE: Feed {feed_id} created without background processing")
        else:
            print(f"WARNING: Background worker not available, feed {feed_id} created without immediate queuing")
        
        # Return unified sidebar content
        return FeedsSidebar(session_id)
        
    except Exception as e:
        print(f"ERROR: Exception in add_feed for {url}: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Return unified sidebar content even on error
        return FeedsSidebar(session_id)

@rt('/api/item/{item_id}/star')
def star_item(item_id: int, htmx, sess):
    """Toggle star status"""
    session_id = sess.get('session_id')
    # Single optimized query: toggle star and get updated item
    item = UserItemModel.toggle_star_and_get_item(session_id, item_id)
    return ItemDetailView(item)

@rt('/api/item/{item_id}/read')
def toggle_read(item_id: int, htmx, sess):
    """Toggle read status"""
    session_id = sess.get('session_id')
    
    # Single optimized query: toggle read status and get updated item
    item = UserItemModel.toggle_read_and_get_item(session_id, item_id)

    if item:
        return ItemDetailView(item)
    
    import traceback
    import json
    import sqlite3
    
    # Execute diagnostic queries to show results
    step1_result = None
    final_result = None
    try:
        with get_db() as conn:
            # Step 1 query - check current read status
            step1_result = conn.execute("""
                SELECT COALESCE(ui.is_read, 0) as current_read
                FROM feed_items fi
                LEFT JOIN user_items ui ON fi.id = ui.item_id AND ui.session_id = ?
                WHERE fi.id = ?
            """, (session_id, item_id)).fetchone()
            
            # Final query that would be used by get_item_for_user
            final_result = conn.execute("""
                SELECT fi.*, f.title as feed_title, 
                       COALESCE(ui.is_read, 0) as is_read,
                       COALESCE(ui.starred, 0) as starred,
                       fo.name as folder_name
                FROM feed_items fi
                JOIN feeds f ON fi.feed_id = f.id
                JOIN user_feeds uf ON f.id = uf.feed_id AND uf.session_id = ?
                LEFT JOIN user_items ui ON fi.id = ui.item_id AND ui.session_id = ?
                LEFT JOIN folders fo ON ui.folder_id = fo.id
                WHERE fi.id = ?
            """, (session_id, session_id, item_id)).fetchone()
    except Exception as e:
        step1_result = f"Query failed: {str(e)}"
        final_result = f"Query failed: {str(e)}"
    
    return Div(
        H2("Item Not Found - Read Toggle Diagnostic Information", cls='text-red-600 font-bold mb-4'),
        
        Details(
            Summary("SQL Query Details"),
            Pre(f"""Query: toggle_read_and_get_item(session_id='{session_id}', item_id={item_id})

Step 1 - Check current read status:
SELECT COALESCE(ui.is_read, 0) as current_read
FROM feed_items fi
LEFT JOIN user_items ui ON fi.id = ui.item_id AND ui.session_id = ?
WHERE fi.id = ?

Parameters: ('{session_id}', {item_id})"""),
            Pre(f"Step 1 Result: {json.dumps(dict(step1_result) if step1_result and isinstance(step1_result, sqlite3.Row) else step1_result, indent=2, default=str)}"),
            Pre(f"""
Step 2 - Update read status (if item exists):
INSERT OR REPLACE INTO user_items (session_id, item_id, is_read, starred, folder_id)
VALUES (?, ?, ?, 
        COALESCE((SELECT starred FROM user_items WHERE session_id = ? AND item_id = ?), 0),
        COALESCE((SELECT folder_id FROM user_items WHERE session_id = ? AND item_id = ?), NULL))

Step 3 - Return updated item via get_item_for_user():
SELECT fi.*, f.title as feed_title, 
       COALESCE(ui.is_read, 0) as is_read,
       COALESCE(ui.starred, 0) as starred,
       fo.name as folder_name
FROM feed_items fi
JOIN feeds f ON fi.feed_id = f.id
JOIN user_feeds uf ON f.id = uf.feed_id AND uf.session_id = ?
LEFT JOIN user_items ui ON fi.id = ui.item_id AND ui.session_id = ?
LEFT JOIN folders fo ON ui.folder_id = fo.id
WHERE fi.id = ?"""),
            Pre(f"Final Result: {json.dumps(dict(final_result) if final_result and isinstance(final_result, sqlite3.Row) else final_result, indent=2, default=str)}")
        ),
        
        Details(
            Summary("Request Context"),
            Pre(f"""Route: /api/item/{item_id}/read
Session ID: {session_id}
HTMX Request: {bool(htmx)}""")
        ),
        
        Details(
            Summary("Stack Trace"),
            Pre(''.join(traceback.format_stack()))
        ),
        
        cls='border border-red-300 bg-red-50 p-4 m-4 rounded text-red-500'
    )

@rt('/api/folder/add')
def add_folder(htmx, sess):
    """Add new folder"""
    session_id = sess.get('session_id')
    # Access hx-prompt through htmx parameter
    name = getattr(htmx, 'prompt', '') if htmx else ''
    if not name and htmx:
        name = getattr(htmx, 'hx_prompt', '') or ''
    name = name.strip()
    
    if name:
        FolderModel.create_folder(session_id, name)
    
    # Return updated sidebar (this is for folder add, always from desktop sidebar)
    return Div(id=ElementIDs.SIDEBAR, cls=Styling.SIDEBAR_DESKTOP)(
        FeedsSidebar(session_id)
    )

@rt('/api/session/reset')
def reset_session(sess):
    """Reset session and all user data, redirect to index"""
    from fasthtml.common import RedirectResponse
    
    session_id = sess.get('session_id')
    if session_id:
        SessionModel.delete_session(session_id)
        # Clear the session cookie
        sess.clear()
    
    # Redirect to index page (will create new session)
    return RedirectResponse(url="/", status_code=302)

@rt('/api/update-status')
def update_status():
    """Return current background worker status for UI"""
    if background_worker.queue_manager and hasattr(background_worker.queue_manager, 'worker'):
        status = background_worker.queue_manager.worker.get_status()
        return UpdateStatusContent(status)
    
    return ""

@rt('/api/memory-status')
def memory_status():
    """Return detailed memory status for monitoring and debugging"""
    if background_worker.queue_manager and hasattr(background_worker.queue_manager, 'worker'):
        memory_status = background_worker.queue_manager.worker.get_memory_status()
        return memory_status
    
    # Return basic system memory if worker not available
    import psutil
    process = psutil.Process()
    current_memory = process.memory_info().rss / 1024 / 1024
    
    return {
        'memory_mb': round(current_memory, 1),
        'worker_status': 'not_initialized',
        'warning_level': 'unknown',
        'error': 'Background worker not initialized'
    }

def UpdateStatusIndicator():
    """Global update status indicator"""
    return Div(
        id="update-status",
        hx_get="/api/update-status",
        hx_trigger="every 3s",
        hx_swap="innerHTML",
        cls="fixed bottom-4 right-4 z-50"
    )

def UpdateStatusContent(status):
    """Render update status content"""
    if status.get('is_updating', False):
        return Div(
            cls="bg-primary text-primary-foreground px-4 py-2 rounded-lg shadow-lg flex items-center gap-2"
        )(
            Span("⟳", cls="animate-spin"),
            Span(f"Updating {status['queue_size']} feeds"),
            Small(status['current_feed'] or "") if status.get('current_feed') else ""
        )
    return ""

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    
    # Always use single uvicorn process with integrated background worker
    # Check if we're in production mode
    is_production = os.environ.get("PRODUCTION", "false").lower() == "true"
    
    if is_production:
        # Production: Single uvicorn process with integrated background worker
        print(f"Starting server on 0.0.0.0:{port}")
        
        uvicorn.run(app, host="0.0.0.0", port=port, 
                   log_level="info",
                   access_log=True,   # Enable access logs for production monitoring
                   reload=False,      # Never reload in production
                   # Performance optimizations:
                   limit_concurrency=1000,  # Max concurrent connections
                   timeout_keep_alive=5,    # Keep-alive timeout in seconds
                   server_header=False,     # Don't send server header (security)
                   date_header=False)       # Don't send date header (slight performance gain)
    else:
        # Development: Use uvicorn with reload
        print(f"Starting development server on 0.0.0.0:{port}")
        
        uvicorn.run("app:app", host="0.0.0.0", port=port, 
                   reload=True,
                   log_level="info",
                   reload_dirs=["."],  # Watch current directory
                   reload_excludes=[
                       "data/*", "*.db", "venv/*", "__pycache__/*",
                       "test_*.py", "debug_*.py", "*.png", "*.jpg"  # Exclude test files and images
                   ])