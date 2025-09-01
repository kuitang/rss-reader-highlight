"""Test Reddit special case RSS detection"""

import unittest
from feed_parser import FeedParser

class TestRedditSpecialCase(unittest.TestCase):
    
    def setUp(self):
        self.parser = FeedParser()
        
        self.reddit_urls = [
            'https://reddit.com/r/OpenAI',
            'https://www.reddit.com/r/ClaudeAI', 
            'https://reddit.com/r/vibecoding/',
            'https://www.reddit.com/r/MicroSaaS/',
            'https://old.reddit.com/r/Python',
            'https://reddit.com/r/programming'
        ]
    
    def test_reddit_rss_suffix_detection(self):
        """Test that Reddit URLs get .rss suffix added correctly"""
        print("\n=== Testing Reddit RSS Suffix Detection ===")
        
        for url in self.reddit_urls:
            print(f"Testing: {url}")
            
            try:
                # Test the internal method
                reddit_feed_url = self.parser._try_reddit_rss_suffix(url)
                
                if reddit_feed_url:
                    print(f"  ✓ Found RSS: {reddit_feed_url}")
                    
                    # Verify it's a working RSS feed
                    fetch_result = self.parser.fetch_feed(reddit_feed_url)
                    self.assertTrue(fetch_result['updated'], f"RSS feed should be fetchable: {reddit_feed_url}")
                    self.assertEqual(fetch_result['status'], 200, f"RSS feed should return 200: {reddit_feed_url}")
                    
                    # Verify it contains RSS content
                    feed_data = fetch_result['data']
                    self.assertTrue(hasattr(feed_data, 'entries'), f"Should have entries: {reddit_feed_url}")
                    self.assertGreater(len(feed_data.entries), 0, f"Should have at least one entry: {reddit_feed_url}")
                else:
                    print(f"  ✗ No RSS found")
                    self.fail(f"Expected to find RSS feed for {url}")
                    
            except Exception as e:
                print(f"  ✗ Exception: {str(e)}")
                self.fail(f"Exception testing {url}: {str(e)}")
    
    def test_reddit_autodiscovery_integration(self):
        """Test that Reddit URLs work through the full add_feed pipeline"""
        print("\n=== Testing Reddit Auto-Discovery Integration ===")
        
        # Test one Reddit URL through full pipeline
        test_url = 'https://reddit.com/r/Python'
        print(f"Testing full pipeline: {test_url}")
        
        try:
            # REMOVED: synchronous add_feed no longer exists - background worker handles feed addition
            result = {'success': False, 'error': 'Method removed - use background worker'}
            
            self.assertTrue(result['success'], f"Should successfully add Reddit feed: {result.get('error', 'Unknown error')}")
            self.assertIn('discovered_from', result, "Should indicate feed was discovered")
            self.assertEqual(result['discovered_from'], test_url, "Should track original URL")
            self.assertTrue(result['feed_url'].endswith('.rss'), "Should use .rss URL")
            
            print(f"  ✓ Success: {result.get('feed_title', 'Unknown')}")
            print(f"  ✓ Discovered from: {result.get('discovered_from')}")
            print(f"  ✓ Feed URL: {result.get('feed_url')}")
            
        except Exception as e:
            print(f"  ✗ Exception: {str(e)}")
            self.fail(f"Exception in full pipeline test: {str(e)}")
    
    def test_non_reddit_urls_unchanged(self):
        """Test that non-Reddit URLs don't trigger special case"""
        print("\n=== Testing Non-Reddit URLs ===")
        
        non_reddit_urls = [
            'https://techcrunch.com',
            'https://stackoverflow.com/questions/tagged/python',
            'https://github.com/microsoft/vscode'
        ]
        
        for url in non_reddit_urls:
            print(f"Testing non-Reddit URL: {url}")
            
            # Should return None for _try_reddit_rss_suffix
            reddit_result = self.parser._try_reddit_rss_suffix(url)
            print(f"  Reddit suffix result: {reddit_result}")
            
            # Should not trigger Reddit special case
            if 'reddit.com' not in url.lower():
                self.assertIsNone(reddit_result, f"Non-Reddit URL should not trigger Reddit special case: {url}")


if __name__ == '__main__':
    unittest.main(verbosity=2)