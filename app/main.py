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

# Initialize database and setup default feeds if needed
init_db()

# Default feeds will be set up by background worker on first startup

# =============================================================================
# RESPONSIVE SINGLE-ELEMENT ARCHITECTURE
# =============================================================================
# This app uses a SINGLE HTML structure that adapts responsively:
# - One set of elements with CSS media queries for responsive behavior
# - JavaScript only for essential mobile interactions (sidebar, article nav)
# - HTMX targets remain consistent across viewports
# - No duplicate elements or conditional rendering
# =============================================================================

# =============================================================================
# CONFIGURATION - All decisions and constants visible here
# =============================================================================

class Targets:
    """HTMX update targets - unified for responsive design"""
    CONTENT = '#feed-list'
    DETAIL = '#article-detail'
    SIDEBAR = '#sidebar'

class ElementIDs:
    """DOM element identifiers - single set for responsive design"""
    SIDEBAR = 'sidebar'
    NAV_BUTTON = 'nav-button'
    CHROME_CONTAINER = 'chrome-container'
    FEED_LIST = 'feed-list'
    ARTICLE_DETAIL = 'article-detail'
    ICON_BAR = 'icon-bar'
    SEARCH_BAR = 'search-bar'
    APP_CONTAINER = 'app-container'
    CONTENT_AREA = 'content-area'

class Styling:
    """CSS classes for responsive components"""
    APP_LAYOUT = 'h-screen w-screen overflow-hidden'
    FEED_ITEM_BASE = 'relative rounded-lg border border-border p-3 text-sm hover:bg-secondary space-y-2 cursor-pointer'
    FEED_ITEM_READ = 'bg-muted tag-read'
    FEED_ITEM_UNREAD = 'tag-unread'
    SIDEBAR = 'sidebar-responsive'
    CHROME = 'chrome-responsive'
    BUTTON_SECONDARY = 'p-2 rounded border hover:bg-secondary'
    BUTTON_NAV = 'nav-button-responsive'
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
        
        # Unified config - no more dual layout
        self.config = {
            'target': Targets.CONTENT,  # Single content target
            'detail_target': Targets.DETAIL,  # Single detail target
            'push_url': True,
            'show_summary': True,
            'layout': 'responsive',
            'id_prefix': ''
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

# Removed old mobile/desktop handlers - now using unified responsive handlers

# Unified HTMX handlers
def unified_feeds_handler(data):
    """Handle feed list updates"""
    return FeedsContent(data.session_id, data.feed_id, data.unread, data.page, data=data)

def unified_article_handler(data, item_id=None):
    """Handle article detail updates"""
    if item_id:
        item = FeedItemModel.get_item_for_user(data.session_id, item_id)
        return ItemDetailView(item, show_back=False)
    return ItemDetailView(None)

def unified_sidebar_handler(data):
    """Handle sidebar updates"""
    return responsive_sidebar(data.session_id)

# ROUTING MAP - Unified handlers
HTMX_ROUTING = {
    # Feed list targets
    'feed-list': unified_feeds_handler,
    '#feed-list': unified_feeds_handler,

    # Article detail targets
    'article-detail': unified_article_handler,
    '#article-detail': unified_article_handler,

    # Sidebar targets
    'sidebar': unified_sidebar_handler,
    '#sidebar': unified_sidebar_handler,
}

def route_htmx_fragment(htmx, data):
    """Route HTMX requests using unified handlers"""

    # Use the HTMX_ROUTING map
    handler = HTMX_ROUTING.get(htmx.target)
    if not handler:
        return Alert(f"Unknown target: {htmx.target}", type='error', cls='m-4')

    # Pass item_id for article detail handler if available
    if 'article-detail' in htmx.target and hasattr(htmx, 'item_id'):
        return handler(data, htmx.item_id)

    # Otherwise use the mapped handler
    return handler(data)

def is_returning_from_article(htmx):
    """Check if this is a mobile navigation back from article view"""
    # Check if this is a navigation back scenario by looking for specific parameters
    # This is a simplified check - could be enhanced based on specific needs
    return hasattr(htmx, 'current_url') and '/item/' in str(getattr(htmx, 'current_url', ''))

def unified_page_layout(data):
    """Single responsive layout - no duplication"""
    feed_name = data.feed_name if hasattr(data, 'feed_name') else "All Feeds"

    return (
        # Single responsive layout
        Div(id=ElementIDs.APP_CONTAINER, cls="app-container")(
            # Sidebar (shared, responsive positioning)
            responsive_sidebar(data.session_id),
            # Sidebar overlay for mobile
            Div(id="sidebar-overlay", hx_on_click="window.toggleSidebar()"),
            # Main layout area
            Div(id="main-layout", cls="main-layout")(
                # Unified chrome
                UnifiedChrome(
                    session_id=data.session_id,
                    feed_id=data.feed_id,
                    unread_view=data.unread,
                    feed_name=feed_name,
                    show_back=False
                ),
                # Content area with feed list and article detail
                Div(id=ElementIDs.CONTENT_AREA, cls="content-area")(
                    # Feed list (middle panel)
                    Div(id=ElementIDs.FEED_LIST, cls="feed-list")(
                        FeedsContent(data.session_id, data.feed_id, data.unread,
                                   data.page, data=data)
                    ),
                    # Article detail (right panel/overlay)
                    Div(id=ElementIDs.ARTICLE_DETAIL, cls="article-detail")(
                        ItemDetailView(None)  # Empty on initial load
                    )
                )
            )
        )
        # Styles and scripts now loaded from static files
    )

def responsive_sidebar(session_id):
    """Create responsive sidebar that works for both mobile and desktop"""
    feeds = FeedModel.get_user_feeds(session_id)
    folders = FolderModel.get_folders(session_id)

    return Div(id=ElementIDs.SIDEBAR, cls="sidebar")(
        Ul(
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
                            name="new_feed_url",
                            cls="flex-1 mr-2 add-feed-input"
                        ),
                        Button(
                            UkIcon('plus'),
                            cls="px-2 add-feed-button",
                            type="submit"
                        )
                    ),
                    hx_post="/api/feed/add",
                    hx_target=f"#{ElementIDs.SIDEBAR}",
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
                    cls="hover:bg-secondary p-4 block",
                    hx_on_click="if(window.innerWidth < 1024) window.toggleSidebar()"
                )
            ),
            Div(cls="feeds-list")(*[
                Li(
                    A(
                        DivLAligned(
                            UkIcon('rss', cls="flex-none"),
                            Span(feed['title']),
                            P(f"updated {human_time_diff(feed.get('last_updated'))}", cls="text-xs text-muted ml-auto"),
                            cls="gap-3"
                        ),
                        href=f"/?feed_id={feed['id']}",
                        cls="hover:bg-secondary p-4 block",
                        hx_on_click="if(window.innerWidth < 1024) window.toggleSidebar()"
                    )
                ) for feed in feeds
            ]),
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
    )

