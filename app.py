"""RSS Reader built with FastHTML and MonsterUI"""

from fasthtml.common import *
from monsterui.all import *
import uuid
from datetime import datetime, timezone
import os
import time
from models import (
    SessionModel, FeedModel, FeedItemModel, UserItemModel, FolderModel,
    init_db, get_db
)
from feed_parser import FeedParser, setup_default_feeds
from dateutil.relativedelta import relativedelta

# Initialize database and setup default feeds if needed
init_db()

# Check if we need to add default feeds (first run)
if not FeedModel.get_feeds_to_update(max_age_minutes=9999):
    print("Setting up default feeds...")
    setup_default_feeds()

# Timing middleware for performance monitoring
def timing_middleware(req, sess):
    """Add timing info to requests"""
    req.scope['start_time'] = time.time()

def after_middleware(req, response):
    """Log request timing"""
    if 'start_time' in req.scope:
        duration = (time.time() - req.scope['start_time']) * 1000  # Convert to ms
        path = req.scope.get('path', 'unknown')
        method = req.scope.get('method', 'unknown')
        print(f"TIMING: {method} {path} - {duration:.2f}ms")
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

# FastHTML app with session support and beforeware
app, rt = fast_app(
    hdrs=Theme.blue.headers() + [
        Script("""
        htmx.logAll();
        htmx.config.includeIndicatorStyles = false;
        """)
    ],
    live=True,
    debug=True,
    before=[timing_middleware, before],
    after=after_middleware
)

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
    
    return Li(
        A(
            DivLAligned(
                Span(UkIcon('rss')),
                Span(feed['title'] or 'Untitled Feed'),
                P(f"updated {last_updated}", cls=TextPresets.muted_sm)
            ),
            href=f"/?feed_id={feed['id']}",
            hx_get=f"/?feed_id={feed['id']}",
            hx_target="#main-content",
            hx_push_url="true",
            cls='hover:bg-secondary p-4'
        )
    )

def FeedsSidebar(session_id):
    """Create feeds sidebar (adapted from mail sidebar)"""
    feeds = FeedModel.get_user_feeds(session_id)
    folders = FolderModel.get_folders(session_id)
    
    return NavContainer(
        NavHeaderLi(H3("Feeds"), cls='p-3'),
        Li(
            DivLAligned(
                Input(
                    placeholder="Enter RSS URL", 
                    id="new-feed-url",
                    name="new_feed_url",  # This maps to FastHTML function parameter
                    cls="flex-1 mr-2"
                ),
                Button(
                    UkIcon('plus'),
                    hx_post="/api/feed/add",
                    hx_include="#new-feed-url",
                    hx_target="#feeds-list",
                    hx_swap="beforeend",
                    cls="px-2"
                )
            ),
            cls='p-4'
        ),
        Li(
            A(
                DivLAligned(
                    Span(UkIcon('globe')),
                    Span("All Feeds"),
                    P("", cls=TextPresets.muted_sm)
                ),
                href="/",
                hx_get="/",
                hx_target="#main-content",
                hx_push_url="true",
                cls='hover:bg-secondary p-4'
            )
        ),
        Div(id="feeds-list")(*[FeedSidebarItem(feed) for feed in feeds]),
        Li(Hr()),
        NavHeaderLi(H4("Folders"), cls='p-3'),
        *[Li(A(DivLAligned(Span(UkIcon('folder')), Span(folder['name'])), 
               href=f"/?folder_id={folder['id']}",
               hx_get=f"/?folder_id={folder['id']}",
               hx_target="#main-content",
               hx_push_url="true",
               cls='hover:bg-secondary p-4')) 
          for folder in folders],
        Li(
            Button(
                UkIcon('plus'),
                " Add Folder",
                hx_post="/api/folder/add",
                hx_prompt="Folder name:",
                hx_target="#sidebar",
                cls="w-full text-left p-4 hover:bg-secondary"
            )
        ),
        cls='mt-3'
    )

