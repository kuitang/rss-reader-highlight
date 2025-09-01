"""
Background worker system for RSS feed updates with domain rate limiting
"""

import threading
import queue
import time
import logging
import os
import gc
import psutil
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
        self.lock = threading.Lock()
    
    def acquire(self):
        """Wait if necessary to respect rate limit for this domain"""
        with self.lock:
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
                    time.sleep(sleep_time)
                
                # Clean up old requests again after sleeping
                now = datetime.now()
                cutoff = now - timedelta(seconds=self.per_seconds)
                self.requests = [r for r in self.requests if r > cutoff]
            
            # Record this request
            self.requests.append(now)


class MemoryMonitor:
    """Memory usage tracking for leak detection"""
    
    def __init__(self, memory_limit_mb: int = 256):
        self.memory_limit_mb = memory_limit_mb
        self.baseline_mb = None
        self.memory_samples = []  # Circular buffer for last 24h
        self.feed_processing_stats = []  # Per-feed memory costs
        self.feeds_processed_today = 0
        self.peak_memory_mb = 0
        self.peak_memory_time = None
        self.last_gc_time = None
        self.last_gc_collected = 0
        
    def record_memory_sample(self, memory_mb: float, context: str = ""):
        """Record a memory sample with timestamp"""
        now = datetime.now()
        sample = {
            'time': now,
            'memory_mb': memory_mb,
            'context': context
        }
        
        self.memory_samples.append(sample)
        
        # Keep only last 24 hours of samples
        cutoff = now - timedelta(hours=24)
        self.memory_samples = [s for s in self.memory_samples if s['time'] > cutoff]
        
        # Update peak memory
        if memory_mb > self.peak_memory_mb:
            self.peak_memory_mb = memory_mb
            self.peak_memory_time = now
    
    def record_feed_processing(self, feed_title: str, memory_before: float, memory_after: float, content_size_kb: float):
        """Record memory cost of processing a specific feed"""
        memory_delta = memory_after - memory_before
        
        self.feed_processing_stats.append({
            'time': datetime.now(),
            'feed_title': feed_title,
            'memory_before_mb': memory_before,
            'memory_after_mb': memory_after,
            'memory_delta_mb': memory_delta,
            'content_size_kb': content_size_kb
        })
        
        # Keep only last 100 feed processing records
        self.feed_processing_stats = self.feed_processing_stats[-100:]
        self.feeds_processed_today += 1
    
    def get_memory_trend(self, hours: int = 1) -> float:
        """Calculate memory trend over last N hours (MB change)"""
        if len(self.memory_samples) < 2:
            return 0.0
            
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_samples = [s for s in self.memory_samples if s['time'] > cutoff]
        
        if len(recent_samples) < 2:
            return 0.0
        
        return recent_samples[-1]['memory_mb'] - recent_samples[0]['memory_mb']
    
    def estimate_feeds_until_oom(self, current_memory_mb: float) -> int:
        """Estimate how many more feeds can be processed before hitting memory limit"""
        if not self.feed_processing_stats:
            return 0
        
        # Calculate average memory cost per feed
        recent_stats = self.feed_processing_stats[-10:]  # Last 10 feeds
        avg_memory_cost = sum(s['memory_delta_mb'] for s in recent_stats) / len(recent_stats)
        
        remaining_memory = self.memory_limit_mb - current_memory_mb
        return max(0, int(remaining_memory / max(avg_memory_cost, 1.0)))
    
    def get_warning_level(self, current_memory_mb: float) -> str:
        """Get memory warning level based on current usage"""
        percent_used = (current_memory_mb / self.memory_limit_mb) * 100
        
        if percent_used > 90:
            return "critical"
        elif percent_used > 75:
            return "high"
        elif percent_used > 50:
            return "medium"
        else:
            return "low"