def responsive_styles():
    """Returns Link to external CSS file"""
    # CSS now served from static/css/main.css
    return Link(rel='stylesheet', href='/static/css/main.css', type='text/css')

def _old_responsive_styles():
    """DEPRECATED: CSS moved to static/css/main.css"""
    return Style("""
    /* Base layout */
    html, body {
        height: 100%;
        overflow: hidden;
        margin: 0;
        padding: 0;
    }

    .app-container {
        height: 100vh;
        width: 100vw;
        overflow: hidden;
    }

    /* Desktop layout - 3 columns */
    @media (min-width: 1024px) {
        .app-container {
            display: grid;
            grid-template-columns: 250px 1fr;
        }

        .main-layout {
            display: grid;
            grid-template-rows: auto 1fr;
            height: 100vh;
            overflow: hidden;
        }

        .content-area {
            display: grid;
            grid-template-columns: 2fr 2fr;
            gap: 0;
            overflow: hidden;
        }

        .sidebar {
            display: block !important;
            position: static !important;
            height: 100vh;
            overflow-y: auto;
            border-right: 1px solid var(--border);
            background-color: hsl(var(--background));
        }

        #sidebar-overlay {
            display: none !important;
        }

        .nav-button-responsive {
            display: none !important;
        }

        .feed-list {
            height: 100%;
            overflow-y: auto;
            padding: 1rem;
            border-right: 1px solid var(--border);
        }

        .article-detail {
            height: 100%;
            overflow-y: auto;
            padding: 1.5rem;
            display: block !important;
        }

        .chrome-container {
            border-bottom: 1px solid var(--border);
        }

        .feed-name-responsive {
            font-size: 1.125rem;
        }
    }

    /* Mobile layout - single column */
    @media (max-width: 1023px) {
        .app-container {
            display: flex;
            flex-direction: column;
            position: relative;
        }

        .main-layout {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .content-area {
            flex: 1;
            overflow: hidden;
            position: relative;
        }

        .sidebar {
            position: fixed;
            left: -100%;
            top: 0;
            bottom: 0;
            width: 80%;
            max-width: 320px;
            z-index: 60;
            transition: left 0.3s ease;
            overflow-y: auto;
            border-right: 1px solid var(--border);
            background-color: hsl(var(--background));
        }

        .sidebar.open {
            left: 0;
        }

        #sidebar-overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.5);
            z-index: 59;
        }

        #sidebar-overlay.show {
            display: block;
        }

        .nav-button-responsive {
            display: flex !important;
            align-items: center;
            justify-content: center;
            padding: 0.5rem;
            border-radius: 0.25rem;
            border: 1px solid var(--border);
            margin-right: 0.5rem;
        }

        .feed-list {
            height: 100%;
            overflow-y: auto;
            padding: 1rem;
        }

        .article-detail {
            position: fixed;
            top: 64px;  /* Below chrome container */
            left: 0;
            right: 0;
            bottom: 0;
            z-index: 50;
            overflow-y: auto;
            padding: 1rem;
            display: none;
        }

        .article-detail.active {
            display: block;
        }

        .feed-list.article-view {
            display: none;
        }

        .chrome-container {
            position: sticky;
            top: 0;
            z-index: 40;
            border-bottom: 1px solid var(--border);
        }

        .feed-name-responsive {
            font-size: 1rem;
            font-weight: 600;
            margin-right: auto;
        }
    }

    /* Search bar responsive styles */
    .chrome-container {
        position: relative;
        height: 64px; /* Fixed height for invariant */
        overflow: hidden;
    }

    #search-bar {
        display: none;
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 64px; /* Match chrome height */
        z-index: 10;
    }

    #search-bar.show {
        display: flex !important;
    }

    #icon-bar.hide {
        display: none !important;
    }

    /* Icon bar is always visible - unified responsive element */
    #icon-bar {
        display: flex !important;
    }

    /* Feed item styles */
    .feed-item {
        cursor: pointer;
    }

    /* Text wrapping */
    .prose, .prose * {
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
        max-width: 100% !important;
    }

    /* Icon bar button styling - ensure 44px minimum height but compact width */
    /* Use more specific selector to override UIKit styles */
    #icon-bar .icon-bar-button {
        min-height: 44px !important;
        height: 44px !important;  /* Force exact height for touch targets */
        width: auto !important;
        padding: 10px 8px !important;  /* Reduced horizontal padding */
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-sizing: border-box !important;
        line-height: 1 !important;  /* Prevent line height from affecting button height */
    }
    """)

