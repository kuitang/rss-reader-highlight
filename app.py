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
from models import (
    SessionModel, FeedModel, FeedItemModel, UserItemModel, FolderModel,
    init_db, get_db, MINIMAL_MODE
)
from feed_parser import FeedParser, setup_default_feeds
from background_worker import initialize_worker_system, shutdown_worker_system
import background_worker
from dateutil.relativedelta import relativedelta
import contextlib

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
    MOBILE_SIDEBAR = '#mobile-sidebar'
    DESKTOP_SIDEBAR = '#sidebar'

class ElementIDs:
    """DOM element identifiers"""
    MOBILE_SIDEBAR = 'mobile-sidebar'
    MOBILE_HEADER = 'mobile-header'
    MOBILE_PERSISTENT_HEADER = 'mobile-persistent-header'
    MOBILE_NAV_BUTTON = 'mobile-nav-button'
    DESKTOP_LAYOUT = 'desktop-layout'
    MOBILE_LAYOUT = 'mobile-layout'
    MAIN_CONTENT = 'main-content'
    DESKTOP_FEEDS_CONTENT = 'desktop-feeds-content'
    DESKTOP_ITEM_DETAIL = 'desktop-item-detail'
    SIDEBAR = 'sidebar'

class Styling:
    """CSS classes for layouts and components"""
    MOBILE_LAYOUT = 'lg:hidden fixed inset-0 flex flex-col overflow-hidden'
    DESKTOP_LAYOUT = 'hidden lg:grid h-screen pt-4'
    FEED_ITEM_BASE = 'relative rounded-lg border border-border p-3 text-sm hover:bg-secondary space-y-2 cursor-pointer'
    FEED_ITEM_READ = 'bg-muted tag-read'
    FEED_ITEM_UNREAD = 'tag-unread'
    SIDEBAR_DESKTOP = 'col-span-1 h-screen overflow-y-auto border-r px-2'
    DESKTOP_FEEDS_COLUMN = 'col-span-2 h-screen flex flex-col overflow-hidden border-r px-4'
    DESKTOP_DETAIL_COLUMN = 'col-span-2 h-screen overflow-y-auto px-6'
    MOBILE_SIDEBAR_OVERLAY = 'fixed inset-0 z-50 lg:hidden'
    MOBILE_PERSISTENT_HEADER = 'flex-shrink-0 bg-background border-b z-10 lg:hidden'
    MOBILE_HEADER = 'lg:hidden fixed top-0 left-0 right-0 bg-background border-b p-4 z-40'
    BUTTON_SECONDARY = 'p-2 rounded border hover:bg-secondary'
    BUTTON_NAV = 'p-2 rounded border hover:bg-secondary mr-2'
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
        
        # EXPLICIT DUAL-LAYOUT SUPPORT
        # Mobile and desktop need different configs - this is by design
        self.mobile_config = {
            'target': Targets.MOBILE_CONTENT,  # Full-screen content swap
            'push_url': True,
            'show_summary': True,
            'layout': 'mobile',
            'id_prefix': 'mobile-'
        }
        
        self.desktop_config = {
            'feeds_target': Targets.DESKTOP_FEEDS,  # Middle column only
            'detail_target': Targets.DESKTOP_DETAIL,  # Right column only
            'push_url': True, 
            'show_summary': True,
            'layout': 'desktop',
            'id_prefix': 'desktop-'
        }
    
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