def FeedItem(item, unread_view=False, for_desktop=False):
    """Create feed item with consistent HTMX approach"""
    cls_base = 'relative rounded-lg border border-border p-3 text-sm hover:bg-secondary space-y-2 cursor-pointer'
    is_read = item.get('is_read', 0) == 1
    
    read_bg = 'bg-muted' if is_read else ''
    cls = f"{cls_base} {read_bg} tag-{'unread' if not is_read else 'read'}"
    
    # Simple consistent approach: same HTMX pattern, just different targets
    if for_desktop:
        target = "#desktop-item-detail"
        push_url = None  # No URL push for desktop detail panel
    else:
        target = "#main-content" 
        push_url = "true"  # URL push for mobile full-page navigation
    
    attrs = {
        "cls": cls,
        "id": f"feed-item-{item['id']}",
        "hx_get": f"/item/{item['id']}?unread_view={unread_view}",
        "hx_target": target,
        "hx_trigger": "click"
    }
    
    if push_url:
        attrs["hx_push_url"] = push_url
    
    return Li(
        DivFullySpaced(
            DivLAligned(
                Strong(item['title']),
                Span(cls='flex h-2 w-2 rounded-full bg-blue-600') if not item.get('is_read', 0) else ''),
            DivLAligned(
                Small(item.get('feed_title', 'Unknown Feed'), cls=TextPresets.muted_sm),
                Time(human_time_diff(item.get('published')), cls='text-xs')
            )
        ),
        Div((item.get('description', '') or '')[:150] + '...', cls=TextPresets.muted_sm),
        DivLAligned(
            *([Label(A(item.get('folder_name', 'General'), href='#'), 
                    cls='uk-label-primary')] if item.get('folder_name') else [])
        ),
        **attrs
    )

def FeedsList(items, unread_view=False, for_desktop=False):
    """Create list of feed items (adapted from MailList)"""
    return Ul(cls='js-filter space-y-2 p-4 pt-0')(*[FeedItem(item, unread_view, for_desktop) for item in items])

def FeedsContent(session_id, feed_id=None, unread_only=False, page=1, for_desktop=False):
    """Create main feeds content area with pagination (adapted from MailContent)"""
    # Get all items first
    all_items = FeedItemModel.get_items_for_user(session_id, feed_id, unread_only)
    print(f"DEBUG: FeedsContent got {len(all_items)} items for session {session_id}")
    
    # Pagination logic (following MonsterUI tasks example)
    page_size = 20
    current_page = max(0, page - 1)  # Convert to 0-indexed
    total_pages = (len(all_items) + page_size - 1) // page_size if all_items else 1
    
    # Get items for current page
    start_idx = current_page * page_size
    end_idx = start_idx + page_size
    paginated_items = all_items[start_idx:end_idx]
    
    # Simple header logic
    if feed_id:
        feeds = FeedModel.get_user_feeds(session_id)
        feed = next((f for f in feeds if f['id'] == feed_id), None)
        feed_name = feed['title'] if feed else "Unknown Feed"
    else:
        feed_name = "All Feeds"  # Unconditionally for the all feeds case
    
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
                Div(f"Showing {len(paginated_items)} of {len(all_items)} posts", cls=TextPresets.muted_sm),
                DivLAligned(
                    DivCentered(f'Page {page} of {total_pages}', cls=TextT.sm),
                    DivLAligned(
                        # Mobile versions
                        Button(UkIcon('chevrons-left'), hx_get=first_url, hx_target="#main-content", hx_push_url="true", cls="p-2 rounded border hover:bg-secondary lg:hidden"),
                        Button(UkIcon('chevron-left'), hx_get=prev_url, hx_target="#main-content", hx_push_url="true", cls="p-2 rounded border hover:bg-secondary lg:hidden"),
                        Button(UkIcon('chevron-right'), hx_get=next_url, hx_target="#main-content", hx_push_url="true", cls="p-2 rounded border hover:bg-secondary lg:hidden"),
                        Button(UkIcon('chevrons-right'), hx_get=last_url, hx_target="#main-content", hx_push_url="true", cls="p-2 rounded border hover:bg-secondary lg:hidden"),
                        # Desktop versions - use HTMX for consistency
                        Button(UkIcon('chevrons-left'), hx_get=first_url, hx_target="#desktop-feeds-content" if for_desktop else "#main-content", cls="p-2 rounded border hover:bg-secondary hidden lg:inline-block"),
                        Button(UkIcon('chevron-left'), hx_get=prev_url, hx_target="#desktop-feeds-content" if for_desktop else "#main-content", cls="p-2 rounded border hover:bg-secondary hidden lg:inline-block"),
                        Button(UkIcon('chevron-right'), hx_get=next_url, hx_target="#desktop-feeds-content" if for_desktop else "#main-content", cls="p-2 rounded border hover:bg-secondary hidden lg:inline-block"),
                        Button(UkIcon('chevrons-right'), hx_get=last_url, hx_target="#desktop-feeds-content" if for_desktop else "#main-content", cls="p-2 rounded border hover:bg-secondary hidden lg:inline-block"),
                        cls='space-x-1'
                    )
                )
            )
        )
    
    return Div(cls='flex flex-col', uk_filter="target: .js-filter")(
        Div(cls='flex px-4 py-2')(
            H3(feed_name),
            TabContainer(
                Li(A("All Posts", href=f"{base_url}{'&' if url_params else '?'}unread=0" if base_url != "/" else "/?unread=0", role='button'),
                   cls='uk-active' if not unread_only else ''),
                Li(A("Unread", href=base_url if base_url != "/" else "/", role='button'),
                   cls='uk-active' if unread_only else ''),
                alt=True, cls='ml-auto max-w-40'
            )
        ),
        Div(cls='flex flex-1 flex-col')(
            Div(cls='p-4')(
                Div(cls='uk-inline w-full')(
                    Span(cls='uk-form-icon text-muted-foreground')(UkIcon('search')),
                    Input(placeholder='Search posts', uk_filter_control="")
                )
            ),
            Div(cls='flex-1 overflow-y-auto', id="feeds-list-container")(
                FeedsList(paginated_items, unread_only, for_desktop) if paginated_items else Div(P("No posts available"), cls='p-4 text-center text-muted-foreground')
            ),
            pagination_footer()
        )
    )