class FeedUpdateWorker(threading.Thread):
    """Background worker for processing RSS feed updates"""
    
    def __init__(self, rate_limit_per_domain: int = 10, rate_limit_window: int = 60):
        super().__init__(daemon=True)
        self.queue = queue.Queue()
        self.domain_limiters = defaultdict(lambda: DomainRateLimiter(rate_limit_per_domain, rate_limit_window))
        self.last_heartbeat = datetime.now()
        self.is_running = False
        self.current_feed = None
        self.feed_parser = FeedParser()
        self.memory_monitor = MemoryMonitor()
    
    def start(self):
        """Start the background worker"""
        if self.is_running:
            return
            
        self.is_running = True
        super().start()  # Start the thread
        logger.info("Background feed worker started")
    
    def stop(self):
        """Stop the background worker gracefully"""
        self.is_running = False
        logger.info("Background feed worker stopped")
    
    def run(self):
        """Main worker loop - processes feeds from queue"""
        # Set memory baseline
        process = psutil.Process()
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
        self.memory_monitor.baseline_mb = baseline_memory
        self.memory_monitor.record_memory_sample(baseline_memory, "worker_startup")
        logger.info(f"Worker thread memory baseline: {baseline_memory:.1f}MB")
        
        # Create HTTP client with connection limits to prevent memory leaks
        with httpx.Client(
            timeout=30.0,
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=2)
        ) as client:
            while self.is_running:
                try:
                    # Wait for a feed to process (with timeout to update heartbeat)
                    feed = self.queue.get(timeout=60.0)
                    self.current_feed = feed
                    
                    # Record memory before processing
                    current_memory = process.memory_info().rss / 1024 / 1024
                    self.memory_monitor.record_memory_sample(current_memory, f"before_feed_{feed.get('id')}")
                    
                    self._process_feed(client, feed)
                    
                    # Record memory after processing
                    memory_after = process.memory_info().rss / 1024 / 1024
                    self.memory_monitor.record_memory_sample(memory_after, f"after_feed_{feed.get('id')}")
                    
                    self.current_feed = None
                    self.last_heartbeat = datetime.now()
                    self.queue.task_done()
                    
                except queue.Empty:
                    # No feeds to process - just update heartbeat and record memory
                    current_memory = process.memory_info().rss / 1024 / 1024
                    self.memory_monitor.record_memory_sample(current_memory, "idle_heartbeat")
                    self.last_heartbeat = datetime.now()
                    self.current_feed = None
                    
                except Exception as e:
                    logger.error(f"Worker error processing feed: {e}")
                    self.current_feed = None
                    self.last_heartbeat = datetime.now()
                    if hasattr(self.queue, 'task_done'):
                        self.queue.task_done()
    
    def _process_feed(self, client: httpx.Client, feed: Dict[str, Any]):
        """Process a single feed with rate limiting and memory management"""
        memory_before = None
        content_size_kb = 0
        try:
            # Log memory usage before processing
            process = psutil.Process()
            memory_before = process.memory_info().rss / 1024 / 1024  # MB
            
            # Extract domain for rate limiting
            domain = urlparse(feed['url']).netloc
            rate_limiter = self.domain_limiters[domain]
            
            # Apply rate limiting
            rate_limiter.acquire()
            
            # Process the feed using existing feed parser logic
            result = self._fetch_and_parse_feed(client, feed)
            content_size_kb = result.get('content_size', 0) / 1024
            
            if result.get('updated'):
                logger.info(f"Updated feed {feed['id']}: {result.get('items_added', 0)} new items")
            
        except Exception as e:
            logger.error(f"Error processing feed {feed.get('id', 'unknown')}: {e}")
        finally:
            # Memory cleanup and monitoring
            if memory_before:
                memory_after = psutil.Process().memory_info().rss / 1024 / 1024
                memory_diff = memory_after - memory_before
                
                # Record detailed memory statistics
                feed_title = feed.get('title', 'Unknown Feed')
                self.memory_monitor.record_feed_processing(
                    feed_title, memory_before, memory_after, content_size_kb
                )
                
                logger.info(f"Feed {feed.get('id')} memory: {memory_before:.1f}MB → {memory_after:.1f}MB (Δ{memory_diff:+.1f}MB)")
                
                # Force garbage collection after processing
                collected = gc.collect()
                self.memory_monitor.last_gc_time = datetime.now()
                self.memory_monitor.last_gc_collected = collected
                
                if collected > 0:
                    memory_final = psutil.Process().memory_info().rss / 1024 / 1024
                    logger.info(f"GC collected {collected} objects, final memory: {memory_final:.1f}MB")
            
            # Mark feed as processed to clean up queued_feeds set
            if hasattr(self, '_queue_manager_ref') and self._queue_manager_ref:
                self._queue_manager_ref.mark_feed_processed(feed.get('id'))
    
    def _fetch_and_parse_feed(self, client: httpx.Client, feed: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch and parse a single feed (sync version)"""
        content = None
        try:
            # Build headers for conditional requests
            headers = {}
            if feed.get('etag'):
                headers['If-None-Match'] = feed['etag']
            if feed.get('last_modified'):
                headers['If-Modified-Since'] = feed['last_modified']
            
            # Make HTTP request
            response = client.get(feed['url'], headers=headers, follow_redirects=True)
            
            if response.status_code == 304:
                # Feed not modified
                return {'updated': False, 'status': 304}
            elif response.status_code != 200:
                logger.error(f"HTTP {response.status_code} for feed {feed['url']}")
                return {'updated': False, 'status': response.status_code}
            
            # Check content size before processing
            content = response.text
            content_size = len(content)
            
            if content_size > 500_000:  # 500KB limit
                logger.warning(f"Skipping large feed {feed['url']}: {content_size} bytes")
                return {'updated': False, 'status': 0, 'error': 'Feed too large'}
            
            # Parse feed directly (no thread pool needed)
            parse_result = self._parse_feed_content(
                content,
                feed['id'],
                response.headers.get('etag'),
                response.headers.get('last-modified')
            )
            
            # Add content size to result for memory monitoring
            parse_result['content_size'] = content_size
            return parse_result
            
        except Exception as e:
            logger.error(f"Error fetching feed {feed['url']}: {e}")
            return {'updated': False, 'status': 0, 'error': str(e)}
        finally:
            # Explicit cleanup of large content
            content = None
            gc.collect()
    
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
    
    def _process_feed_direct(self, feed: Dict[str, Any]):
        """Direct feed processing for testing (bypasses queue)"""
        with httpx.Client(timeout=30.0) as client:
            self._process_feed(client, feed)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current worker status for UI"""
        return {
            'is_updating': self.queue.qsize() > 0 and self.is_running,
            'queue_size': self.queue.qsize(),
            'current_feed': self.current_feed.get('title') if self.current_feed else None,
            'worker_alive': self._is_worker_alive(),
            'last_heartbeat': self.last_heartbeat.isoformat()
        }
    
    def get_memory_status(self) -> Dict[str, Any]:
        """Get detailed memory status for monitoring"""
        process = psutil.Process()
        current_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Calculate derived metrics
        memory_increase = current_memory - (self.memory_monitor.baseline_mb or 0)
        memory_percent = (current_memory / self.memory_monitor.memory_limit_mb) * 100
        memory_trend_1h = self.memory_monitor.get_memory_trend(hours=1)
        feeds_until_oom = self.memory_monitor.estimate_feeds_until_oom(current_memory)
        warning_level = self.memory_monitor.get_warning_level(current_memory)
        
        # Recent feed processing stats
        recent_feeds = self.memory_monitor.feed_processing_stats[-5:]  # Last 5 feeds
        avg_memory_cost = 0
        largest_feed = None
        
        if recent_feeds:
            avg_memory_cost = sum(s['memory_delta_mb'] for s in recent_feeds) / len(recent_feeds)
            largest_feed = max(recent_feeds, key=lambda x: x['memory_delta_mb'])
        
        return {
            # Current memory state
            'memory_mb': round(current_memory, 1),
            'memory_baseline_mb': round(self.memory_monitor.baseline_mb or 0, 1),
            'memory_increase_mb': round(memory_increase, 1),
            'memory_percent_of_limit': round(memory_percent, 1),
            
            # Worker state
            'worker_status': 'processing' if self.current_feed else ('idle' if self.is_running else 'stopped'),
            'current_feed': self.current_feed.get('title') if self.current_feed else None,
            'queue_size': self.queue.qsize(),
            'feeds_processed_today': self.memory_monitor.feeds_processed_today,
            
            # Memory trends and warnings
            'memory_trend_1h_mb': round(memory_trend_1h, 1),
            'peak_memory_mb': round(self.memory_monitor.peak_memory_mb, 1),
            'peak_memory_time': self.memory_monitor.peak_memory_time.isoformat() if self.memory_monitor.peak_memory_time else None,
            'warning_level': warning_level,
            'feeds_until_oom': feeds_until_oom,
            'recommend_restart': warning_level == 'critical' or memory_trend_1h > 20.0,
            
            # Garbage collection
            'last_gc_time': self.memory_monitor.last_gc_time.isoformat() if self.memory_monitor.last_gc_time else None,
            'last_gc_collected': self.memory_monitor.last_gc_collected,
            
            # Feed processing efficiency
            'avg_memory_cost_per_feed_mb': round(avg_memory_cost, 1) if recent_feeds else 0,
            'largest_feed_processed': {
                'title': largest_feed['feed_title'][:50] if largest_feed else None,
                'memory_cost_mb': round(largest_feed['memory_delta_mb'], 1) if largest_feed else 0,
                'content_size_kb': round(largest_feed['content_size_kb'], 1) if largest_feed else 0
            } if largest_feed else None
        }
    
    def _is_worker_alive(self) -> bool:
        """Check if worker is healthy"""
        if not self.is_running:
            return False
        if not self.is_alive():
            return False
        # Worker is alive if heartbeat is recent (< 2 minutes)
        return datetime.now() - self.last_heartbeat < timedelta(minutes=2)


class FeedQueueManager:
    """Manages feed update queue based on user activity"""
    
    def __init__(self, worker: FeedUpdateWorker, update_interval_minutes: int = 1):
        self.worker = worker
        self.update_interval = timedelta(minutes=update_interval_minutes)
        self.queued_feeds: Set[int] = set()
        # Give worker reference to queue manager for cleanup
        self.worker._queue_manager_ref = self
    
    def queue_user_feeds(self, session_id: str):
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
                    self.worker.queue.put(feed_data)
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


def initialize_worker_system():
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
        
        feed_worker.start()
        print(f"[{timestamp}] DEBUG: Worker started")
        
        # Queue all feeds initially for first startup
        all_feeds = FeedModel.get_feeds_to_update(max_age_minutes=60)  # Feeds older than 1 hour
        print(f"[{timestamp}] DEBUG: Found {len(all_feeds)} feeds to queue")
        
        for feed in all_feeds:
            feed_worker.queue.put(feed)
        
        print(f"[{timestamp}] DEBUG: After init - feed_worker: {feed_worker}, queue_manager: {queue_manager}")
        logger.info(f"[{timestamp}] Worker system initialized, queued {len(all_feeds)} feeds (PIDs: main={os.getpid()})")
    else:
        print(f"[{timestamp}] DEBUG: Worker system already initialized")


def shutdown_worker_system():
    """Shutdown the global worker system"""
    global feed_worker
    
    if feed_worker:
        feed_worker.stop()
        if feed_worker.is_alive():
            feed_worker.join(timeout=5.0)
        feed_worker = None