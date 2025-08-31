"""RSS/Atom feed parsing and updating logic"""

import feedparser
import httpx
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dateutil import parser as date_parser
import logging
from models import FeedModel, FeedItemModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FeedParser:
    def __init__(self):
        self.client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,  # Follow HTTP redirects like BBC's 302
            headers={
                'User-Agent': 'RSS Reader/1.0 (+https://github.com/user/rss-reader)'
            }
        )
    
    def parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats to datetime"""
        if not date_str:
            return None
        
        try:
            # Try feedparser's time parsing first
            parsed_time = feedparser._parse_date(date_str)
            if parsed_time:
                return datetime(*parsed_time[:6], tzinfo=timezone.utc)
        except:
            pass
        
        try:
            # Fallback to dateutil parser
            parsed_date = date_parser.parse(date_str)
            if parsed_date.tzinfo is None:
                parsed_date = parsed_date.replace(tzinfo=timezone.utc)
            return parsed_date
        except:
            logger.warning(f"Could not parse date: {date_str}")
            return None
    
    def fetch_feed(self, url: str, etag: str = None, last_modified: str = None) -> Dict:
        """Fetch feed with HTTP caching headers"""
        headers = {}
        
        if etag:
            headers['If-None-Match'] = etag
        if last_modified:
            headers['If-Modified-Since'] = last_modified
        
        try:
            response = self.client.get(url, headers=headers)
            
            if response.status_code == 304:
                logger.info(f"Feed not modified: {url}")
                return {'status': 304, 'updated': False}
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch feed {url}: {response.status_code}")
                return {'status': response.status_code, 'updated': False}
            
            # Parse feed content
            feed_data = feedparser.parse(response.text)
            
            if feed_data.bozo and hasattr(feed_data, 'bozo_exception'):
                logger.warning(f"Feed parsing warning for {url}: {feed_data.bozo_exception}")
            
            return {
                'status': response.status_code,
                'updated': True,
                'data': feed_data,
                'etag': response.headers.get('etag'),
                'last_modified': response.headers.get('last-modified'),
                'content': response.text
            }
            
        except Exception as e:
            logger.error(f"Error fetching feed {url}: {str(e)}")
            return {'status': 0, 'updated': False, 'error': str(e)}
    
    def parse_and_store_feed(self, feed_id: int, url: str, etag: str = None, last_modified: str = None) -> Dict:
        """Fetch, parse and store feed items"""
        result = self.fetch_feed(url, etag, last_modified)
        
        if not result['updated']:
            return result
        
        feed_data = result['data']
        
        if hasattr(feed_data, 'feed'):
            # Update feed metadata
            feed_title = getattr(feed_data.feed, 'title', None)
            feed_description = getattr(feed_data.feed, 'description', None)
            
            FeedModel.update_feed(
                feed_id=feed_id,
                title=feed_title,
                description=feed_description,
                etag=result.get('etag'),
                last_modified=result.get('last_modified')
            )
        
        # Process feed entries
        items_added = 0
        if hasattr(feed_data, 'entries'):
            for entry in feed_data.entries:
                try:
                    # Extract item data
                    guid = getattr(entry, 'id', None) or getattr(entry, 'guid', None) or getattr(entry, 'link', None)
                    title = getattr(entry, 'title', 'Untitled')
                    link = getattr(entry, 'link', '')
                    
                    # Get description and content
                    description = None
                    content = None
                    
                    if hasattr(entry, 'summary'):
                        description = entry.summary
                    
                    if hasattr(entry, 'content') and entry.content:
                        # Take the first content entry
                        content_entry = entry.content[0] if isinstance(entry.content, list) else entry.content
                        if hasattr(content_entry, 'value'):
                            content = content_entry.value
                        else:
                            content = str(content_entry)
                    
                    # Parse published date
                    published = None
                    if hasattr(entry, 'published'):
                        published = self.parse_date(entry.published)
                    elif hasattr(entry, 'updated'):
                        published = self.parse_date(entry.updated)
                    
                    if guid and title and link:
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
                    
                except Exception as e:
                    logger.error(f"Error processing entry for feed {feed_id}: {str(e)}")
                    continue
        
        logger.info(f"Updated feed {feed_id}: {items_added} items added")
        return {
            'status': result['status'],
            'updated': True,
            'items_added': items_added,
            'feed_title': feed_title if 'feed_title' in locals() else None
        }
    
    def update_all_feeds(self, max_age_minutes: int = 1):
        """Update all feeds that need refreshing"""
        feeds_to_update = FeedModel.get_feeds_to_update(max_age_minutes)
        
        logger.info(f"Updating {len(feeds_to_update)} feeds")
        
        results = []
        for feed in feeds_to_update:
            try:
                result = self.parse_and_store_feed(
                    feed_id=feed['id'],
                    url=feed['url'],
                    etag=feed.get('etag'),
                    last_modified=feed.get('last_modified')
                )
                results.append({
                    'feed_id': feed['id'],
                    'url': feed['url'],
                    **result
                })
            except Exception as e:
                logger.error(f"Error updating feed {feed['id']}: {str(e)}")
                results.append({
                    'feed_id': feed['id'],
                    'url': feed['url'],
                    'status': 0,
                    'updated': False,
                    'error': str(e)
                })
        
        return results
    
    def add_feed(self, url: str) -> Dict:
        """Add new feed and do initial parsing"""
        try:
            # Create or get existing feed
            feed_id = FeedModel.create_feed(url)
            
            # Do initial parse
            result = self.parse_and_store_feed(feed_id, url)
            
            return {
                'success': True,
                'feed_id': feed_id,
                **result
            }
            
        except Exception as e:
            logger.error(f"Error adding feed {url}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def __del__(self):
        """Clean up HTTP client"""
        if hasattr(self, 'client'):
            self.client.close()

def setup_default_feeds():
    """Set up default RSS feeds"""
    parser = FeedParser()
    
    default_feeds = [
        "https://hnrss.org/frontpage",  # Hacker News
        "https://www.reddit.com/r/all/.rss",  # Reddit All
        "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain"  # WSJ Markets
    ]
    
    results = []
    for url in default_feeds:
        try:
            result = parser.add_feed(url)
            results.append(result)
            logger.info(f"Added default feed: {url} - {result}")
        except Exception as e:
            logger.error(f"Failed to add default feed {url}: {str(e)}")
            results.append({'success': False, 'url': url, 'error': str(e)})
    
    return results

if __name__ == "__main__":
    # Test setup
    print("Setting up default feeds...")
    results = setup_default_feeds()
    
    for result in results:
        if result['success']:
            print(f"✓ Added feed {result.get('feed_title', 'Unknown')}")
        else:
            print(f"✗ Failed to add feed: {result.get('error', 'Unknown error')}")
    
    print("\nUpdating all feeds...")
    parser = FeedParser()
    update_results = parser.update_all_feeds()
    
    for result in update_results:
        if result['updated']:
            print(f"✓ Updated feed {result['feed_id']}: {result.get('items_added', 0)} items")
        else:
            print(f"- Feed {result['feed_id']} not updated (status: {result['status']})")