def MobileSidebar(session_id):
    """Create mobile sidebar overlay"""
    return Div(
        id="mobile-sidebar",
        cls="fixed inset-0 z-50 lg:hidden",
        hidden="true"
    )(
        Div(cls="bg-black bg-opacity-50 absolute inset-0", uk_toggle="target: #mobile-sidebar"),
        Div(cls="bg-background w-80 h-full overflow-y-auto relative z-10")(
            Div(cls="p-4 border-b")(
                DivFullySpaced(
                    H3("RSS Reader"),
                    Button(
                        UkIcon('x'),
                        cls="p-1 rounded hover:bg-secondary",
                        uk_toggle="target: #mobile-sidebar"
                    )
                )
            ),
            FeedsSidebar(session_id)
        )
    )

def MobileHeader(session_id, show_back=False):
    """Create mobile header with hamburger menu and optional back button"""
    
    # Loading spinner
    loading_spinner = Div(
        id="loading-spinner",
        cls="fixed top-20 left-1/2 transform -translate-x-1/2 bg-background border rounded p-3 z-50 lg:hidden htmx-indicator"
    )(
        DivLAligned(
            UkIcon('loader', cls="animate-spin"),
            Span("Loading...", cls="ml-2")
        )
    )
    
    return Div(
        # Fixed header bar
        Div(cls="lg:hidden fixed top-0 left-0 right-0 bg-background border-b p-4 z-40")(
            DivFullySpaced(
                DivLAligned(
                    Button(
                        UkIcon('arrow-left'),
                        hx_get="/",
                        hx_target="#main-content", 
                        hx_push_url="true",
                        cls="p-2 rounded border hover:bg-secondary mr-2"
                    ) if show_back else "",
                    Button(
                        UkIcon('menu'),
                        cls="p-2 rounded border hover:bg-secondary",
                        uk_toggle="target: #mobile-sidebar"
                    ),
                    H3("RSS Reader", cls="ml-3")
                )
            )
        ),
        loading_spinner
    )

