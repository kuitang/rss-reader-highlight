"""
Background worker system for RSS feed updates with domain rate limiting
"""

import asyncio
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Set, Optional, Any
import httpx
from urllib.parse import urlparse
import trafilatura
from bs4 import BeautifulSoup

from models import FeedModel
from feed_parser import FeedParser

logger = logging.getLogger(__name__)


class DomainRateLimiter:
    """Rate limiter for HTTP requests per domain"""
    
    def __init__(self, max_requests: int, per_seconds: int):
        self.max_requests = max_requests
        self.per_seconds = per_seconds
        self.requests = []
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        """Wait if necessary to respect rate limit for this domain"""
        async with self.lock:
            now = datetime.now()
            
            # Remove old requests outside the time window
            cutoff = now - timedelta(seconds=self.per_seconds)
            self.requests = [r for r in self.requests if r > cutoff]
            
            # If we're at the limit, wait until we can make another request
            if len(self.requests) >= self.max_requests:
                oldest_request = min(self.requests)
                sleep_until = oldest_request + timedelta(seconds=self.per_seconds)
                sleep_time = (sleep_until - now).total_seconds()
                
                if sleep_time > 0:
                    logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
                    await asyncio.sleep(sleep_time)
                
                # Clean up old requests again after sleeping
                now = datetime.now()
                cutoff = now - timedelta(seconds=self.per_seconds)
                self.requests = [r for r in self.requests if r > cutoff]
            
            # Record this request
            self.requests.append(now)