class MobileHandlers:
    """Mobile uses #main-content for full-screen navigation"""
    
    @staticmethod
    def content(data):
        """Mobile content area - feeds list or article detail"""
        responses = [FeedsContent(data.session_id, data.feed_id, data.unread, 
                    data.page, for_desktop=False, data=data)]
        
        # Update persistent header with correct tab state for mobile
        updated_header = Div(
            cls='flex-shrink-0 bg-background border-b z-10 lg:hidden',
            id='mobile-persistent-header',
            hx_swap_oob="outerHTML",
            onwheel="event.preventDefault(); event.stopPropagation(); return false;"
        )(
            Div(cls='flex px-4 py-2')(
                H3(data.feed_name),
                create_tab_container(data.feed_name, data.feed_id, data.unread, for_mobile=True)
            ),
            Div(cls='px-4 pb-2')(
                Div(cls='uk-inline w-full')(
                    Span(cls='uk-form-icon text-muted-foreground')(UkIcon('search')),
                    Input(placeholder='Search posts', uk_filter_control="", id="mobile-persistent-search")
                )
            )
        )
        responses.append(updated_header)
        
        return tuple(responses)
    
    @staticmethod
    def sidebar(data):
        """Mobile sidebar overlay"""
        return MobileSidebar(data.session_id)
    
    @staticmethod
    def navigation_restore(data):
        """Restore mobile navigation when returning from article"""
        responses = [FeedsContent(data.session_id, data.feed_id, data.unread, 
                    data.page, for_desktop=False, data=data)]
        
        # Update persistent header with correct tab state using hx_swap_oob
        updated_header = Div(
            cls='flex-shrink-0 bg-background border-b z-10 lg:hidden',
            id='mobile-persistent-header',
            hx_swap_oob="outerHTML",
            onwheel="event.preventDefault(); event.stopPropagation(); return false;"
        )(
            Div(cls='flex px-4 py-2')(
                H3(data.feed_name),
                create_tab_container(data.feed_name, data.feed_id, data.unread, for_mobile=True)
            ),
            Div(cls='px-4 pb-2')(
                Div(cls='uk-inline w-full')(
                    Span(cls='uk-form-icon text-muted-foreground')(UkIcon('search')),
                    Input(placeholder='Search posts', uk_filter_control="", id="mobile-persistent-search")
                )
            )
        )
        responses.append(updated_header)
        
        # Remove article-view class from body to show persistent header
        body_class_script = Script("""
        document.body.classList.remove('article-view');
        """)
        responses.append(body_class_script)
        
        # Restore hamburger button for list view
        hamburger_button = Button(
            UkIcon('menu'),
            cls="p-2 rounded border hover:bg-secondary mr-2",
            onclick="document.getElementById('mobile-sidebar').removeAttribute('hidden')",
            id="mobile-nav-button",
            hx_swap_oob="outerHTML"
        )
        responses.append(hamburger_button)
        
        return tuple(responses)

class DesktopHandlers:
    """Desktop uses separate targets for each column"""
    
    @staticmethod
    def feeds_column(data):
        """Middle column - feeds list only"""
        return FeedsContent(data.session_id, data.feed_id, data.unread,
                          data.page, for_desktop=True, data=data)
    
    @staticmethod
    def detail_column(data, item_id=None):
        """Right column - article detail only"""
        if item_id:
            item = FeedItemModel.get_item_for_user(data.session_id, item_id)
            return ItemDetailView(item, show_back=False)
        return ItemDetailView(None)
    
    @staticmethod
    def sidebar_column(data):
        """Left column - feeds sidebar"""
        return Div(id=ElementIDs.SIDEBAR, cls=Styling.SIDEBAR_DESKTOP)(
            FeedsSidebar(data.session_id)
        )

# ROUTING MAP - Explicit about which handler for which target
HTMX_ROUTING = {
    # Mobile targets
    'main-content': MobileHandlers.content,
    '#main-content': MobileHandlers.content,
    'mobile-sidebar': MobileHandlers.sidebar,
    '#mobile-sidebar': MobileHandlers.sidebar,
    
    # Desktop targets
    'desktop-feeds-content': DesktopHandlers.feeds_column,
    '#desktop-feeds-content': DesktopHandlers.feeds_column,
    'desktop-item-detail': DesktopHandlers.detail_column,
    '#desktop-item-detail': DesktopHandlers.detail_column,
    'sidebar': DesktopHandlers.sidebar_column,
    '#sidebar': DesktopHandlers.sidebar_column,
}

def route_htmx_fragment(htmx, data):
    """Route HTMX requests using handlers from Step 4"""
    
    # Use the HTMX_ROUTING map from Step 4
    handler = HTMX_ROUTING.get(htmx.target)
    if not handler:
        return Alert(f"Unknown target: {htmx.target}", type='error', cls='m-4')
    
    # Special case for mobile navigation restore
    if htmx.target in ['main-content', '#main-content'] and is_returning_from_article(htmx):
        return MobileHandlers.navigation_restore(data)
    
    # Otherwise use the mapped handler
    return handler(data)

def is_returning_from_article(htmx):
    """Check if this is a mobile navigation back from article view"""
    # Check if this is a navigation back scenario by looking for specific parameters
    # This is a simplified check - could be enhanced based on specific needs
    return hasattr(htmx, 'current_url') and '/item/' in str(getattr(htmx, 'current_url', ''))

def full_page_dual_layout(data):
    """Complete page with both mobile and desktop layouts"""
    # Flatten the mobile_chrome list and return individual elements
    chrome_elements = mobile_chrome(data.session_id, data.feed_id, data.unread)
    return (
        *chrome_elements,  # Unpack mobile chrome elements
        desktop_layout(data),
        mobile_layout(data), 
        viewport_styles()
    )

def mobile_chrome(session_id, feed_id=None, unread=True):
    """Mobile-specific chrome elements"""
    return [
        Div(id='mobile-header')(MobileHeader(session_id, show_back=False, feed_id=feed_id, unread_view=unread)),
        MobileSidebar(session_id)
    ]