def ItemDetailView(item, show_back=False):
    """Create item detail view with optional back button for mobile"""
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
    
    # Mobile back button (will be handled by mobile header)
    back_button = "" if show_back else ""
    
    return Container(
        back_button,
        DivFullySpaced(
            DivLAligned(
                *[UkIcon(
                    icon, 
                    uk_tooltip=tooltip,
                    hx_post=f"/api/item/{item['id']}/{'star' if 'star' in tooltip.lower() else 'folder' if 'folder' in tooltip.lower() else 'read'}",
                    hx_target="#main-content",
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
            NotStr(item.get('content') or item.get('description', 'No content available')),
            cls=TextT.sm + 'p-4 prose max-w-none'
        ),
        id="item-detail"
    )

@rt('/')
def index(request, feed_id: int = None, unread: bool = True, folder_id: int = None, page: int = 1):
    """Main page with mobile-first responsive design"""
    session_id = request.scope['session_id']
    print(f"DEBUG: Main page for session: {session_id}")
    
    # Check what feeds this session has
    user_feeds = FeedModel.get_user_feeds(session_id)
    print(f"DEBUG: User has {len(user_feeds)} feeds")
    
    # Check what items are available  
    items = FeedItemModel.get_items_for_user(session_id, feed_id, unread)
    print(f"DEBUG: Found {len(items)} items for user, page {page}")
    
    # Update feeds that need refreshing (older than 1 minute)
    parser = FeedParser()
    parser.update_all_feeds(max_age_minutes=1)
    
    # This is now handled by MobileHeader function
    
    # Check if this is an HTMX request for mobile content updates
    is_htmx = request.headers.get('HX-Request') == 'true'
    
    if is_htmx:
        # Return only the feeds content for HTMX requests
        return FeedsContent(session_id, feed_id, unread, page)
    
    return Title("RSS Reader"), Container(
        Div(id="mobile-header")(MobileHeader(session_id, show_back=False)),
        MobileSidebar(session_id),
        # Desktop layout: sidebar + feeds + article detail
        Div(cls="hidden lg:grid", id="desktop-layout")(
            Grid(
                Div(id="sidebar")(FeedsSidebar(session_id), cls='col-span-1 h-screen'),
                Div(cls='col-span-2 h-screen flex flex-col', id="desktop-feeds-content")(
                    Div(cls='flex-1 overflow-y-auto')(FeedsContent(session_id, feed_id, unread, page, for_desktop=True))
                ),
                Div(id="desktop-item-detail")(ItemDetailView(None), cls='col-span-2 h-screen'),
                cols_lg=5, cols_xl=5,
                gap=0, cls='h-screen'
            )
        ),
        # Mobile layout: just feeds content (articles list) with top padding for fixed header
        Div(cls="lg:hidden pt-20", id="main-content")(
            FeedsContent(session_id, feed_id, unread, page)
        ),
        cls=('min-h-screen', ContainerT.xl)
    )

@rt('/item/{item_id}')
def show_item(item_id: int, request, unread_view: bool = False):
    """Get item detail and mark as read with mobile-responsive UI updates"""
    session_id = request.scope['session_id']
    
    # Get item before marking as read to check original status
    items_before = FeedItemModel.get_items_for_user(session_id)
    item_before = next((i for i in items_before if i['id'] == item_id), None)
    
    if not item_before:
        return ItemDetailView(None, show_back=True)
    
    was_unread = not item_before.get('is_read', 0)
    
    # Mark item as read
    UserItemModel.mark_read(session_id, item_id, True)
    
    # Get updated item details
    items_after = FeedItemModel.get_items_for_user(session_id)
    item_after = next((i for i in items_after if i['id'] == item_id), None)
    
    # Check the target to determine mobile vs desktop  
    hx_target = request.headers.get('HX-Target', '')
    is_mobile_request = hx_target in ['#main-content', 'main-content']
    is_desktop_request = hx_target in ['#desktop-item-detail', 'desktop-item-detail']
    
    
    responses = []
    
    # Main response: Item detail view
    detail_view = ItemDetailView(item_after, show_back=is_mobile_request)
    responses.append(detail_view)
    
    # Update list item appearance if it was unread
    if was_unread and item_after:
        if is_mobile_request:
            # Mobile: update header to show back button
            mobile_header_with_back = Div(
                cls="lg:hidden fixed top-0 left-0 right-0 bg-background border-b p-4 z-40",
                hx_swap_oob="true",
                id="mobile-header"
            )(
                DivFullySpaced(
                    DivLAligned(
                        Button(
                            UkIcon('arrow-left'),
                            hx_get="/",
                            hx_target="#main-content", 
                            hx_push_url="true",
                            cls="p-2 rounded border hover:bg-secondary mr-2"
                        ),
                        Button(
                            UkIcon('menu'),
                            cls="p-2 rounded border hover:bg-secondary",
                            uk_toggle="target: #mobile-sidebar"
                        ),
                        H3("RSS Reader", cls="ml-3")
                    )
                )
            )
            responses.append(mobile_header_with_back)
        elif is_desktop_request:
            # Desktop: update the list item appearance with correct attributes
            updated_item_attrs = {
                "cls": f"relative rounded-lg border border-border p-3 text-sm hover:bg-secondary space-y-2 cursor-pointer bg-muted tag-read",
                "id": f"feed-item-{item_id}",
                "hx_get": f"/item/{item_after['id']}?unread_view={unread_view}",
                "hx_target": "#desktop-item-detail",
                "hx_trigger": "click",
                "hx_swap_oob": "true"
            }
            
            updated_item = Li(
                DivFullySpaced(
                    DivLAligned(
                        Strong(item_after['title']),
                        # No blue dot for read items
                    ),
                    DivLAligned(
                        Small(item_after.get('feed_title', 'Unknown Feed'), cls=TextPresets.muted_sm),
                        Time(human_time_diff(item_after.get('published')), cls='text-xs')
                    )
                ),
                Div((item_after.get('description', '') or '')[:150] + '...', cls=TextPresets.muted_sm),
                **updated_item_attrs
            )
            responses.append(updated_item)
    
    return tuple(responses) if len(responses) > 1 else detail_view

@rt('/api/feed/add')
def add_feed(request, new_feed_url: str = ""):
    """Add new feed"""
    session_id = request.scope['session_id']
    url = new_feed_url.strip()
    print(f"DEBUG: add_feed called with URL='{url}'")
    
    if not url:
        return Div("Please enter a URL", cls='text-red-500 p-4')
    
    # Check if user is already subscribed to this feed
    user_feeds = FeedModel.get_user_feeds(session_id)
    existing_feed = next((f for f in user_feeds if f['url'] == url), None)
    
    if existing_feed:
        return Div(f"Already subscribed to: {existing_feed['title']}", 
                  cls='text-yellow-600 p-4')
    
    parser = FeedParser()
    result = parser.add_feed(url)
    
    if result['success']:
        # Subscribe user to the new feed
        try:
            SessionModel.subscribe_to_feed(session_id, result['feed_id'])
            
            # Get feed details and return updated sidebar
            feeds = FeedModel.get_user_feeds(session_id)
            feed = next((f for f in feeds if f['id'] == result['feed_id']), None)
            
            if feed:
                return FeedSidebarItem(feed)
        except Exception as e:
            # Log the actual error for debugging
            print(f"ERROR: Feed subscription failed for {url}: {str(e)}")
            return Div(f"Error subscribing to feed: {str(e)}", cls='text-red-500 p-4')
    
    return Div(f"Failed to add feed: {result.get('error', 'Unknown error')}", 
              cls='text-red-500 p-4')

@rt('/api/item/{item_id}/star')
def star_item(item_id: int, request):
    """Toggle star status"""
    session_id = request.scope['session_id']
    UserItemModel.toggle_star(session_id, item_id)
    
    # Return updated item detail with mobile support
    items = FeedItemModel.get_items_for_user(session_id)
    item = next((i for i in items if i['id'] == item_id), None)
    is_htmx = request.headers.get('HX-Request') == 'true'
    return ItemDetailView(item, show_back=is_htmx)

@rt('/api/item/{item_id}/read')
def toggle_read(item_id: int, request):
    """Toggle read status"""
    session_id = request.scope['session_id']
    
    # Get current status and toggle
    items = FeedItemModel.get_items_for_user(session_id)
    item = next((i for i in items if i['id'] == item_id), None)
    
    if item:
        is_read = not item.get('is_read', 0)
        UserItemModel.mark_read(session_id, item_id, is_read)
        
        # Return updated item detail with mobile support
        items = FeedItemModel.get_items_for_user(session_id)
        item = next((i for i in items if i['id'] == item_id), None)
        is_htmx = request.headers.get('HX-Request') == 'true'
        return ItemDetailView(item, show_back=is_htmx)
    
    return Div("Item not found", cls='text-red-500 p-4')

@rt('/api/folder/add')
def add_folder(request):
    """Add new folder"""
    session_id = request.scope['session_id']
    name = request.headers.get('hx-prompt', '').strip()
    
    if name:
        FolderModel.create_folder(session_id, name)
    
    # Return updated sidebar
    return FeedsSidebar(session_id)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    serve(port=port, host="0.0.0.0")