def responsive_javascript():
    """Returns Script link to external JavaScript file"""
    # JavaScript now served from static/js/main.js
    return Script(src='/static/js/main.js')

def _old_responsive_javascript():
    """DEPRECATED: JavaScript moved to static/js/main.js"""
    return Script("""
    // Sidebar toggle
    window.toggleSidebar = function() {
        const sidebar = document.getElementById('sidebar');
        const overlay = document.getElementById('sidebar-overlay');
        if (sidebar.classList.contains('open')) {
            sidebar.classList.remove('open');
            overlay.classList.remove('show');
        } else {
            sidebar.classList.add('open');
            overlay.classList.add('show');
        }
    };

    // Search toggle - improved with proper state management
    window.toggleSearch = function() {
        // Unified elements - single source of truth
        const searchBar = document.getElementById('search-bar');
        const iconBar = document.getElementById('icon-bar');
        const searchInput = document.getElementById('search-input');

        if (searchBar && searchBar.classList.contains('show')) {
            // Close search
            searchBar.classList.remove('show');
            if (iconBar) iconBar.classList.remove('hide');
        } else if (searchBar) {
            // Open search
            searchBar.classList.add('show');
            if (iconBar) iconBar.classList.add('hide');
            // Focus input after animation
            setTimeout(() => {
                if (searchInput) searchInput.focus();
            }, 50);
        }
    };

    // Article view management for mobile with race condition prevention
    window.articleTransitioning = false;
    window.currentArticleRequest = null;

    window.showArticle = function(itemId) {
        if (window.innerWidth < 1024) {
            // Prevent race conditions - abort any pending transition
            if (window.articleTransitioning) {
                console.log('Article transition already in progress, blocking new request');
                return;
            }
            window.articleTransitioning = true;

            const articleDetail = document.getElementById('article-detail');
            const feedList = document.getElementById('feed-list');
            const navButton = document.getElementById('nav-button');

            if (articleDetail) {
                articleDetail.classList.add('active');
            }
            if (feedList) {
                feedList.classList.add('article-view');
            }

            // Update nav button to back
            if (navButton) {
                navButton.dataset.mode = 'back';
                const arrowIcon = document.createElement('div');
                arrowIcon.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15,18 9,12 15,6"></polyline></svg>';
                navButton.innerHTML = '';
                navButton.appendChild(arrowIcon.firstChild);
                navButton.setAttribute('hx-get', navButton.dataset.returnUrl || '/');
                navButton.setAttribute('hx-target', '#feed-list');
                navButton.removeAttribute('onclick');
            }

            // Release lock after transition completes
            setTimeout(() => {
                window.articleTransitioning = false;
            }, 300);
        }
    };

    window.hideArticle = function() {
        if (window.innerWidth < 1024) {
            // Prevent race conditions during hide
            window.articleTransitioning = true;
            const articleDetail = document.getElementById('article-detail');
            const feedList = document.getElementById('feed-list');
            const navButton = document.getElementById('nav-button');

            articleDetail.classList.remove('active');
            feedList.classList.remove('article-view');

            // Update nav button to menu
            if (navButton) {
                navButton.dataset.mode = 'menu';
                const menuIcon = document.createElement('div');
                menuIcon.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>';
                navButton.innerHTML = '';
                navButton.appendChild(menuIcon.firstChild);
                navButton.removeAttribute('hx-get');
                navButton.removeAttribute('hx-target');
                navButton.setAttribute('onclick', 'toggleSidebar()');
            }

            // Release lock after transition completes
            setTimeout(() => {
                window.articleTransitioning = false;
            }, 300);
        }
    };

    // Legacy HTMX handlers removed - now handled by global htmx.on handlers

    // Click outside to close search - improved robustness
    document.addEventListener('click', function(event) {
        // Unified elements - single source of truth
        const searchBar = document.getElementById('search-bar');
        const iconBar = document.getElementById('icon-bar');

        if (searchBar && searchBar.classList.contains('show')) {
            const clickedInsideSearch = searchBar.contains(event.target);
            const clickedSearchButton = event.target.closest('button[title="Search"]');
            const clickedCloseButton = event.target.closest('button[title="Close search"]');

            // Don't close if clicked on search elements
            if (!clickedInsideSearch && !clickedSearchButton && !clickedCloseButton) {
                searchBar.classList.remove('show');
                if (iconBar) iconBar.classList.remove('hide');
            }
        }
    });

    // Escape key to close search
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            // Unified elements - single source of truth
            const searchBar = document.getElementById('search-bar');
            const iconBar = document.getElementById('icon-bar');

            if (searchBar && searchBar.classList.contains('show')) {
                searchBar.classList.remove('show');
                if (iconBar) iconBar.classList.remove('hide');
            }
        }
    });
    """)