def mobile_layout(data):
    """Mobile layout - single column, full-screen navigation"""
    return Div(cls=Styling.MOBILE_LAYOUT, id="mobile-layout")(
        Div(cls="h-20 flex-shrink-0"),  # Header spacer
        MobilePersistentHeader(data.session_id, data.feed_id, data.unread),
        Div(cls="flex-1 overflow-y-auto", id="main-content")(
            MobileHandlers.content(data)
        )
    )

def desktop_layout(data):
    """Desktop layout - three-column email interface"""
    return Div(cls=Styling.DESKTOP_LAYOUT, id="desktop-layout")(
        Grid(
            DesktopHandlers.sidebar_column(data),
            Div(cls=Styling.DESKTOP_FEEDS_COLUMN, id="desktop-feeds-content")(
                DesktopHandlers.feeds_column(data)
            ),
            Div(id="desktop-item-detail", cls=Styling.DESKTOP_DETAIL_COLUMN)(
                ItemDetailView(None)  # Empty on initial load
            ),
            cols_lg=5, cols_xl=5, gap=4, cls='h-screen gap-4'
        )
    )

def viewport_styles():
    """Global styles for viewport management"""
    return Style("""
    /* Fix viewport scrolling - prevent main viewport scroll on ALL devices */
    html, body {
        height: 100% !important;
        max-height: 100vh !important;
        overflow: hidden !important;
        position: fixed !important;
        width: 100% !important;
    }
    
    /* Ensure only designated containers can scroll */
    .scrollable-panel {
        overflow-y: auto !important;
    }
    
    /* Unified responsive form targeting */
    .add-feed-form {
        /* Desktop: target parent sidebar */
    }
    
    .add-feed-form.mobile-context {
        /* Mobile: target mobile sidebar container */
    }
    
    .add-feed-button {
        /* Default desktop targeting */
    }
    
    /* Mobile sidebar context gets different targeting */
    #mobile-sidebar .add-feed-form {
        /* Mobile-specific HTMX targeting handled via JS */
    }
    """)

def create_tab_container(feed_name, feed_id, unread_only, for_mobile=False):
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
             # Mobile-only: HTMX attributes for partial updates
             **({'hx_get': f"{base_url}{'&' if url_params else '?'}unread=0" if base_url != "/" else "/?unread=0",
                'hx_target': Targets.MOBILE_CONTENT,
                'hx_push_url': "true"} if for_mobile else {}),
             role='button'),
           cls='uk-active' if not unread_only else ''),
        Li(A("Unread",
             href=base_url if base_url != "/" else "/",
             # Mobile-only: HTMX attributes for partial updates
             **({'hx_get': base_url if base_url != "/" else "/",
                'hx_target': Targets.MOBILE_CONTENT,
                'hx_push_url': "true"} if for_mobile else {}),
             role='button'),
           cls='uk-active' if unread_only else ''),
        alt=True, cls='ml-auto max-w-40'
    )

def prepare_item_data(session_id, item_id, feed_id, unread_view):
    """Centralized item data preparation"""
    class ItemData:
        def __init__(self):
            self.item = FeedItemModel.get_item_for_user(session_id, item_id)
            self.was_unread = not self.item.get('is_read', 0) if self.item else False
            self.feed_id = feed_id
            self.unread_view = unread_view
            self.session_id = session_id
            self.item_id = item_id
        
        def mark_read_and_refresh(self):
            """Mark item as read and refresh data"""
            if self.item:
                self.item = UserItemModel.mark_read_and_get_item(self.session_id, self.item_id, True)
    
    return ItemData()

