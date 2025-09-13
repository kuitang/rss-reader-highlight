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
from .models import FeedModel, FeedItemModel

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
                    
                    if hasattr(entry, 'summary') and entry.summary:
                        # Convert HTML summary to clean Markdown
                        logger.debug(f"Processing summary for entry: {title[:50]}...")
                        logger.debug(f"Summary content type: {type(entry.summary)}")
                        logger.debug(f"Summary length: {len(entry.summary) if entry.summary else 0}")
                        logger.debug(f"Summary preview: {entry.summary[:200] if entry.summary else 'None'}...")
                        
                        # Extract images first using BeautifulSoup
                        from bs4 import BeautifulSoup
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
                        published = self.parse_date(entry.published)
                    elif hasattr(entry, 'updated'):
                        published = self.parse_date(entry.updated)
                    
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
    
    
    def _extract_description_with_images(self, html_summary: str) -> str:
        """Extract description with images from HTML summary"""
        # Extract images first using BeautifulSoup
        soup = BeautifulSoup(html_summary, 'html.parser')
        images = []
        for img in soup.find_all('img'):
            src = img.get('src')
            alt = img.get('alt', '')
            if src:
                # Create markdown image syntax: ![alt text](url)
                images.append(f"![{alt}]({src})")
        
        # Extract text content with trafilatura
        wrapped_html = f"<html><body>{html_summary}</body></html>"
        description = trafilatura.extract(wrapped_html, include_formatting=True, output_format='markdown')
        
        # Combine images and text
        if images and description:
            # Add images at the beginning of the description
            return '\n'.join(images) + '\n\n' + description
        elif images and not description:
            # If only images, use them as description
            return '\n'.join(images)
        elif description:
            return description
        else:
            return None
    
    def _extract_content_with_images(self, raw_content: str) -> str:
        """Extract content with images from HTML content"""
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
                return paragraphs[0] + '\n\n' + '\n'.join(images) + '\n\n' + '\n\n'.join(paragraphs[1:])
            else:
                # Add images at the beginning
                return '\n'.join(images) + '\n\n' + content
        elif images and not content:
            # If only images, use them as content
            return '\n'.join(images)
        elif content:
            return content
        else:
            return None

    def __del__(self):
        """Clean up HTTP client"""
        if hasattr(self, 'client'):
            self.client.close()

def setup_default_feeds(minimal_mode=False):
    """Set up default RSS feeds - FAST database records only, background worker handles content"""
    if minimal_mode:
        # Minimal set for testing - just 2 feeds
        default_feeds = [
            ("https://hnrss.org/frontpage", "Hacker News: Front Page"),
            ("https://www.reddit.com/r/ClaudeAI/.rss", "ClaudeAI")
        ]
    else:
        # Full set for production
        default_feeds = [
            ("https://feeds.bloomberg.com/economics/news.rss", "Bloomberg Economics"),
            ("https://feeds.bloomberg.com/markets/news.rss", "Bloomberg Markets"),
            ("https://www.ft.com/rss/home", "Financial Times"),
            ("https://hnrss.org/frontpage", "Hacker News"),
            ("https://www.reddit.com/r/ClaudeAI/.rss", "ClaudeAI"),
            ("https://www.reddit.com/r/MicroSaaS/.rss", "MicroSaaS"),
            ("https://www.reddit.com/r/OpenAI/.rss", "OpenAI"),
            ("https://www.reddit.com/r/all/.rss", "Reddit All"),
            ("https://www.reddit.com/r/vibecoding/.rss", "VibeCoding"),
            ("https://feeds.content.dowjones.io/public/rss/RSSMarketsMain", "WSJ Markets"),
            ("https://techcrunch.com/feed/", "TechCrunch"),
            ("https://stackoverflow.com/feeds/tag?tagnames=python&sort=newest", "Python Q&A"),
            ("https://reddit.com/r/Python/.rss", "Python")
        ]
    
    results = []
    feeds_created = 0
    
    for url, title in default_feeds:
        try:
            # FAST: Only create database record if not exists
            if not FeedModel.feed_exists_by_url(url):
                feed_id = FeedModel.create_feed(url, title)
                feeds_created += 1
                logger.info(f"Created default feed record: {title} ({url})")
                results.append({'success': True, 'feed_id': feed_id, 'url': url, 'title': title})
            else:
                logger.debug(f"Default feed already exists: {title}")
                results.append({'success': True, 'url': url, 'title': title, 'already_exists': True})
                
        except Exception as e:
            logger.error(f"Failed to create default feed {title}: {str(e)}")
            results.append({'success': False, 'url': url, 'title': title, 'error': str(e)})
    
    mode_text = "minimal mode" if minimal_mode else "normal mode"
    if feeds_created > 0:
        logger.info(f"Fast startup ({mode_text}): Created {feeds_created} default feed records (background worker will fetch content)")
    else:
        logger.info(f"Fast startup ({mode_text}): All default feeds already exist")
    
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