def viewport_styles():
    """Viewport styles are now in main.css"""
    # Styles consolidated into static/css/main.css
    return Div()  # Return empty div instead of styles

def _old_viewport_styles():
    """DEPRECATED: Styles moved to static/css/main.css"""
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
        
        /* Ensure all clickable elements meet 44px minimum size */
        button, a, [role="button"], input[type="submit"], input[type="button"] {
            min-height: 44px !important;
            min-width: 44px !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
        }
        
        /* Override for tab buttons to keep them compact but accessible */
        .uk-tab-alt {
            max-width: 10rem !important; /* 160px - preserve max-w-40 constraint */
        }

        .uk-tab-alt a {
            min-height: 44px !important;  /* WCAG touch target minimum */
            min-width: auto !important;
            height: auto !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            max-width: 5rem !important; /* 80px per button - keep mobile compact */
        }
    }
    
    /* URL replacement styling */
    .url-replacement {
        flex-wrap: wrap !important;
        max-width: 100% !important;
    }
    
    /* First item top spacing without affecting tabs */
    .js-filter > li:first-child {
        margin-top: 1rem !important;
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
                'hx_target': Targets.CONTENT,
                'hx_push_url': "true"} if for_mobile else {}),
             role='button'),
           cls='uk-active' if not unread_only else ''),
        Li(A("Unread",
             href=base_url if base_url != "/" else "/",
             # Mobile-only: HTMX attributes for partial updates
             **({'hx_get': base_url if base_url != "/" else "/",
                'hx_target': Targets.CONTENT,
                'hx_push_url': "true"} if for_mobile else {}),
             role='button'),
           cls='uk-active' if unread_only else ''),
        alt=True, cls='ml-auto max-w-40'
    )

