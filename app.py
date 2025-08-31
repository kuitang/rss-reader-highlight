"""RSS Reader built with FastHTML and MonsterUI"""

from fasthtml.common import *
from monsterui.all import *
import uuid
from datetime import datetime, timezone
import os
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
                except:
                    print(f"DEBUG: Already subscribed to feed {feed['id']}: {feed['title']}")
    
    # Store in request scope for easy access
    req.scope['session_id'] = session_id

bware = Beforeware(before)

# FastHTML app with session support and beforeware
app, rt = fast_app(
    hdrs=Theme.blue.headers(),
    live=True,
    debug=True,
    before=bware
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
                cls='hover:bg-secondary p-4'
            )
        ),
        Div(id="feeds-list")(*[FeedSidebarItem(feed) for feed in feeds]),
        Li(Hr()),
        NavHeaderLi(H4("Folders"), cls='p-3'),
        *[Li(A(DivLAligned(Span(UkIcon('folder')), Span(folder['name'])), 
               href=f"/?folder_id={folder['id']}", cls='hover:bg-secondary p-4')) 
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

def FeedItem(item, unread_view=False):
    """Create feed item (adapted from MailItem)"""
    cls_base = 'relative rounded-lg border border-border p-3 text-sm hover:bg-secondary space-y-2 cursor-pointer'
    cls = f"{cls_base} {'bg-muted' if item.get('is_read', 0) == 0 else ''} tag-{'unread' if not item.get('is_read', 0) else 'read'}"
    
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
        cls=cls,
        id=f"feed-item-{item['id']}",  # Unique ID for HTMX targeting
        hx_get=f"/item/{item['id']}?unread_view={unread_view}",  # Pass view context
        hx_target="#item-detail",
        hx_trigger="click"
    )

def FeedsList(items, unread_view=False):
    """Create list of feed items (adapted from MailList)"""
    return Ul(cls='js-filter space-y-2 p-4 pt-0')(*[FeedItem(item, unread_view) for item in items])

def FeedsContent(session_id, feed_id=None, unread_only=False, page=1):
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
    
    feed_name = "All Posts"
    if feed_id:
        feeds = FeedModel.get_user_feeds(session_id)
        feed = next((f for f in feeds if f['id'] == feed_id), None)
        feed_name = feed['title'] if feed else "Unknown Feed"
    
    # Build URL parameters for pagination
    url_params = []
    if feed_id:
        url_params.append(f"feed_id={feed_id}")
    if unread_only:
        url_params.append("unread=1")
    
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
                        UkIconLink(icon='chevrons-left', href=first_url, button=True, uk_tooltip="First page"),
                        UkIconLink(icon='chevron-left', href=prev_url, button=True, uk_tooltip="Previous page"),
                        UkIconLink(icon='chevron-right', href=next_url, button=True, uk_tooltip="Next page"),
                        UkIconLink(icon='chevrons-right', href=last_url, button=True, uk_tooltip="Last page"),
                        cls='space-x-1'
                    )
                )
            )
        )
    
    return Div(cls='flex flex-col', uk_filter="target: .js-filter")(
        Div(cls='flex px-4 py-2')(
            H3(feed_name),
            TabContainer(
                Li(A("All Posts", href=base_url, role='button'), 
                   cls='uk-active' if not unread_only else '', 
                   uk_filter_control="filter: .tag-read, .tag-unread"),
                Li(A("Unread", href=f"{base_url}{'&' if url_params else '?'}unread=1" if base_url != "/" else "/?unread=1", role='button'),
                   cls='uk-active' if unread_only else '',
                   uk_filter_control="filter: .tag-unread"),
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
                FeedsList(paginated_items, unread_only) if paginated_items else Div(P("No posts available"), cls='p-4 text-center text-muted-foreground')
            ),
            pagination_footer()
        )
    )