def htmx_item_response(htmx, item_data, _scroll=None):
    """HTMX item response using routing patterns"""
    responses = [ItemDetailView(item_data.item, show_back=False)]
    
    # MOBILE UPDATES - Full article view setup
    if htmx.target in ['main-content', '#main-content']:
        # Add CSS class to body to hide mobile persistent header
        body_class_script = Script("""
        document.body.classList.add('article-view');
        """)
        responses.append(body_class_script)
        
        # Update nav button to show chevron for article view
        back_url = "/"
        if item_data.feed_id:
            back_url = f"/?feed_id={item_data.feed_id}"
        
        # Add unread parameter based on the view we came from
        if item_data.unread_view is False:  # We came from "All Posts" view
            back_url += "&unread=0" if item_data.feed_id else "?unread=0"
        
        # Preserve scroll position if provided
        if _scroll:
            back_url += f"&_scroll={_scroll}" if '?' in back_url else f"?_scroll={_scroll}"
        
        back_button = Button(
            UkIcon('arrow-left'),
            hx_get=back_url,
            hx_target=Targets.MOBILE_CONTENT,
            hx_push_url="true",
            cls="p-2 rounded border hover:bg-secondary mr-2",
            id="mobile-nav-button",
            hx_swap_oob="outerHTML"
        )
        responses.append(back_button)
    
    # DESKTOP UPDATES - Update list item appearance if it was unread
    elif htmx.target in ['desktop-item-detail', '#desktop-item-detail'] and item_data.was_unread:
        updated_item_attrs = {
            "cls": f"relative rounded-lg border border-border p-3 text-sm hover:bg-secondary space-y-2 cursor-pointer bg-muted tag-read",
            "id": f"desktop-feed-item-{item_data.item['id']}",
            "hx_get": f"/item/{item_data.item['id']}?unread_view={item_data.unread_view}",
            "hx_target": "#desktop-item-detail",
            "hx_trigger": "click",
            "hx_swap_oob": "true"
        }
        
        updated_item = Li(
            # Title row with no blue dot (read state)
            DivLAligned(
                Span(item_data.item['title']),  # Unbolded title for read items
                # No blue dot for read items
            ),
            # Source and time row - source left, time right
            DivFullySpaced(
                Small(item_data.item.get('feed_title', 'Unknown Feed'), cls=TextPresets.muted_sm),
                Time(human_time_diff(item_data.item.get('published')), cls='text-xs text-muted-foreground')
            ),
            **updated_item_attrs
        )
        responses.append(updated_item)
    
    return responses[0] if len(responses) == 1 else tuple(responses)

def full_page_item_response(item_data):
    """Full page response for item with proper layout"""
    # Create PageData for consistency
    page_data = PageData(item_data.session_id, item_data.feed_id, item_data.unread_view, 1)
    
    # Modify desktop layout to show the item in detail column
    def desktop_layout_with_item(data, item):
        return Div(cls=Styling.DESKTOP_LAYOUT, id="desktop-layout")(
            Grid(
                DesktopHandlers.sidebar_column(data),
                Div(cls=Styling.DESKTOP_FEEDS_COLUMN, id="desktop-feeds-content")(
                    FeedsContent(data.session_id, data.feed_id, data.unread, 1, for_desktop=True)
                ),
                Div(id="desktop-item-detail", cls=Styling.DESKTOP_DETAIL_COLUMN)(
                    ItemDetailView(item, show_back=False)
                ),
                cols_lg=5, cols_xl=5, gap=4, cls='h-screen gap-4'
            )
        )
    
    # Modify mobile layout to show the item
    def mobile_layout_with_item(data, item):
        return Div(cls=Styling.MOBILE_LAYOUT, id="mobile-layout")(
            Div(cls="h-20 flex-shrink-0"),  # Header spacer
            MobilePersistentHeader(data.session_id, data.feed_id, data.unread, show_chrome=False),
            Div(cls="flex-1 overflow-y-auto", id="main-content")(
                ItemDetailView(item, show_back=True)
            )
        )
    
    return (
        # Chrome elements for item view
        Div(id='mobile-header')(MobileHeader(item_data.session_id, show_back=True, feed_id=item_data.feed_id, unread_view=item_data.unread_view)),
        MobileSidebar(item_data.session_id),
        
        # BOTH LAYOUTS with item content
        mobile_layout_with_item(page_data, item_data.item),
        desktop_layout_with_item(page_data, item_data.item),
        
        # Global styles
        viewport_styles()
    )

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
    
    # Store in request scope for easy access
    req.scope['session_id'] = session_id

# Lifespan event handler for background worker
@contextlib.asynccontextmanager
async def lifespan(app):
    """Handle app startup and shutdown with background worker"""
    if MINIMAL_MODE:
        print("FastHTML app starting in MINIMAL MODE...")
        print("⚡ Skipping background worker and default feeds for fast startup")
    else:
        print("FastHTML app starting up...")
        
        # Initialize background worker in single process
        initialize_worker_system()
        print("Background worker system initialized")
        
        # Add default feeds - database constraints handle duplicates
        print("Adding default feeds to database...")
        setup_default_feeds()
    
    yield  # App is running
    
    # Shutdown: Clean up background worker only if not in minimal mode
    if not MINIMAL_MODE:
        print("Shutting down background worker...")
        shutdown_worker_system()
    print("FastHTML app shutdown complete")

