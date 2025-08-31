"""RSS/Atom feed parsing and updating logic"""

import feedparser
import httpx
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dateutil import parser as date_parser
import logging
import trafilatura
from bs4 import BeautifulSoup
import urllib.parse
from models import FeedModel, FeedItemModel

import os
# Configure logging level from environment variable
log_level = getattr(logging, os.environ.get('LOG_LEVEL', 'INFO').upper(), logging.INFO)
logging.basicConfig(level=log_level)
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
    
    def discover_feeds_from_html(self, html_content: str, base_url: str) -> List[Dict]:
        """Parse HTML to discover RSS/Atom feeds via link rel=alternate tags"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            feeds = []
            
            # Look for RSS and Atom auto-discovery links
            feed_links = soup.find_all('link', rel='alternate')
            
            for link in feed_links:
                feed_type = link.get('type', '').lower()
                
                # Check for RSS or Atom MIME types
                if feed_type in ['application/rss+xml', 'application/atom+xml']:
                    href = link.get('href')
                    title = link.get('title', 'RSS Feed')
                    
                    if href:
                        # Resolve relative URLs to absolute
                        absolute_url = urllib.parse.urljoin(base_url, href)
                        feeds.append({
                            'url': absolute_url,
                            'title': title,
                            'type': 'rss' if 'rss' in feed_type else 'atom'
                        })
            
            return feeds
            
        except Exception as e:
            logger.warning(f"Error parsing HTML for feed discovery: {str(e)}")
            return []
    
    def discover_feeds(self, url: str) -> List[Dict]:
        """Discover RSS/Atom feeds from a webpage URL"""
        try:
            response = self.client.get(url)
            
            if response.status_code != 200:
                logger.warning(f"Failed to fetch page for feed discovery: {url} - HTTP {response.status_code}")
                return []
            
            # Standard auto-discovery via HTML link tags
            discovered = self.discover_feeds_from_html(response.text, url)
            
            # Reddit special case: if no feeds found and URL contains reddit.com
            if not discovered and 'reddit.com' in url.lower():
                reddit_feed_url = self._try_reddit_rss_suffix(url)
                if reddit_feed_url:
                    discovered.append({
                        'url': reddit_feed_url,
                        'title': 'Reddit RSS Feed',
                        'type': 'rss'
                    })
            
            return discovered
            
        except Exception as e:
            logger.warning(f"Error discovering feeds from {url}: {str(e)}")
            return []
    
    def _try_reddit_rss_suffix(self, url: str) -> Optional[str]:
        """Try adding .rss suffix for Reddit URLs"""
        try:
            # Handle various Reddit URL formats
            if url.endswith('/'):
                test_url = url + '.rss'
            else:
                test_url = url + '/.rss'
            
            # Test if the RSS URL actually works
            response = self.client.get(test_url)
            if response.status_code == 200:
                # Quick check if it's actually RSS content
                if 'xml' in response.headers.get('content-type', '').lower() or \
                   'rss' in response.text[:200].lower() or \
                   '<?xml' in response.text[:100]:
                    return test_url
            
            return None
            
        except Exception as e:
            logger.warning(f"Error testing Reddit RSS suffix for {url}: {str(e)}")
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
                    
                    # Get description and content, sanitize HTML and convert to Markdown
                    description = None
                    content = None
                    
                    if hasattr(entry, 'summary'):
                        # Convert HTML summary to clean Markdown
                        logger.debug(f"Processing summary for entry: {title[:50]}...")
                        logger.debug(f"Summary content type: {type(entry.summary)}")
                        logger.debug(f"Summary length: {len(entry.summary) if entry.summary else 0}")
                        logger.debug(f"Summary preview: {entry.summary[:200] if entry.summary else 'None'}...")
                        
                        try:
                            # Wrap fragment in complete HTML document for trafilatura
                            wrapped_html = f"<html><body>{entry.summary}</body></html>"
                            description = trafilatura.extract(wrapped_html, include_formatting=True, output_format='markdown')
                            if description:
                                logger.debug(f"Trafilatura extraction successful: {len(description)} chars")
                            else:
                                # Final fallback: use BeautifulSoup for simple text extraction
                                from bs4 import BeautifulSoup
                                soup = BeautifulSoup(entry.summary, 'html.parser')
                                text_content = soup.get_text(strip=True)
                                if text_content and len(text_content) > 10:  # Only use if meaningful content
                                    description = text_content
                                    logger.debug(f"Using BeautifulSoup fallback: {len(description)} chars")
                                else:
                                    logger.error(f"Trafilatura extract returned None for '{title}' - FULL XML ENTRY: {entry}")
                                    continue  # Skip this entry entirely
                        except Exception as e:
                            logger.error(f"Trafilatura extract failed for '{title}': {str(e)} - FULL XML ENTRY: {entry}")
                            continue  # Skip this entry entirely
                    
                    if hasattr(entry, 'content') and entry.content:
                        # Take the first content entry
                        content_entry = entry.content[0] if isinstance(entry.content, list) else entry.content
                        raw_content = content_entry.value if hasattr(content_entry, 'value') else str(content_entry)
                        
                        # Convert HTML content to clean Markdown
                        logger.debug(f"Processing content for entry: {title[:50]}...")
                        logger.debug(f"Content type: {type(raw_content)}")
                        logger.debug(f"Content length: {len(raw_content) if raw_content else 0}")
                        logger.debug(f"Content preview: {raw_content[:200] if raw_content else 'None'}...")
                        
                        try:
                            # Wrap fragment in complete HTML document for trafilatura
                            wrapped_content = f"<html><body>{raw_content}</body></html>"
                            content = trafilatura.extract(wrapped_content, include_formatting=True, output_format='markdown')
                            if content:
                                logger.debug(f"Trafilatura content extraction successful: {len(content)} chars")
                            else:
                                # Final fallback: use BeautifulSoup for simple text extraction
                                from bs4 import BeautifulSoup
                                soup = BeautifulSoup(raw_content, 'html.parser')
                                text_content = soup.get_text(strip=True)
                                if text_content and len(text_content) > 10:  # Only use if meaningful content
                                    content = text_content
                                    logger.debug(f"Using BeautifulSoup content fallback: {len(content)} chars")
                                else:
                                    logger.error(f"Trafilatura content extract returned None for '{title}' - FULL XML ENTRY: {entry}")
                                    continue  # Skip this entry entirely
                        except Exception as e:
                            logger.error(f"Trafilatura content extract failed for '{title}': {str(e)} - FULL XML ENTRY: {entry}")
                            continue  # Skip this entry entirely
                    
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
        """Add new feed with auto-discovery support"""
        try:
            # FIRST: Try direct feed parsing
            fetch_result = self.fetch_feed(url)
            
            if fetch_result['updated'] and fetch_result['status'] == 200:
                # Check if it's a valid feed
                feed_data = fetch_result['data']
                if hasattr(feed_data, 'feed') and hasattr(feed_data, 'entries'):
                    feed_title = getattr(feed_data.feed, 'title', None)
                    if feed_title:
                        # Direct feed URL works - proceed normally
                        feed_id = FeedModel.create_feed(url, feed_title)
                        result = self.parse_and_store_feed(feed_id, url)
                        
                        if not result['updated']:
                            return {
                                'success': False,
                                'error': 'Feed parsing failed after creation'
                            }
                        
                        return {
                            'success': True,
                            'feed_id': feed_id,
                            'feed_title': feed_title,
                            **result
                        }
            
            # SECOND: If direct parsing failed, try auto-discovery
            logger.info(f"Direct feed parsing failed for {url}, trying auto-discovery...")
            discovered_feeds = self.discover_feeds(url)
            
            if not discovered_feeds:
                return {
                    'success': False,
                    'error': 'No RSS/Atom feeds found via auto-discovery'
                }
            
            # THIRD: Try the first discovered feed
            primary_feed = discovered_feeds[0]
            feed_url = primary_feed['url']
            
            logger.info(f"Found feed via auto-discovery: {feed_url}")
            
            # Try to parse the discovered feed
            fetch_result = self.fetch_feed(feed_url)
            
            if not fetch_result['updated'] or fetch_result['status'] != 200:
                return {
                    'success': False,
                    'error': f"Cannot fetch discovered feed: HTTP {fetch_result['status']}"
                }
            
            # Verify discovered feed has parseable content
            feed_data = fetch_result['data']
            if not hasattr(feed_data, 'feed') or not hasattr(feed_data, 'entries'):
                return {
                    'success': False, 
                    'error': 'Discovered feed has invalid RSS/Atom format'
                }
            
            # Get feed metadata
            feed_title = getattr(feed_data.feed, 'title', None) or primary_feed['title']
            if not feed_title:
                return {
                    'success': False,
                    'error': 'Discovered feed has no title'
                }
            
            # Create feed with discovered URL
            feed_id = FeedModel.create_feed(feed_url, feed_title)
            
            # Store the articles
            result = self.parse_and_store_feed(feed_id, feed_url)
            
            if not result['updated']:
                return {
                    'success': False,
                    'error': 'Feed parsing failed after creation'
                }
            
            return {
                'success': True,
                'feed_id': feed_id,
                'feed_title': feed_title,
                'discovered_from': url,
                'feed_url': feed_url,
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
        "https://feeds.feedburner.com/reuters/businessNews",  # BizToc
        "https://feeds.bloomberg.com/economics/news.rss",  # Bloomberg Economics
        "https://feeds.bloomberg.com/markets/news.rss",  # Bloomberg Markets
        "https://www.ft.com/rss/home",  # Financial Times
        "https://hnrss.org/frontpage",  # Hacker News
        "https://www.reddit.com/r/ClaudeAI/.rss",  # ClaudeAI subreddit
        "https://www.reddit.com/r/MicroSaaS/.rss",  # MicroSaaS subreddit (larger one)
        "https://www.reddit.com/r/OpenAI/.rss",  # OpenAI subreddit
        "https://www.reddit.com/r/all/.rss",  # Reddit All
        "https://www.reddit.com/r/vibecoding/.rss",  # vibecoding subreddit
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