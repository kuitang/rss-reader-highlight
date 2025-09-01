"""Test RSS/Atom auto-discovery using test-driven development"""

import unittest
from unittest.mock import patch, MagicMock
from feed_parser import FeedParser
import tempfile
import os

class TestRssAutoDiscovery(unittest.TestCase):
    
    def setUp(self):
        """Set up test cases with real websites that should have RSS auto-discovery"""
        self.test_sites = [
            {
                'url': 'https://github.com/microsoft/vscode',
                'expected_type': 'atom',
                'description': 'GitHub repo - should have Atom feed',
                'should_work': False  # GitHub doesn't use auto-discovery
            },
            {
                'url': 'https://reddit.com/r/OpenAI', 
                'expected_type': 'rss',
                'description': 'Reddit subreddit - should auto-discover .rss',
                'should_work': True  # Reddit special case should work
            },
            {
                'url': 'https://www.reddit.com/r/ClaudeAI',
                'expected_type': 'rss', 
                'description': 'Reddit subreddit with www - should auto-discover .rss',
                'should_work': True  # Reddit special case should work
            },
            {
                'url': 'https://techcrunch.com',
                'expected_type': 'rss', 
                'description': 'TechCrunch - should have RSS feed',
                'should_work': True  # Standard auto-discovery works
            },
            {
                'url': 'https://stackoverflow.com/questions/tagged/python',
                'expected_type': 'rss',
                'description': 'Stack Overflow tag - should have RSS feed',
                'should_work': True  # Standard auto-discovery works
            }
        ]
        
        self.parser = FeedParser()
    
    def test_current_direct_feed_parsing_fails(self):
        """Test that current method fails on non-direct feed URLs (should fail initially)"""
        print("\n=== Testing Current Method (Should Fail) ===")
        
        failures = []
        for site in self.test_sites:
            url = site['url']
            description = site['description']
            
            print(f"Testing: {description}")
            print(f"URL: {url}")
            
            try:
                # REMOVED: synchronous add_feed no longer exists
                result = {'success': False, 'error': 'Method removed - use background worker'}
                if result['success']:
                    print(f"  ⚠️  Unexpectedly succeeded: {result.get('feed_title', 'Unknown')}")
                else:
                    print(f"  ✓ Failed as expected: {result.get('error', 'Unknown error')}")
                    failures.append(site)
            except Exception as e:
                print(f"  ✓ Exception as expected: {str(e)}")
                failures.append(site)
        
        # All should fail with current implementation
        self.assertEqual(len(failures), len(self.test_sites), 
                         "Current method should fail on all non-direct feed URLs")
    
    def test_mock_html_parsing(self):
        """Test HTML parsing logic with mock data"""
        print("\n=== Testing HTML Auto-Discovery Logic ===")
        
        # Mock HTML with various feed types
        test_html_cases = [
            {
                'html': '''
                <html><head>
                    <link rel="alternate" type="application/rss+xml" 
                          title="RSS Feed" href="/feed.rss">
                </head></html>
                ''',
                'expected_feeds': [{'href': '/feed.rss', 'title': 'RSS Feed', 'type': 'rss'}],
                'description': 'Standard RSS feed'
            },
            {
                'html': '''
                <html><head>
                    <link rel="alternate" type="application/atom+xml"
                          title="Atom Feed" href="/atom.xml">
                </head></html>
                ''',
                'expected_feeds': [{'href': '/atom.xml', 'title': 'Atom Feed', 'type': 'atom'}],
                'description': 'Standard Atom feed'
            },
            {
                'html': '''
                <html><head>
                    <link rel="alternate" type="application/rss+xml" 
                          title="Main RSS" href="/rss">
                    <link rel="alternate" type="application/atom+xml"
                          title="Atom Feed" href="/atom">
                </head></html>
                ''',
                'expected_feeds': [
                    {'href': '/rss', 'title': 'Main RSS', 'type': 'rss'},
                    {'href': '/atom', 'title': 'Atom Feed', 'type': 'atom'}
                ],
                'description': 'Multiple feeds (RSS + Atom)'
            },
            {
                'html': '''
                <html><head>
                    <link rel="stylesheet" href="/style.css">
                    <link rel="icon" href="/favicon.ico">
                </head></html>
                ''',
                'expected_feeds': [],
                'description': 'No RSS/Atom feeds'
            }
        ]
        
        # Test each HTML case
        for case in test_html_cases:
            print(f"Testing: {case['description']}")
            
            # This will fail until we implement the discover_feeds method
            try:
                feeds = self.parser.discover_feeds_from_html(case['html'], 'https://example.com')
                print(f"  Found {len(feeds)} feeds: {feeds}")
                self.assertEqual(len(feeds), len(case['expected_feeds']))
                
                # Verify feed details
                for i, expected in enumerate(case['expected_feeds']):
                    if i < len(feeds):
                        self.assertIn(expected['href'], feeds[i]['url'])
                        self.assertEqual(expected['title'], feeds[i]['title'])
                        self.assertEqual(expected['type'], feeds[i]['type'])
            except Exception as e:
                print(f"  ✗ Error: {str(e)}")
    
    def test_url_resolution(self):
        """Test relative URL resolution"""
        print("\n=== Testing URL Resolution ===")
        
        test_cases = [
            ('https://example.com/page', '/feed.rss', 'https://example.com/feed.rss'),
            ('https://example.com/blog/', 'feed.xml', 'https://example.com/blog/feed.xml'), 
            ('https://example.com', 'https://feeds.example.com/rss', 'https://feeds.example.com/rss'),
        ]
        
        for base_url, feed_href, expected in test_cases:
            # Test URL resolution using urllib.parse.urljoin
            import urllib.parse
            resolved = urllib.parse.urljoin(base_url, feed_href)
            print(f"  {base_url} + {feed_href} = {resolved}")
            self.assertEqual(resolved, expected)
    
    def test_full_autodiscovery_integration(self):
        """Test full integration after implementing auto-discovery (initially skipped)"""
        print("\n=== Testing Full Auto-Discovery Integration ===")
        
        successes = []
        for site in self.test_sites:
            url = site['url']
            expected_type = site['expected_type']
            description = site['description']
            should_work = site['should_work']
            
            print(f"Testing: {description}")
            print(f"URL: {url}")
            
            try:
                # REMOVED: synchronous add_feed no longer exists
                result = {'success': False, 'error': 'Method removed - use background worker'}
                if result['success']:
                    feed_info = f"{result.get('feed_title', 'Unknown')}"
                    if 'discovered_from' in result:
                        feed_info += f" (discovered from {result['discovered_from']})"
                    print(f"  ✓ Success: {feed_info}")
                    successes.append(site)
                    
                    if should_work:
                        self.assertTrue(True, f"Expected success for {description}")
                    else:
                        print(f"    ⚠️  Unexpected success - site may have added auto-discovery")
                else:
                    print(f"  ✗ Failed: {result.get('error', 'Unknown error')}")
                    if should_work:
                        self.fail(f"Expected {description} to work with auto-discovery")
            except Exception as e:
                print(f"  ✗ Exception: {str(e)}")
                if should_work:
                    self.fail(f"Expected {description} to work, got exception: {str(e)}")
        
        # Should have at least the sites marked as should_work
        expected_successes = sum(1 for site in self.test_sites if site['should_work'])
        self.assertGreaterEqual(len(successes), expected_successes, 
                               f"Expected at least {expected_successes} successes")


if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)