# FastHTML app with session support and lifespan
app, rt = fast_app(
    hdrs=Theme.blue.headers() + [
        Script("""
        htmx.logAll();
        htmx.config.includeIndicatorStyles = false;
        
        // Scroll restoration using hx-vals (configured per FeedItem)
        // Restore scroll position after navigating back
        htmx.on('htmx:afterSwap', function(evt) {
            if (window.innerWidth < 1024 && evt.detail.target && evt.detail.target.id === 'main-content') {
                // Extract scroll position from request path
                if (evt.detail.pathInfo && evt.detail.pathInfo.requestPath) {
                    const match = evt.detail.pathInfo.requestPath.match(/_scroll=(\\d+)/);
                    if (match) {
                        const scrollPos = parseInt(match[1]);
                        setTimeout(() => {
                            const mainContent = document.getElementById('main-content');
                            if (mainContent) {
                                mainContent.scrollTop = scrollPos;
                            }
                        }, 50);
                    }
                }
            }
        });
        
        // Close mobile sidebar when a feed link is clicked
        document.addEventListener('click', function(e) {
            // Check if clicked element is a feed link
            if (e.target.closest('a[href^="/?feed_id="], a[href^="/?folder_id="], a[href="/"]')) {
                const sidebar = document.getElementById('mobile-sidebar');
                if (sidebar && !sidebar.hasAttribute('hidden')) {
                    sidebar.setAttribute('hidden', 'true');
                }
            }
        });
        
        // Unified responsive form targeting
        document.addEventListener('htmx:configRequest', function(e) {
            if (e.detail.elt.classList.contains('add-feed-form')) {
                // Determine target based on container
                const isMobile = e.detail.elt.closest('#mobile-sidebar');
                
                if (isMobile) {
                    // Override target for mobile context
                    e.detail.target = '#mobile-sidebar';
                    e.detail.headers['HX-Target'] = '#mobile-sidebar';
                }
                // Desktop keeps default #sidebar target
            }
        });
        
        // Removed afterSwap handler - now using CSS classes instead of hidden attribute
        
        """),
        Style("""
        .htmx-indicator { display: none; }
        .htmx-request .htmx-indicator { display: flex; }
        
        /* Hide mobile persistent header when body has article-view class */
        body.article-view #mobile-persistent-header {
            display: none !important;
        }
        
        /* Fix viewport scrolling on mobile - more specific and with !important */
        @media (max-width: 1023px) {
            html, body {
                height: 100% !important;
                max-height: 100vh !important;
                overflow: hidden !important;
                position: fixed !important;
                width: 100% !important;
            }
        }
        """)
    ],
    live=True,
    debug=True,
    before=[timing_middleware, before],
    after=after_middleware,
    lifespan=lifespan
)

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
    """Create sidebar item for feed (adapted from MailSbLi)"""
    last_updated = human_time_diff(feed.get('last_updated'))
    
    # Handle Unknown timestamp gracefully
    update_text = last_updated if last_updated != "Unknown" else "never updated"
    
    # Alternative: Use hx_boost="false" to prevent HTMX interception
    # This tells HTMX to skip this link entirely, allowing normal navigation
    return Li(
        A(
            DivLAligned(
                UkIcon('rss', cls="flex-none"),
                Span(feed['title'] or 'Untitled Feed'),
                P(f"updated {update_text}", cls="text-xs text-muted"),
                cls="gap-3"
            ),
            href=f"/?feed_id={feed['id']}",
            cls=Styling.SIDEBAR_ITEM
        )
    )