def prepare_item_data(session_id, item_id, feed_id, unread_view, page=1):
    """Centralized item data preparation"""
    class ItemData:
        def __init__(self):
            self.item = FeedItemModel.get_item_for_user(session_id, item_id)
            self.was_unread = not self.item.get('is_read', 0) if self.item else False
            self.feed_id = feed_id
            self.unread_view = unread_view
            self.session_id = session_id
            self.item_id = item_id
            self.page = page
        
        def mark_read_and_refresh(self):
            """Mark item as read and refresh data"""
            if self.item:
                self.item = UserItemModel.mark_read_and_get_item(self.session_id, self.item_id, True)
    
    return ItemData()

def htmx_item_response(htmx, item_data, _scroll=None):
    """HTMX item response using routing patterns"""
    responses = [ItemDetailView(item_data.item, show_back=False)]
    
    # MOBILE UPDATES - Full article view setup (body class now handled in ItemDetailView)
    if htmx.target in ['main-content', '#main-content']:
        # Update nav button to show chevron for article view
        back_url = "/"
        if item_data.feed_id:
            back_url = f"/?feed_id={item_data.feed_id}"
        
        # Add unread parameter based on the view we came from
        if item_data.unread_view is False:  # We came from "All Posts" view
            back_url += "&unread=0" if item_data.feed_id else "?unread=0"
        
        # Add page parameter if we came from a page other than 1
        if item_data.page > 1:
            back_url += f"&page={item_data.page}" if '?' in back_url else f"?page={item_data.page}"
        
        # Preserve scroll position if provided
        if _scroll:
            back_url += f"&_scroll={_scroll}" if '?' in back_url else f"?_scroll={_scroll}"
        
        back_button_attrs = {
            "id": ElementIDs.NAV_BUTTON,
            "class": "uk-btn nav-button-responsive",
            "hx-get": back_url,
            "hx-target": Targets.CONTENT,
            "hx-push-url": "true",
            "hx-swap-oob": "outerHTML",
            "data-mode": "back",
            "type": "button"
        }
        back_button = Button(
            UkIcon('arrow-left'),
            **back_button_attrs
        )
        responses.append(back_button)
    
    # Update list item appearance if it was unread (works for both mobile and desktop)
    if htmx.target in ['article-detail', '#article-detail', ElementIDs.ARTICLE_DETAIL, f'#{ElementIDs.ARTICLE_DETAIL}'] and item_data.was_unread:
        # Create updated feed item without blue dot (item is now marked as read)
        # Build the same way as FeedItem but with OOB swap
        item = item_data.item
        item_id = f"feed-item-{item['id']}"
        item_url = f"/item/{item['id']}?unread_view={item_data.unread_view}"
        if item_data.feed_id:
            item_url += f"&feed_id={item_data.feed_id}"
        if item_data.page > 1:
            item_url += f"&page={item_data.page}"

        # Item is now read, so no blue dot and different styling
        updated_item = Li(
            # Title row without blue dot (item is read)
            DivFullySpaced(
                Span(item['title']),  # Regular text for read items
                ''  # No blue dot for read items
            ),
            # Source and time row
            DivFullySpaced(
                Small(item.get('feed_title', 'Unknown Feed'), cls=TextPresets.muted_sm),
                Time(human_time_diff(item.get('published')), cls='text-xs text-muted-foreground')
            ),
            cls=f"{Styling.FEED_ITEM_BASE} {Styling.FEED_ITEM_READ} feed-item",
            id=item_id,
            hx_get=item_url,
            hx_target=f"#{ElementIDs.ARTICLE_DETAIL}",
            hx_trigger="click",
            hx_push_url="true",
            hx_vals='js:{_scroll: window.innerWidth < 1024 ? (document.getElementById("feed-list")?.scrollTop || 0) : 0}',
            hx_swap_oob="outerHTML"  # Replace the existing item in the feed list
        )
        responses.append(updated_item)
    
    return responses[0] if len(responses) == 1 else tuple(responses)

