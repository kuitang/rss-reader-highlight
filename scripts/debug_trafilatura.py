#!/usr/bin/env python3
"""Debug trafilatura extraction issues"""

import feedparser
import trafilatura
import httpx

# Test with a simple feed that was failing
test_url = "https://feeds.feedburner.com/reuters/businessNews"

print("=== Debugging trafilatura extraction ===")
print(f"Testing feed: {test_url}")

# Fetch the feed
client = httpx.Client(follow_redirects=True)
response = client.get(test_url)
print(f"Feed fetch status: {response.status_code}")

# Parse with feedparser
feed_data = feedparser.parse(response.text)
print(f"Feed entries found: {len(feed_data.entries)}")

if feed_data.entries:
    entry = feed_data.entries[0]
    print(f"\n=== Testing first entry ===")
    print(f"Title: {entry.title}")
    
    if hasattr(entry, 'summary'):
        print(f"Summary length: {len(entry.summary)}")
        print(f"Summary type: {type(entry.summary)}")
        print(f"Summary preview: {entry.summary[:300]}...")
        
        print(f"\n=== Testing trafilatura.extract ===")
        try:
            result = trafilatura.extract(entry.summary, include_formatting=True, output_format='markdown')
            if result:
                print(f"SUCCESS: Extracted {len(result)} chars")
                print(f"Result preview: {result[:200]}...")
            else:
                print("FAILED: trafilatura.extract returned None")
                
                # Try different parameters
                print("\n=== Trying without include_formatting ===")
                result2 = trafilatura.extract(entry.summary, output_format='markdown')
                if result2:
                    print(f"SUCCESS: {len(result2)} chars without include_formatting")
                else:
                    print("FAILED: Still None without include_formatting")
                    
                # Try without output format
                print("\n=== Trying default extraction ===")
                result3 = trafilatura.extract(entry.summary)
                if result3:
                    print(f"SUCCESS: {len(result3)} chars with default extraction")
                else:
                    print("FAILED: Even default extraction returned None")
                    
        except Exception as e:
            print(f"EXCEPTION: {str(e)}")
            
    else:
        print("No summary found in entry")
        
client.close()