class FeedUpdateWorker:
    """Background worker for processing RSS feed updates"""
    
    def __init__(self, rate_limit_per_domain: int = 10, rate_limit_window: int = 60):
        self.queue = asyncio.Queue()
        self.domain_limiters = defaultdict(lambda: DomainRateLimiter(rate_limit_per_domain, rate_limit_window))
        self.worker_task = None
        self.last_heartbeat = datetime.now()
        self.is_running = False
        self.current_feed = None
        self.feed_parser = FeedParser()
    
    async def start(self):
        """Start the background worker"""
        if self.is_running:
            return
            
        self.is_running = True
        self.worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Background feed worker started")
    
    async def stop(self):
        """Stop the background worker gracefully"""
        self.is_running = False
        
        if self.worker_task and not self.worker_task.done():
            self.worker_task.cancel()
            try:
                await asyncio.wait_for(self.worker_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Worker shutdown timed out")
            except asyncio.CancelledError:
                pass
        
        logger.info("Background feed worker stopped")
    
    async def _worker_loop(self):
        """Main worker loop - processes feeds from queue"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            while self.is_running:
                try:
                    # Wait for a feed to process (with timeout to update heartbeat)
                    feed = await asyncio.wait_for(self.queue.get(), timeout=60.0)
                    self.current_feed = feed
                    
                    await self._process_feed(client, feed)
                    
                    self.current_feed = None
                    self.last_heartbeat = datetime.now()
                    
                except asyncio.TimeoutError:
                    # No feeds to process - just update heartbeat
                    self.last_heartbeat = datetime.now()
                    self.current_feed = None
                    
                except Exception as e:
                    logger.error(f"Worker error processing feed: {e}")
                    self.current_feed = None
                    self.last_heartbeat = datetime.now()
    
    async def _process_feed(self, client: httpx.AsyncClient, feed: Dict[str, Any]):
        """Process a single feed with rate limiting"""
        try:
            # Extract domain for rate limiting
            domain = urlparse(feed['url']).netloc
            rate_limiter = self.domain_limiters[domain]
            
            # Apply rate limiting
            await rate_limiter.acquire()
            
            # Process the feed using existing feed parser logic
            result = await self._fetch_and_parse_feed(client, feed)
            
            if result.get('updated'):
                logger.info(f"Updated feed {feed['id']}: {result.get('items_added', 0)} new items")
            
        except Exception as e:
            logger.error(f"Error processing feed {feed.get('id', 'unknown')}: {e}")
    
    async def _fetch_and_parse_feed(self, client: httpx.AsyncClient, feed: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch and parse a single feed (async version of feed_parser logic)"""
        try:
            # Build headers for conditional requests
            headers = {}
            if feed.get('etag'):
                headers['If-None-Match'] = feed['etag']
            if feed.get('last_modified'):
                headers['If-Modified-Since'] = feed['last_modified']
            
            # Make HTTP request
            response = await client.get(feed['url'], headers=headers, follow_redirects=True)
            
            if response.status_code == 304:
                # Feed not modified
                return {'updated': False, 'status': 304}
            elif response.status_code != 200:
                logger.error(f"HTTP {response.status_code} for feed {feed['url']}")
                return {'updated': False, 'status': response.status_code}
            
            # Parse feed using existing synchronous parser
            # (We'll run the CPU-bound parsing in a thread pool to avoid blocking)
            parse_result = await asyncio.get_event_loop().run_in_executor(
                None,
                self._parse_feed_content,
                response.text,
                feed['id'],
                response.headers.get('etag'),
                response.headers.get('last-modified')
            )
            
            return parse_result
            
        except Exception as e:
            logger.error(f"Error fetching feed {feed['url']}: {e}")
            return {'updated': False, 'status': 0, 'error': str(e)}
    
    def _parse_feed_content(self, content: str, feed_id: int, etag: str, last_modified: str) -> Dict[str, Any]:
        """Synchronous feed parsing (runs in thread pool) - FULL EXTRACTION LOGIC"""
        import feedparser
        import trafilatura
        from bs4 import BeautifulSoup
        
        # Parse the feed content
        feed_data = feedparser.parse(content)
        
        if feed_data.bozo and hasattr(feed_data, 'bozo_exception'):
            logger.warning(f"Feed parsing warning for feed {feed_id}: {feed_data.bozo_exception}")
        
        if not feed_data or not hasattr(feed_data, 'feed'):
            return {'updated': False, 'status': 0, 'error': 'Invalid feed format'}
        
        # Update feed metadata
        feed_title = getattr(feed_data.feed, 'title', None)
        feed_description = getattr(feed_data.feed, 'description', None)
        
        FeedModel.update_feed(
            feed_id=feed_id,
            title=feed_title,
            description=feed_description,
            etag=etag,
            last_modified=last_modified
        )
        
        # Process feed entries with FULL extraction logic
        items_added = 0
        if hasattr(feed_data, 'entries'):
            from models import FeedItemModel
            
            for entry in feed_data.entries:
                try:
                    # Extract item data
                    guid = getattr(entry, 'id', None) or getattr(entry, 'guid', None) or getattr(entry, 'link', None)
                    title = getattr(entry, 'title', 'Untitled')
                    link = getattr(entry, 'link', '')
                    
                    # Get description and content, sanitize HTML and convert to Markdown
                    description = None
                    content = None
                    
                    if hasattr(entry, 'summary') and entry.summary:
                        # Convert HTML summary to clean Markdown
                        logger.debug(f"Processing summary for entry: {title[:50]}...")
                        logger.debug(f"Summary content type: {type(entry.summary)}")
                        logger.debug(f"Summary length: {len(entry.summary) if entry.summary else 0}")
                        logger.debug(f"Summary preview: {entry.summary[:200] if entry.summary else 'None'}...")
                        
                        # Extract images first using BeautifulSoup
                        soup = BeautifulSoup(entry.summary, 'html.parser')
                        images = []
                        for img in soup.find_all('img'):
                            src = img.get('src')
                            alt = img.get('alt', '')
                            if src:
                                # Create markdown image syntax: ![alt text](url)
                                images.append(f"![{alt}]({src})")
                        
                        # Extract text content with trafilatura
                        wrapped_html = f"<html><body>{entry.summary}</body></html>"
                        description = trafilatura.extract(wrapped_html, include_formatting=True, output_format='markdown')
                        
                        # Combine images and text
                        if images and description:
                            # Add images at the beginning of the description
                            description = '\n'.join(images) + '\n\n' + description
                        elif images and not description:
                            # If only images, use them as description
                            description = '\n'.join(images)
                        elif not description:
                            # No text or images - skip this item
                            logger.warning(f"Skipping '{title}' - trafilatura couldn't extract content from: {entry.summary[:200]}")
                            continue
                    
                    if hasattr(entry, 'content') and entry.content:
                        # Take the first content entry
                        content_entry = entry.content[0] if isinstance(entry.content, list) else entry.content
                        raw_content = content_entry.value if hasattr(content_entry, 'value') else str(content_entry)
                        
                        # Convert HTML content to clean Markdown
                        logger.debug(f"Processing content for entry: {title[:50]}...")
                        logger.debug(f"Content type: {type(raw_content)}")
                        logger.debug(f"Content length: {len(raw_content) if raw_content else 0}")
                        logger.debug(f"Content preview: {raw_content[:200] if raw_content else 'None'}...")
                        
                        # Extract images first using BeautifulSoup
                        soup = BeautifulSoup(raw_content, 'html.parser')
                        images = []
                        for img in soup.find_all('img'):
                            src = img.get('src')
                            alt = img.get('alt', '')
                            if src:
                                # Create markdown image syntax: ![alt text](url)
                                images.append(f"![{alt}]({src})")
                        
                        # Extract text content with trafilatura
                        wrapped_content = f"<html><body>{raw_content}</body></html>"
                        content = trafilatura.extract(wrapped_content, include_formatting=True, output_format='markdown')
                        
                        # Combine images and text
                        if images and content:
                            # Add images at appropriate position (after first paragraph if exists)
                            paragraphs = content.split('\n\n')
                            if len(paragraphs) > 1:
                                # Insert images after first paragraph
                                content = paragraphs[0] + '\n\n' + '\n'.join(images) + '\n\n' + '\n\n'.join(paragraphs[1:])
                            else:
                                # Add images at the beginning
                                content = '\n'.join(images) + '\n\n' + content
                        elif images and not content:
                            # If only images, use them as content
                            content = '\n'.join(images)
                        elif not content:
                            # Log the failure - but if we have a description, continue with that
                            logger.warning(f"Couldn't extract content for '{title}' - using description only")
                            if not description:
                                # No description either - skip this item entirely
                                logger.error(f"Skipping '{title}' - no extractable content or description")
                                continue
                    
                    # Parse published date
                    published = None
                    if hasattr(entry, 'published'):
                        published = self.feed_parser.parse_date(entry.published)
                    elif hasattr(entry, 'updated'):
                        published = self.feed_parser.parse_date(entry.updated)
                    
                    # Only save items that have meaningful content
                    if guid and title and link and (description or content):
                        FeedItemModel.create_item(
                            feed_id=feed_id,
                            guid=guid,
                            title=title,
                            link=link,
                            description=description,
                            content=content,
                            published=published
                        )
                        items_added += 1
                    else:
                        logger.warning(f"Skipping item '{title}' - missing required fields or content")
                        
                except Exception as e:
                    logger.error(f"Error processing entry for feed {feed_id}: {str(e)}")
                    continue
        
        logger.info(f"Updated feed {feed_id}: {items_added} items added")
        return {
            'updated': True,
            'status': 200,
            'items_added': items_added,
            'feed_title': feed_title
        }
    
    async def _process_feed_direct(self, feed: Dict[str, Any]):
        """Direct feed processing for testing (bypasses queue)"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            await self._process_feed(client, feed)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current worker status for UI"""
        return {
            'is_updating': self.queue.qsize() > 0 and self.is_running,
            'queue_size': self.queue.qsize(),
            'current_feed': self.current_feed.get('title') if self.current_feed else None,
            'worker_alive': self._is_worker_alive(),
            'last_heartbeat': self.last_heartbeat.isoformat()
        }
    
    def _is_worker_alive(self) -> bool:
        """Check if worker is healthy"""
        if not self.is_running:
            return False
        if not self.worker_task or self.worker_task.done():
            return False
        # Worker is alive if heartbeat is recent (< 2 minutes)
        return datetime.now() - self.last_heartbeat < timedelta(minutes=2)


class FeedQueueManager:
    """Manages feed update queue based on user activity"""
    
    def __init__(self, worker: FeedUpdateWorker, update_interval_minutes: int = 1):
        self.worker = worker
        self.update_interval = timedelta(minutes=update_interval_minutes)
        self.queued_feeds: Set[int] = set()
    
    async def queue_user_feeds(self, session_id: str):
        """Queue feeds for a user if they need updating"""
        try:
            # Get user's subscribed feeds
            user_feeds = FeedModel.get_user_feeds(session_id)
            
            feeds_queued = 0
            for feed in user_feeds:
                if self._needs_update(feed) and feed['id'] not in self.queued_feeds:
                    # Create feed dict with required fields for worker
                    feed_data = {
                        'id': feed['id'],
                        'url': feed['url'],
                        'title': feed.get('title'),
                        'last_updated': feed.get('last_updated'),
                        'etag': feed.get('etag'),
                        'last_modified': feed.get('last_modified')
                    }
                    await self.worker.queue.put(feed_data)
                    self.queued_feeds.add(feed['id'])
                    feeds_queued += 1
            
            if feeds_queued > 0:
                logger.info(f"Queued {feeds_queued} feeds for session {session_id}")
            
        except Exception as e:
            logger.error(f"Error queueing feeds for session {session_id}: {e}")
            # Re-raise for debugging in tests
            raise
    
    def _needs_update(self, feed: Dict[str, Any]) -> bool:
        """Check if feed needs updating based on last update time"""
        if not feed.get('last_updated'):
            return True
        
        try:
            last_updated = datetime.fromisoformat(feed['last_updated'])
            return datetime.now() - last_updated > self.update_interval
        except (ValueError, TypeError):
            # If we can't parse the date, assume it needs updating
            return True
    
    def mark_feed_processed(self, feed_id: int):
        """Mark feed as processed (remove from queued set)"""
        self.queued_feeds.discard(feed_id)


# Global worker instance (will be initialized in app.py)
feed_worker: Optional[FeedUpdateWorker] = None
queue_manager: Optional[FeedQueueManager] = None


async def initialize_worker_system():
    """Initialize the global worker system"""
    global feed_worker, queue_manager
    
    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"[{timestamp}] DEBUG: initialize_worker_system() called")
    print(f"[{timestamp}] DEBUG: Before init - feed_worker: {feed_worker}, queue_manager: {queue_manager}")
    
    if feed_worker is None:
        print(f"[{timestamp}] DEBUG: Creating new worker and queue manager...")
        feed_worker = FeedUpdateWorker()
        print(f"[{timestamp}] DEBUG: Created feed_worker: {feed_worker}")
        
        queue_manager = FeedQueueManager(feed_worker)
        print(f"[{timestamp}] DEBUG: Created queue_manager: {queue_manager}")
        
        await feed_worker.start()
        print(f"[{timestamp}] DEBUG: Worker started")
        
        # Queue all feeds initially for first startup
        all_feeds = FeedModel.get_feeds_to_update(max_age_minutes=60)  # Feeds older than 1 hour
        print(f"[{timestamp}] DEBUG: Found {len(all_feeds)} feeds to queue")
        
        for feed in all_feeds:
            await feed_worker.queue.put(feed)
        
        print(f"[{timestamp}] DEBUG: After init - feed_worker: {feed_worker}, queue_manager: {queue_manager}")
        logger.info(f"[{timestamp}] Worker system initialized, queued {len(all_feeds)} feeds (PIDs: main={os.getpid()})")
    else:
        print(f"[{timestamp}] DEBUG: Worker system already initialized")


async def shutdown_worker_system():
    """Shutdown the global worker system"""
    global feed_worker
    
    if feed_worker:
        await feed_worker.stop()
        feed_worker = None