def full_page_item_response(item_data):
    """Full page response for item with unified responsive layout"""
    # Create PageData for consistency
    page_data = PageData(item_data.session_id, item_data.feed_id, item_data.unread_view, item_data.page)
    feed_name = page_data.feed_name if hasattr(page_data, 'feed_name') else "All Feeds"

    # For mobile, show back button in chrome
    show_back = True

    return (
        # Single responsive layout
        Div(id=ElementIDs.APP_CONTAINER, cls="app-container")(
            # Sidebar (shared, responsive positioning)
            responsive_sidebar(item_data.session_id),
            # Sidebar overlay for mobile
            Div(id="sidebar-overlay", hx_on_click="window.toggleSidebar()"),
            # Main layout area
            Div(id="main-layout", cls="main-layout")(
                # Unified chrome with back button for mobile
                UnifiedChrome(
                    session_id=item_data.session_id,
                    feed_id=item_data.feed_id,
                    unread_view=item_data.unread_view,
                    feed_name=feed_name,
                    show_back=show_back
                ),
                # Content area with feed list and article detail
                Div(id=ElementIDs.CONTENT_AREA, cls="content-area")(
                    # Feed list (hidden on mobile when viewing article)
                    Div(id=ElementIDs.FEED_LIST, cls="feed-list")(
                        FeedsContent(page_data.session_id, page_data.feed_id, page_data.unread,
                                   page_data.page, data=page_data)
                    ),
                    # Article detail (active on mobile)
                    Div(id=ElementIDs.ARTICLE_DETAIL, cls="article-detail active")(
                        ItemDetailView(item_data.item, show_back=False)
                    )
                )
            )
        ),
        # Styles and scripts now loaded from static files
        # Add script to activate article view on mobile
        Script("""
            document.addEventListener('DOMContentLoaded', function() {
                if (window.innerWidth < 1024) {
                    window.showArticle();
                }
            });
        """)
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
    hdrs=Theme.blue.headers() + [
        Link(rel='stylesheet', href='/static/css/main.css', type='text/css'),
        Script(src='/static/js/htmx-config.js'),
        Script(src='/static/js/main.js'),
        # All JavaScript now loaded from external files
        # HTMX event handlers moved to /static/js/htmx-config.js
        # Additional inline CSS for HTMX and mobile-specific styles
        # (Most styles moved to /static/css/main.css, keeping only critical inline styles)
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

# Static file serving route
@rt("/static/{fname:path}")
async def static(fname: str):
    """Serve static files from the static directory"""
    from starlette.responses import FileResponse
    import os
    file_path = os.path.join("static", fname)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return Response("Not found", status_code=404)

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
            cls=Styling.SIDEBAR_ITEM,
            hx_on_click="if(window.innerWidth < 1024) window.toggleSidebar()"
        )
    )

# Removed duplicate FeedsSidebar - use responsive_sidebar instead

