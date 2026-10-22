"""Consolidated feed ingestion tests - RSS/Atom parsing, Reddit special cases, and autodiscovery

Combines functionality from:
- test_reddit_special_case.py
- test_rss_autodiscovery.py
- RSS/Atom format parsing
- HTTP redirect handling
"""

import pytest
from unittest.mock import patch, MagicMock
import httpx
from app.feed_parser import FeedParser


class TestFeedIngestion:
    """Test feed ingestion including Reddit special cases and RSS autodiscovery"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Exercise real HTTP client/redirect/parser behavior with fixed upstream replies.

        CI must validate ingestion independently of Reddit rate limits, upstream
        outages, or changing discovery pages. Unknown requests fail closed.
        """
        self.parser = FeedParser()
        self.requests = []
        rss = """<?xml version="1.0"?><rss version="2.0"><channel>
            <title>Fixture RSS</title><description>Test feed</description>
            <item><title>Fixture item</title><link>https://example.com/item</link>
            <description>Fixture article</description></item>
            </channel></rss>"""
        atom = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
            <title>Fixture Atom</title><entry><title>Fixture entry</title>
            <id>fixture-entry</id><link href="https://example.com/entry"/>
            </entry></feed>"""

        def respond(request):
            self.requests.append(str(request.url))
            assert request.method == 'GET'
            host, path = request.url.host, request.url.path
            if host in {'reddit.com', 'www.reddit.com', 'old.reddit.com'} and path.startswith('/r/'):
                if path.endswith('/.rss'):
                    return httpx.Response(200, text=rss, headers={'content-type': 'application/rss+xml'})
                return httpx.Response(200, text='<html><head></head><body>Subreddit</body></html>')
            if host == 'techcrunch.com':
                if path == '/':
                    return httpx.Response(200, text='<link rel="alternate" type="application/rss+xml" href="/feed/" title="TechCrunch">')
                if path == '/feed/':
                    return httpx.Response(200, text=rss, headers={'content-type': 'application/rss+xml'})
            if host == 'stackoverflow.com':
                if path == '/questions/tagged/python':
                    return httpx.Response(200, text='<link rel="alternate" type="application/atom+xml" href="/feeds/tag/python" title="Python">')
                if path == '/feeds/tag/python':
                    return httpx.Response(200, text=atom, headers={'content-type': 'application/atom+xml'})
            if host == 'github.com' and path == '/microsoft/vscode':
                return httpx.Response(200, text='<html><head></head><body>No alternate feed</body></html>')
            if host == 'feeds.bbci.co.uk' and path == '/news/rss.xml':
                if request.url.scheme == 'http':
                    return httpx.Response(302, headers={'location': 'https://feeds.bbci.co.uk/news/rss.xml'})
                return httpx.Response(200, text=rss, headers={'content-type': 'application/rss+xml'})
            raise AssertionError(f'Unexpected ingestion fixture request: {request.url}')

        original = self.parser.client
        # Preserve the production client's redirect policy and headers so a
        # regression in FeedParser's configuration still breaks these tests.
        self.parser.client = httpx.Client(
            transport=httpx.MockTransport(respond),
            follow_redirects=original.follow_redirects,
            headers=original.headers,
            timeout=original.timeout,
        )
        original.close()
        yield
        self.parser.client.close()

    @pytest.mark.parametrize('url', [
        'https://reddit.com/r/OpenAI',
        'https://www.reddit.com/r/ClaudeAI',
        'https://reddit.com/r/vibecoding/',
        'https://www.reddit.com/r/MicroSaaS/',
        'https://old.reddit.com/r/Python',
        'https://reddit.com/r/programming',
    ])
    def test_reddit_rss_suffix_detection(self, url):
        """All supported Reddit URL forms retain the expected /.rss suffix."""
        expected = url.rstrip('/') + '/.rss'
        assert self.parser._try_reddit_rss_suffix(url) == expected
        result = self.parser.fetch_feed(expected)
        assert result['updated'] and result['status'] == 200
        assert len(result['data'].entries) == 1
        assert self.requests == [expected, expected]

    @pytest.mark.parametrize('url,expected,feed_type', [
        ('https://reddit.com/r/OpenAI', 'https://reddit.com/r/OpenAI/.rss', 'rss'),
        ('https://www.reddit.com/r/ClaudeAI', 'https://www.reddit.com/r/ClaudeAI/.rss', 'rss'),
        ('https://techcrunch.com', 'https://techcrunch.com/feed/', 'rss'),
        ('https://stackoverflow.com/questions/tagged/python', 'https://stackoverflow.com/feeds/tag/python', 'atom'),
    ])
    def test_rss_autodiscovery_success_cases(self, url, expected, feed_type):
        """Use real HTML discovery and Reddit fallback, then parse the result."""
        discovered = self.parser.discover_feeds(url)
        assert len(discovered) == 1
        assert discovered[0]['url'] == expected
        assert discovered[0]['type'] == feed_type
        result = self.parser.fetch_feed(expected)
        assert result['updated'] and result['status'] == 200
        assert len(result['data'].entries) == 1

    def test_rss_autodiscovery_failure_cases(self):
        """Pages without alternate links return no feeds without inventing a URL."""
        assert self.parser.discover_feeds('https://github.com/microsoft/vscode') == []
        assert self.requests == ['https://github.com/microsoft/vscode']

    # Feed Format Parsing Tests
    def test_fetch_feed_success(self):
        """Test successful feed fetching with real FeedParser method"""
        # Mock httpx response for RSS feed
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Test RSS Feed</title>
                <description>A test RSS feed</description>
                <item>
                    <title>Test Item</title>
                    <description>Test description</description>
                    <link>https://example.com/item1</link>
                </item>
            </channel>
        </rss>"""
        mock_response.headers = {}
        
        with patch.object(self.parser.client, 'get', return_value=mock_response):
            result = self.parser.fetch_feed("https://example.com/rss")
            
            assert result['updated']
            assert result['status'] == 200
            assert 'data' in result
            # feedparser should parse the RSS content
            assert hasattr(result['data'], 'entries')
            assert result['data'].feed.title == "Test RSS Feed"
    
    def test_fetch_atom_feed_success(self):
        """Test fetching Atom format feeds with real FeedParser method"""
        # Mock httpx response for Atom feed
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <title>Test Atom Feed</title>
            <subtitle>A test Atom feed</subtitle>
            <entry>
                <title>Test Entry</title>
                <summary>Test summary</summary>
                <link href="https://example.com/entry1"/>
            </entry>
        </feed>"""
        mock_response.headers = {}
        
        with patch.object(self.parser.client, 'get', return_value=mock_response):
            result = self.parser.fetch_feed("https://example.com/atom")
            
            assert result['updated']
            assert result['status'] == 200
            assert 'data' in result
            # feedparser should parse the Atom content
            assert hasattr(result['data'], 'entries')
            assert result['data'].feed.title == "Test Atom Feed"
    
    # HTTP Redirect Handling Tests
    def test_http_redirect_handling(self):
        """The actual configured client follows BBC's HTTP to HTTPS redirect."""
        original = 'http://feeds.bbci.co.uk/news/rss.xml'
        final = 'https://feeds.bbci.co.uk/news/rss.xml'
        result = self.parser.fetch_feed(original)
        assert result['updated'] and result['status'] == 200
        assert len(result['data'].entries) == 1
        assert self.requests == [original, final]

    def test_fetch_feed_with_network_error(self):
        """Test handling of network errors with real FeedParser method"""
        # Mock httpx to raise network error
        with patch.object(self.parser.client, 'get', side_effect=httpx.ConnectError("Connection failed")):
            result = self.parser.fetch_feed("https://nonexistent-domain.com/rss")
            
            # Should handle gracefully
            assert not result['updated']
            assert result.get('status') == 0
            assert result.get('data') is None
            assert 'error' in result
    
    def test_fetch_feed_with_http_error(self):
        """Test handling of HTTP errors (404, 500, etc.) with real FeedParser method"""
        # Mock httpx response with error status
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.headers = {}
        
        with patch.object(self.parser.client, 'get', return_value=mock_response):
            result = self.parser.fetch_feed("https://example.com/nonexistent.rss")
            
            # Should handle HTTP errors gracefully
            assert not result['updated']
            assert result['status'] == 404