def FeedsSidebar(session_id):
    """Create unified feeds sidebar that works for both mobile and desktop"""
    feeds = FeedModel.get_user_feeds(session_id)
    folders = FolderModel.get_folders(session_id)
    
    return Ul(
        Li(H3("Feeds"), cls='p-3'),
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
                hx_target=Targets.DESKTOP_SIDEBAR,  # Default to desktop, JS will override for mobile
                hx_swap="outerHTML",
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
                cls="hover:bg-secondary p-4 block"
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

def FeedItem(item, unread_view=False, for_desktop=False, feed_id=None):
    """Feed item component
    
    Args:
        for_desktop: True for desktop layout (targets #desktop-item-detail),
                    False for mobile (targets #main-content)
    
    The different targets are architectural - mobile swaps full screen,
    desktop updates only the detail column.
    """
    cls_base = Styling.FEED_ITEM_BASE
    is_read = item.get('is_read', 0) == 1
    
    read_bg = Styling.FEED_ITEM_READ if is_read else Styling.FEED_ITEM_UNREAD
    cls = f"{cls_base} {read_bg}"
    
    # Build item URL with feed context preserved
    item_url = f"/item/{item['id']}?unread_view={unread_view}"
    if feed_id:
        item_url += f"&feed_id={feed_id}"
    
    # Simple consistent approach: same HTMX pattern, just different targets
    if for_desktop:
        target = Targets.DESKTOP_DETAIL
        push_url = "true"  # Enable URL push for desktop to fix back button navigation
    else:
        target = Targets.MOBILE_CONTENT
        push_url = "true"  # URL push for mobile full-page navigation
    
    # Use unique IDs for desktop vs mobile to avoid HTML violations
    item_id = f"{'desktop-' if for_desktop else 'mobile-'}feed-item-{item['id']}"
    
    attrs = {
        "cls": cls,
        "id": item_id,
        "hx_get": item_url,
        "hx_target": target,
        "hx_trigger": "click"
    }
    
    if push_url:
        attrs["hx_push_url"] = push_url
    
    # Add scroll position capture for mobile using hx-vals
    if not for_desktop:  # Mobile only
        attrs["hx_vals"] = 'js:{_scroll: window.innerWidth < 1024 ? (document.getElementById("main-content")?.scrollTop || 0) : 0}'
    
    return Li(
        # Title row with blue dot
        DivLAligned(
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

def FeedsList(items, unread_view=False, for_desktop=False, feed_id=None):
    """Create list of feed items (adapted from MailList)"""
    return Ul(cls='js-filter space-y-2 p-4 pt-0')(*[FeedItem(item, unread_view, for_desktop, feed_id) for item in items])

def MobilePersistentHeader(session_id, feed_id=None, unread_only=False, show_chrome=True):
    """Create persistent mobile header with tabs and search form - conditionally visible"""
    # Simple header logic
    if feed_id:
        feeds = FeedModel.get_user_feeds(session_id)
        feed = next((f for f in feeds if f['id'] == feed_id), None)
        feed_name = feed['title'] if feed else "Unknown Feed"
    else:
        feed_name = "All Feeds"
    
    # Build URL parameters for tab navigation
    url_params = []
    if feed_id:
        url_params.append(f"feed_id={feed_id}")
    
    # Base URL for tab navigation
    base_url = "/?" + "&".join(url_params) if url_params else "/"
    
    # Option 2: Return completely different elements based on visibility
    # This ensures HTMX can do simple element replacement
    if not show_chrome:
        # Return a hidden placeholder div with same ID
        return Div(
            id='mobile-persistent-header',
            cls='hidden',
            style='display: none;'
        )()
    
    # Return the visible header - removed hx-preserve to allow tab state updates
    return Div(
        cls='flex-shrink-0 bg-background border-b z-10 lg:hidden',
        id='mobile-persistent-header',
        onwheel="event.preventDefault(); event.stopPropagation(); return false;"
    )(
        Div(cls='flex px-4 py-2')(
            H3(feed_name),
            create_tab_container(feed_name, feed_id, unread_only, for_mobile=True)
        ),
        Div(cls='px-4 pb-2')(
            Div(cls='uk-inline w-full')(
                Span(cls='uk-form-icon text-muted-foreground')(UkIcon('search')),
                Input(placeholder='Search posts', uk_filter_control="", id="mobile-persistent-search")
            )
        )
    )

def FeedsContent(session_id, feed_id=None, unread_only=False, page=1, for_desktop=False, data=None):
    """Create main feeds content area with pagination - MOBILE VERSION NO LONGER INCLUDES HEADER
    
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
    
    print(f"🔍 MOBILE_FORM_BUG_FIX: FeedsContent() - for_desktop={for_desktop}, MOBILE header moved to persistent header")
    
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
        
        return Div(cls='p-4 border-t')(
            DivFullySpaced(
                Div(f"Showing {len(paginated_items)} of {total_items} posts", cls=TextPresets.muted_sm),
                DivLAligned(
                    DivCentered(f'Page {page} of {total_pages}', cls=TextT.sm),
                    DivLAligned(
                        # Mobile versions
                        Button(UkIcon('chevrons-left'), hx_get=first_url, hx_target=Targets.MOBILE_CONTENT, hx_push_url="true", cls="p-2 rounded border hover:bg-secondary lg:hidden"),
                        Button(UkIcon('chevron-left'), hx_get=prev_url, hx_target=Targets.MOBILE_CONTENT, hx_push_url="true", cls="p-2 rounded border hover:bg-secondary lg:hidden"),
                        Button(UkIcon('chevron-right'), hx_get=next_url, hx_target=Targets.MOBILE_CONTENT, hx_push_url="true", cls="p-2 rounded border hover:bg-secondary lg:hidden"),
                        Button(UkIcon('chevrons-right'), hx_get=last_url, hx_target=Targets.MOBILE_CONTENT, hx_push_url="true", cls="p-2 rounded border hover:bg-secondary lg:hidden"),
                        # Desktop versions - use HTMX for consistency
                        Button(UkIcon('chevrons-left'), hx_get=first_url, hx_target=Targets.DESKTOP_FEEDS if for_desktop else "#main-content", cls="p-2 rounded border hover:bg-secondary hidden lg:inline-block"),
                        Button(UkIcon('chevron-left'), hx_get=prev_url, hx_target=Targets.DESKTOP_FEEDS if for_desktop else "#main-content", cls="p-2 rounded border hover:bg-secondary hidden lg:inline-block"),
                        Button(UkIcon('chevron-right'), hx_get=next_url, hx_target=Targets.DESKTOP_FEEDS if for_desktop else "#main-content", cls="p-2 rounded border hover:bg-secondary hidden lg:inline-block"),
                        Button(UkIcon('chevrons-right'), hx_get=last_url, hx_target=Targets.DESKTOP_FEEDS if for_desktop else "#main-content", cls="p-2 rounded border hover:bg-secondary hidden lg:inline-block"),
                        cls='space-x-1'
                    )
                )
            )
        )
    
    # Different layouts for mobile vs desktop
    if for_desktop:
        # Desktop: sticky header + scrollable content (unchanged)
        return Div(cls='flex flex-col h-full')(
            # Sticky header section
            Div(cls='sticky top-0 bg-background border-b z-10')(
                Div(cls='flex px-4 py-3')(
                    H3(feed_name),
                    create_tab_container(feed_name, feed_id, unread_only, for_mobile=False)
                ),
                Div(cls='px-4 pb-3')(
                    Div(cls='uk-inline w-full')(
                        Span(cls='uk-form-icon text-muted-foreground')(UkIcon('search')),
                        Input(placeholder='Search posts', uk_filter_control="")
                    )
                )
            ),
            # Scrollable content area
            Div(cls='flex-1 overflow-y-auto', id="feeds-list-container", uk_filter="target: .js-filter")(
                FeedsList(paginated_items, unread_only, for_desktop, feed_id) if paginated_items else Div(P("No posts available"), cls='p-4 text-center text-muted-foreground'),
                pagination_footer()
            )
        )
    else:
        # Mobile: ONLY content (header moved to persistent header, parent handles scrolling)
        return Div(cls='p-0', id="feeds-list-container", uk_filter="target: .js-filter")(
            FeedsList(paginated_items, unread_only, for_desktop, feed_id) if paginated_items else Div(P("No posts available"), cls='p-4 text-center text-muted-foreground'),
            pagination_footer()
        )

def MobileSidebar(session_id):
    """Create mobile sidebar overlay"""
    return Div(
        id=ElementIDs.MOBILE_SIDEBAR,
        cls="fixed inset-0 z-50 lg:hidden",
        hidden="true"
    )(
        Div(
            cls="bg-black bg-opacity-50 absolute inset-0",
            onclick="document.getElementById('mobile-sidebar').setAttribute('hidden', 'true')"
        ),
        Div(cls="bg-background w-80 h-full overflow-y-auto relative z-10")(
            Div(cls="p-4 border-b")(
                DivFullySpaced(
                    H3("RSS Reader"),
                    Button(
                        UkIcon('x'),
                        cls="p-1 rounded hover:bg-secondary",
                        onclick="document.getElementById('mobile-sidebar').setAttribute('hidden', 'true')"
                    )
                )
            ),
            FeedsSidebar(session_id)
        )
    )

def MobileHeader(session_id, show_back=False, feed_id=None, unread_view=False):
    """Create mobile header with hamburger menu and optional back button - unified component"""
    
    # Build return URL with feed context and toggle state preserved
    return_url = "/"
    if feed_id:
        if unread_view:
            return_url = f"/?feed_id={feed_id}"  # Unread view (default)
        else:
            return_url = f"/?feed_id={feed_id}&unread=0"  # All posts view
    else:
        # No specific feed - preserve global toggle state
        if not unread_view:
            return_url = "/?unread=0"  # All posts view
    
    # Loading spinner - hidden by default, shown during HTMX requests
    loading_spinner = Div(
        id="loading-spinner",
        cls="fixed top-20 left-1/2 transform -translate-x-1/2 bg-background border rounded p-3 z-50 lg:hidden htmx-indicator hidden"
    )(
        DivLAligned(
            UkIcon('loader', cls="animate-spin"),
            Span("Loading...", cls="ml-2")
        )
    )
    
    # Single parameterized header - either back button (for article view) or hamburger (for list view)
    nav_button = Button(
        UkIcon('arrow-left'),
        hx_get=return_url,
        hx_target=Targets.MOBILE_CONTENT,
        hx_push_url="true",
        cls="p-2 rounded border hover:bg-secondary mr-2",
        id="mobile-nav-button"
    ) if show_back else Button(
        UkIcon('menu'),
        cls="p-2 rounded border hover:bg-secondary mr-2",  # Added mr-2 for consistent spacing
        onclick="document.getElementById('mobile-sidebar').removeAttribute('hidden')",
        id="mobile-nav-button"
    )
    
    return Div(
        # Fixed header bar
        Div(cls="lg:hidden fixed top-0 left-0 right-0 bg-background border-b p-4 z-40")(
            DivFullySpaced(
                DivLAligned(
                    nav_button,
                    H3("RSS Reader", cls="ml-3")
                )
            )
        ),
        loading_spinner
    )

def ItemDetailView(item, show_back=False):
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
            )
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
            NotStr(mistletoe.markdown(item.get('content') or item.get('description') or 'No content available')),
            cls=TextT.sm + 'p-4 prose max-w-none'
        ),
        id="item-detail"
    )

@rt('/')
def index(htmx, sess, feed_id: int = None, unread: bool = True, folder_id: int = None, page: int = 1, _scroll: int = None):
    """Main page with mobile-first responsive design"""
    session_id = sess.get('session_id')
    
    # STEP 3: Use centralized data preparation
    data = PageData(session_id, feed_id, unread, page)
    
    # Queue user's feeds for background updating (skip in minimal mode)
    if not MINIMAL_MODE and background_worker.queue_manager:
        try:
            background_worker.queue_manager.queue_user_feeds(session_id)
            print(f"DEBUG: Queued user feeds for background update")
        except Exception as e:
            print(f"WARNING: Could not queue user feeds: {str(e)}")
    
    # HTMX - Use routing from Step 5
    if htmx and getattr(htmx, 'request', None) and getattr(htmx, 'target', None):
        return route_htmx_fragment(htmx, data)
    
    # FULL PAGE - From Step 5
    return Titled("RSS Reader", *full_page_dual_layout(data))

@rt('/item/{item_id}')
def show_item(item_id: int, htmx, sess, unread_view: bool = False, feed_id: int = None, _scroll: int = None):
    """Item detail route following same pattern"""
    session_id = sess.get('session_id')
    
    # Prepare item data
    item_data = prepare_item_data(session_id, item_id, feed_id, unread_view)
    
    if not item_data.item:
        if htmx and getattr(htmx, 'request', None) and getattr(htmx, 'target', None):
            return Alert("Item not found", type='error', cls='m-4')
        else:
            # Create empty PageData for not found case
            page_data = PageData(session_id, feed_id, True, 1)
            return Titled("RSS Reader", *full_page_dual_layout(page_data))
    
    # Mark as read
    item_data.mark_read_and_refresh()
    
    # Route response
    if htmx and getattr(htmx, 'request', None) and getattr(htmx, 'target', None):
        return htmx_item_response(htmx, item_data, _scroll)
    else:
        return Titled("RSS Reader", *full_page_item_response(item_data))

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
        
        # Return unified sidebar response - JavaScript targeting handles mobile vs desktop
        target_container = getattr(htmx, 'target', '') if htmx else ''
        
        if target_container and 'mobile-sidebar' in target_container:
            # Mobile: return complete mobile sidebar structure  
            return MobileSidebar(session_id)
        else:
            # Desktop: return sidebar container with content
            return Div(id=ElementIDs.SIDEBAR, cls=Styling.SIDEBAR_DESKTOP)(
                FeedsSidebar(session_id)
            )
        
    except Exception as e:
        print(f"ERROR: Exception in add_feed for {url}: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Return proper sidebar structure even on error
        target_container = getattr(htmx, 'target', '') if htmx else ''
        
        if target_container and 'mobile-sidebar' in target_container:
            return MobileSidebar(session_id)
        else:
            return Div(id=ElementIDs.SIDEBAR, cls=Styling.SIDEBAR_DESKTOP)(
                FeedsSidebar(session_id)
            )

@rt('/api/item/{item_id}/star')
def star_item(item_id: int, htmx, sess):
    """Toggle star status"""
    session_id = sess.get('session_id')
    # Single optimized query: toggle star and get updated item
    item = UserItemModel.toggle_star_and_get_item(session_id, item_id)
    return ItemDetailView(item, show_back=bool(htmx))

@rt('/api/item/{item_id}/read')
def toggle_read(item_id: int, htmx, sess):
    """Toggle read status"""
    session_id = sess.get('session_id')
    
    # Single optimized query: toggle read status and get updated item
    item = UserItemModel.toggle_read_and_get_item(session_id, item_id)
    
    if item:
        return ItemDetailView(item, show_back=bool(htmx))
    
    return Div("Item not found", cls='text-red-500 p-4')

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