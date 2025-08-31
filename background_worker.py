"""
Background worker system for RSS feed updates with domain rate limiting
"""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Set, Optional, Any
import httpx
from urllib.parse import urlparse

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
        """Synchronous feed parsing (runs in thread pool)"""
        import feedparser
        
        # Parse the feed content
        feed_data = feedparser.parse(content)
        
        if not feed_data or feed_data.bozo:
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
        
        # Process feed items - simplified for background worker
        items_added = 0
        if hasattr(feed_data, 'entries'):
            from models import FeedItemModel
            
            for entry in feed_data.entries:
                try:
                    # Extract basic item data
                    guid = getattr(entry, 'id', None) or getattr(entry, 'guid', None) or getattr(entry, 'link', None)
                    title = getattr(entry, 'title', 'Untitled')
                    link = getattr(entry, 'link', '')
                    
                    if not (guid and title and link):
                        continue
                    
                    # Simple description extraction for testing
                    description = None
                    if hasattr(entry, 'summary') and entry.summary:
                        description = entry.summary[:500]  # Simple truncation for testing
                    
                    # Parse published date
                    published = None
                    if hasattr(entry, 'published'):
                        try:
                            published = self.feed_parser.parse_date(entry.published)
                        except:
                            published = datetime.now()
                    
                    # Save to database (INSERT OR REPLACE handles duplicates)
                    if description:
                        FeedItemModel.create_item(
                            feed_id=feed_id,
                            guid=guid,
                            title=title,
                            link=link,
                            description=description,
                            content=None,
                            published=published
                        )
                        items_added += 1
                        
                except Exception as e:
                    logger.error(f"Error processing feed item: {e}")
                    continue
        
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
    
    if feed_worker is None:
        feed_worker = FeedUpdateWorker()
        queue_manager = FeedQueueManager(feed_worker)
        await feed_worker.start()
        
        # Queue all feeds initially for first startup
        all_feeds = FeedModel.get_feeds_to_update(max_age_minutes=60)  # Feeds older than 1 hour
        for feed in all_feeds:
            await feed_worker.queue.put(feed)
        
        logger.info(f"Worker system initialized, queued {len(all_feeds)} feeds")


async def shutdown_worker_system():
    """Shutdown the global worker system"""
    global feed_worker
    
    if feed_worker:
        await feed_worker.stop()
        feed_worker = None