def ItemDetailView(item):
    """Create item detail view (adapted from MailDetailView)"""
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
    
    return Container(
        DivFullySpaced(
            DivLAligned(
                *[UkIcon(
                    icon, 
                    uk_tooltip=tooltip,
                    hx_post=f"/api/item/{item['id']}/{'star' if 'star' in tooltip.lower() else 'folder' if 'folder' in tooltip.lower() else 'read'}",
                    hx_target="#item-detail",
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
            # Show content if available, otherwise description
            NotStr(item.get('content') or item.get('description', 'No content available')),
            cls=TextT.sm + 'p-4 prose max-w-none'
        ),
        id="item-detail"
    )

@rt('/')
def index(request, feed_id: int = None, unread: bool = False, folder_id: int = None, page: int = 1):
    """Main page"""
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
    
    return Title("RSS Reader"), Container(
        Grid(
            Div(id="sidebar")(FeedsSidebar(session_id), cls='col-span-1 h-screen overflow-y-auto'),
            Div(FeedsContent(session_id, feed_id, unread, page), cls='col-span-2 h-screen'),
            Div(id="item-detail")(ItemDetailView(None), cls='col-span-2 h-screen overflow-y-auto'),
            cols_sm=1, cols_md=1, cols_lg=5, cols_xl=5,
            gap=0, cls='h-screen'
        ),
        cls=('min-h-screen', ContainerT.xl)
    )

@rt('/item/{item_id}')
def show_item(item_id: int, request, unread_view: bool = False):
    """Get item detail and mark as read with UI updates"""
    session_id = request.scope['session_id']
    
    # Get item before marking as read to check original status
    items_before = FeedItemModel.get_items_for_user(session_id)
    item_before = next((i for i in items_before if i['id'] == item_id), None)
    
    if not item_before:
        return ItemDetailView(None)
    
    was_unread = not item_before.get('is_read', 0)
    
    # Mark item as read
    UserItemModel.mark_read(session_id, item_id, True)
    
    # Get updated item details
    items_after = FeedItemModel.get_items_for_user(session_id)
    item_after = next((i for i in items_after if i['id'] == item_id), None)
    
    # Prepare response components
    responses = []
    
    # 1. Main response: Item detail view
    detail_view = ItemDetailView(item_after)
    responses.append(detail_view)
    
    # 2. Out-of-band swap: Update the list item appearance (remove blue indicator)
    if was_unread and item_after:
        if unread_view:
            # In unread view: remove the item entirely
            updated_item = Div(hx_swap_oob=f'outerHTML:#{f"feed-item-{item_id}"}')  # Empty div replaces item
            responses.append(updated_item)
        else:
            # In all posts view: update item to show as read (no blue indicator)
            updated_item = FeedItem(item_after, unread_view)
            updated_item = Li(
                *updated_item.children,  # Copy children
                cls=updated_item.get('cls', ''),  # Copy classes
                id=f"feed-item-{item_id}",
                hx_swap_oob='outerHTML',  # Replace the entire list item
                hx_get=f"/item/{item_after['id']}?unread_view={unread_view}",
                hx_target="#item-detail",
                hx_trigger="click"
            )
            responses.append(updated_item)
    
    # Return tuple of responses for HTMX to handle
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
            return Div(f"Already subscribed to this feed", cls='text-yellow-600 p-4')
    
    return Div(f"Failed to add feed: {result.get('error', 'Unknown error')}", 
              cls='text-red-500 p-4')

@rt('/api/item/{item_id}/star')
def star_item(item_id: int, request):
    """Toggle star status"""
    session_id = request.scope['session_id']
    UserItemModel.toggle_star(session_id, item_id)
    
    # Return updated item detail
    items = FeedItemModel.get_items_for_user(session_id)
    item = next((i for i in items if i['id'] == item_id), None)
    return ItemDetailView(item)

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
        
        # Return updated item detail
        items = FeedItemModel.get_items_for_user(session_id)
        item = next((i for i in items if i['id'] == item_id), None)
        return ItemDetailView(item)
    
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
    serve(port=5001, host="0.0.0.0")