def FeedItem(item, unread_view=False, feed_id=None, page=1):
    """Unified feed item component - responsive behavior via CSS

    Single element that adapts to mobile/desktop via CSS and JavaScript
    """
    cls_base = Styling.FEED_ITEM_BASE
    is_read = item.get('is_read', 0) == 1

    read_bg = Styling.FEED_ITEM_READ if is_read else Styling.FEED_ITEM_UNREAD
    cls = f"{cls_base} {read_bg} feed-item"

    # Build item URL with feed context preserved
    item_url = f"/item/{item['id']}?unread_view={unread_view}"
    if feed_id:
        item_url += f"&feed_id={feed_id}"
    if page > 1:
        item_url += f"&page={page}"

    # Single ID for each item
    item_id = f"feed-item-{item['id']}"

    # Always target article detail
    attrs = {
        "cls": cls,
        "id": item_id,
        "hx_get": item_url,
        "hx_target": f"#{ElementIDs.ARTICLE_DETAIL}",
        "hx_trigger": "click",
        "hx_push_url": "true",
        "hx_vals": 'js:{_scroll: window.innerWidth < 1024 ? (document.getElementById("feed-list")?.scrollTop || 0) : 0}'
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
    """Create unified list of feed items"""
    return Ul(cls='js-filter space-y-2 p-4 pt-0')(*[FeedItem(item, unread_view, feed_id, page) for item in items])

def MobilePersistentHeader(session_id, feed_id=None, unread_only=False, show_chrome=True):
    """Create persistent mobile header - simplified since icons moved to main header"""
    # New design: no persistent header chrome, all functionality moved to main header
    # Return empty/hidden element to maintain layout structure
    return Div(
        id='mobile-persistent-header',
        cls='hidden',
        style='display: none;'
    )()

def FeedsContent(session_id, feed_id=None, unread_only=False, page=1, data=None):
    """Create unified feeds content area with pagination

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
    
    print(f"🔍 FeedsContent() - unified content area")
    
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

        target = Targets.CONTENT  # Unified target

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
    
    # Unified layout - same simple content structure
    # Feed name now shown in chrome, not in content area
    content_elements = [
        FeedsList(paginated_items, unread_only, feed_id, page) if paginated_items else Div(P("No posts available"), cls='p-4 text-center text-muted-foreground'),
        pagination_footer()
    ]
    
    return Div(cls='p-0', id="feeds-list-container", uk_filter="target: .js-filter")(
        *content_elements
    )

# Removed duplicate MobileSidebar - use responsive_sidebar instead

def UnifiedChrome(session_id, feed_id=None, unread_view=True, feed_name="All Feeds", show_back=False):
    """Unified chrome component - single element for all viewports

    Args:
        session_id: User session ID
        feed_id: Current feed ID (optional)
        unread_view: Whether in unread view mode
        feed_name: Name of current feed
        show_back: Show back button instead of hamburger
    """
    # Build URLs for action buttons
    all_posts_url = f"/?feed_id={feed_id}&unread=0" if feed_id else "/?unread=0"
    unread_url = f"/?feed_id={feed_id}" if feed_id else "/"

    # Build return URL for back button
    return_url = "/"
    if feed_id:
        if unread_view:
            return_url = f"/?feed_id={feed_id}"
        else:
            return_url = f"/?feed_id={feed_id}&unread=0"
    else:
        if not unread_view:
            return_url = "/?unread=0"

    # Navigation button - visible only on mobile via CSS
    # Use explicit empty name to prevent automatic name attribute generation
    nav_button_attrs = {
        "id": ElementIDs.NAV_BUTTON,
        "class": "uk-btn nav-button-responsive",
        "data-mode": "back" if show_back else "menu",
        "type": "button",
        "name": ""  # Prevent FastHTML from auto-generating name attribute
    }

    if show_back:
        nav_button_attrs.update({
            "hx-get": return_url,
            "hx-target": Targets.CONTENT,
            "hx-push-url": "true"
        })
    else:
        nav_button_attrs["onclick"] = "toggleSidebar()"

    nav_button = Button(
        UkIcon('arrow-left' if show_back else 'menu'),
        **nav_button_attrs
    )

    # Feed name
    feed_name_element = H3(feed_name, cls="feed-name-responsive flex-1 text-center", id="feed-name")

    # Action buttons (with compact spacing and proper touch targets)
    action_buttons = Div(
        cls="flex items-center space-x-2 sm:space-x-3",
        id=ElementIDs.ICON_BAR
    )(
        Button(
            UkIcon('list'),
            hx_get=all_posts_url,
            hx_target=Targets.CONTENT,
            hx_push_url="true",
            cls="icon-bar-button rounded hover:bg-secondary",
            style="height: 44px; min-height: 44px; display: inline-flex; align-items: center; justify-content: center; padding: 10px 8px;",
            title="All Posts"
        ),
        Button(
            UkIcon('mail'),
            hx_get=unread_url,
            hx_target=Targets.CONTENT,
            hx_push_url="true",
            cls="icon-bar-button rounded hover:bg-secondary",
            style="height: 44px; min-height: 44px; display: inline-flex; align-items: center; justify-content: center; padding: 10px 8px;",
            title="Unread"
        ),
        Button(
            UkIcon('search'),
            onclick="window.toggleSearch()",
            cls="icon-bar-button rounded hover:bg-secondary",
            style="height: 44px; min-height: 44px; display: inline-flex; align-items: center; justify-content: center; padding: 10px 8px;",
            title="Search"
        )
    )

    # Expandable search bar - positioned absolutely to not affect height
    search_bar = Div(
        cls="absolute inset-0 flex items-center px-4 bg-white z-10",
        id=ElementIDs.SEARCH_BAR,
        style="display: none;"
    )(
        # Create separate nav button for main search bar to avoid duplicate IDs
        Button(
            UkIcon('menu'),
            **{
                "type": "button",
                "onclick": "toggleSidebar()",
                "class": "uk-btn nav-button-responsive",
                "id": "search-nav-button",
                "data-mode": "menu",
                "name": ""  # Prevent FastHTML from auto-generating name attribute
            }
        ),
        Div(cls="flex-1 mx-4")(
            Div(cls="uk-inline w-full")(
                Input(
                    placeholder="Search posts",
                    cls="w-full pr-10",
                    id="search-input",
                    uk_filter_control=""
                ),
                Button(
                    UkIcon('x', cls="w-4 h-4"),
                    onclick="window.toggleSearch()",
                    cls="uk-form-icon uk-form-icon-flip p-1 hover:text-red-500 cursor-pointer absolute right-2 top-1/2 -translate-y-1/2",
                    title="Close search"
                )
            )
        )
    )

    # Chrome container structure - fixed height to maintain invariant
    # UNIFIED responsive structure - NO test-specific duplicate elements
    # Standard padding for proper UX - px-4 gives 1rem on each side
    chrome_content = Div(
        cls="chrome-container flex items-center justify-between border-b min-h-[64px] max-h-[64px] px-4",
        id=ElementIDs.CHROME_CONTAINER,
        hx_preserve="true"  # Preserve chrome during HTMX swaps (mobile article view)
    )(
        nav_button,
        feed_name_element,
        # Single unified icon bar - responsive via CSS
        Div(
            cls="flex items-center",
            id="icon-bar"
        )(
            Button(
                UkIcon('list'),
                hx_get=all_posts_url,
                hx_target=Targets.CONTENT,
                hx_push_url="true",
                cls="icon-bar-button rounded hover:bg-secondary",
                style="height: 44px; min-height: 44px; display: inline-flex; align-items: center; justify-content: center; padding: 10px 8px;",
                title="All Posts"
            ),
            Button(
                UkIcon('mail'),
                hx_get=unread_url,
                hx_target=Targets.CONTENT,
                hx_push_url="true",
                cls="icon-bar-button rounded hover:bg-secondary",
                style="height: 44px; min-height: 44px; display: inline-flex; align-items: center; justify-content: center; padding: 10px 8px;",
                title="Unread"
            ),
            Button(
                UkIcon('search'),
                onclick="window.toggleSearch()",
                cls="icon-bar-button rounded hover:bg-secondary",
                style="height: 44px; min-height: 44px; display: inline-flex; align-items: center; justify-content: center; padding: 10px 8px;",
                title="Search"
            )
        )
    )

    # Include search bars in the chrome structure - NO container padding for edge alignment
    chrome_with_search = Div(
        cls="relative",  # Remove container padding, keep relative for search bar
        style="padding: 0; margin: 0;"  # Force no padding/margin for edge buttons
    )(
        chrome_content,
        search_bar  # Include the main search bar defined above
    )

    return chrome_with_search

# Removed MobileHeader - now using unified UnifiedChrome directly

def ItemDetailView(item, show_back=False):
    """Create item detail view - back button now handled by header"""
    if not item:
        return Container(
            P("Select a post to read", cls='text-center text-muted-foreground p-8')
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
                    hx_target=Targets.DETAIL,
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
        )
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
    
    # FULL PAGE - Single responsive layout
    return unified_page_layout(data)

@rt('/item/{item_id}')
def show_item(item_id: int, htmx, sess, unread_view: bool = False, feed_id: int = None, page: int = 1, _scroll: int = None):
    """Item detail route following same pattern"""
    session_id = sess.get('session_id')
    
    # Prepare item data
    item_data = prepare_item_data(session_id, item_id, feed_id, unread_view, page)
    
    if not item_data.item:
        if htmx and getattr(htmx, 'request', None) and getattr(htmx, 'target', None):
            import traceback
            import json
            import sqlite3
            
            # Execute the same query to get diagnostic results
            diagnostic_result = None
            try:
                with get_db() as conn:
                    diagnostic_result = conn.execute("""
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
                diagnostic_result = f"Query failed: {str(e)}"
            
            return Div(
                H2("Item Not Found - Diagnostic Information", cls='text-red-600 font-bold mb-4'),
                
                Details(
                    Summary("SQL Query Details"),
                    Pre(f"""Query: get_item_for_user(session_id='{session_id}', item_id={item_id})

Executed SQL:
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

Parameters: ('{session_id}', '{session_id}', {item_id})"""),
                    Pre(f"Result: {json.dumps(dict(diagnostic_result) if diagnostic_result and isinstance(diagnostic_result, sqlite3.Row) else diagnostic_result, indent=2, default=str)}")
                ),
                
                Details(
                    Summary("Request Context"),
                    Pre(f"""Route: /item/{item_id}
Session ID: {session_id}
Feed ID: {feed_id}
Unread View: {unread_view}
HTMX Request: {bool(htmx)}
HTMX Target: {getattr(htmx, 'target', None) if htmx else None}""")
                ),
                
                Details(
                    Summary("Stack Trace"),
                    Pre(''.join(traceback.format_stack()))
                ),
                
                cls='border border-red-300 bg-red-50 p-4 m-4 rounded'
            )
        else:
            # Create empty PageData for not found case
            page_data = PageData(session_id, feed_id, True, page)
            return full_page_dual_layout(page_data)
    
    # Mark as read
    item_data.mark_read_and_refresh()
    
    # Route response
    if htmx and getattr(htmx, 'request', None) and getattr(htmx, 'target', None):
        return htmx_item_response(htmx, item_data, _scroll)
    else:
        return full_page_item_response(item_data)

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
        
        # Return unified sidebar response
        return responsive_sidebar(session_id)
        
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
                FeedsSidebar(session_id, for_mobile=False)
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
        FeedsSidebar(session_id, for_mobile=False)
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