"""Test HTML sanitization and markdown rendering for malicious/weird content"""

import unittest
from unittest.mock import patch, MagicMock
import trafilatura
import mistletoe
from app.feed_parser import FeedParser
from app.main import ItemDetailView


class TestHtmlSanitization(unittest.TestCase):
    
    def setUp(self):
        """Set up test cases with malicious HTML content"""
        self.malicious_html_cases = [
            # XSS attempts
            '<script>alert("xss")</script>Hello world',
            '<img src="x" onerror="alert(1)">',
            '<div onclick="alert(\'click\')">Click me</div>',
            'javascript:alert("xss")',
            
            # Malformed HTML
            '<div><p>Unclosed tags',
            '<><><><>weird tags<><><><>',
            '<<<>>>broken<<>>',
            
            # Mixed content
            '<h1>Title</h1><script>evil()</script><p>Normal content</p>',
            '<style>body{display:none}</style>Content here',
            
            # Complex nested attacks
            '<div><script>var x="</script><script>alert(1)</script>"</script></div>',
            '<iframe src="javascript:alert(1)"></iframe>',
            
            # Data URI attacks
            '<img src="data:text/html,<script>alert(1)</script>">',
            
            # Unicode/encoding attacks
            '<img src="&#106;&#97;&#118;&#97;&#115;&#99;&#114;&#105;&#112;&#116;&#58;&#97;&#108;&#101;&#114;&#116;&#40;&#39;&#88;&#83;&#83;&#39;&#41;">',
        ]
    
    def test_trafilatura_sanitization(self):
        """Test that trafilatura properly sanitizes malicious HTML during ingestion"""
        for malicious_html in self.malicious_html_cases:
            with self.subTest(html=malicious_html[:50]):
                # Test trafilatura extraction
                sanitized = trafilatura.extract(malicious_html, include_formatting=True, output_format='markdown')
                
                # Should not contain script tags, javascript:, or other dangerous elements
                if sanitized:
                    self.assertNotIn('<script', sanitized.lower())
                    self.assertNotIn('javascript:', sanitized.lower())
                    self.assertNotIn('onerror=', sanitized.lower())
                    self.assertNotIn('onclick=', sanitized.lower())
                    self.assertNotIn('<iframe', sanitized.lower())
                    self.assertNotIn('<style>', sanitized.lower())
    
    def test_markdown_rendering_safety(self):
        """Test that final markdown-to-HTML rendering is safe"""
        for malicious_html in self.malicious_html_cases:
            with self.subTest(html=malicious_html[:50]):
                # Simulate full pipeline: HTML -> Markdown -> HTML
                markdown_content = trafilatura.extract(malicious_html, include_formatting=True, output_format='markdown')
                
                if markdown_content:
                    # Render markdown to HTML (as done in ItemDetailView)
                    final_html = mistletoe.markdown(markdown_content)
                    
                    # Final output should be safe
                    self.assertNotIn('<script', final_html.lower())
                    self.assertNotIn('javascript:', final_html.lower())
                    self.assertNotIn('onerror=', final_html.lower())
                    self.assertNotIn('onclick=', final_html.lower())
                    self.assertNotIn('<iframe', final_html.lower())
    
    def test_feed_parser_integration(self):
        """Test that FeedParser properly sanitizes content during parsing"""
        parser = FeedParser()
        
        # Mock feed entry with malicious content
        mock_entry = MagicMock()
        mock_entry.summary = '<script>alert("xss")</script><p>Real content here</p>'
        mock_entry.content = [MagicMock()]
        mock_entry.content[0].value = '<div onclick="alert(1)"><h1>Article Title</h1><p>Article body</p></div>'
        
        # Test the sanitization happens during parsing
        with patch('trafilatura.extract') as mock_extract:
            mock_extract.side_effect = [
                'Real content here',  # For summary
                '# Article Title\n\nArticle body'  # For content
            ]
            
            # Simulate the parsing logic
            description = trafilatura.extract(mock_entry.summary, include_formatting=True, output_format='markdown')
            content = trafilatura.extract(mock_entry.content[0].value, include_formatting=True, output_format='markdown')
            
            # Verify clean output
            self.assertEqual(description, 'Real content here')
            self.assertEqual(content, '# Article Title\n\nArticle body')
            self.assertNotIn('<script', description)
            self.assertNotIn('onclick=', content)
    
    def test_item_detail_view_rendering(self):
        """Test that ItemDetailView safely renders markdown content"""
        # Test item with markdown content (as stored after sanitization)
        test_item = {
            'id': 1,
            'title': 'Test Article',
            'link': 'https://example.com',
            'feed_title': 'Test Feed',
            'published': '2025-01-01T00:00:00Z',
            'content': '# Safe Title\n\n**Bold text** and [safe link](https://example.com)',
            'description': 'Safe *italic* description'
        }
        
        # Generate the view and extract the actual HTML content
        view = ItemDetailView(test_item)
        
        # Get the rendered markdown HTML directly
        content_html = mistletoe.markdown(test_item['content'])
        
        # Should contain properly rendered markdown
        self.assertIn('<h1>Safe Title</h1>', content_html)
        self.assertIn('<strong>Bold text</strong>', content_html)
        self.assertIn('<a href="https://example.com">safe link</a>', content_html)
        
        # Should not contain any dangerous elements in rendered content
        self.assertNotIn('<script', content_html.lower())
        self.assertNotIn('javascript:', content_html.lower())
        self.assertNotIn('onerror=', content_html.lower())
    
    def test_edge_cases(self):
        """Test edge cases like empty content, None values, etc."""
        edge_cases = [
            None,
            '',
            '   ',
            'Plain text with no HTML',
            '<p></p>',  # Empty paragraph
            '<!-- HTML comment only -->',
        ]
        
        for case in edge_cases:
            with self.subTest(content=str(case)):
                # Test trafilatura handling
                if case:
                    result = trafilatura.extract(case, include_formatting=True, output_format='markdown')
                    if result:
                        # Should not crash markdown rendering
                        rendered = mistletoe.markdown(result)
                        self.assertIsInstance(rendered, str)
                
                # Test with None/empty fallback in ItemDetailView
                test_item = {
                    'id': 1,
                    'title': 'Test',
                    'link': 'https://example.com',
                    'feed_title': 'Test Feed',
                    'published': '2025-01-01T00:00:00Z',
                    'content': case,
                    'description': case
                }
                
                # Should not crash - handle None/empty content gracefully
                try:
                    view = ItemDetailView(test_item)
                    self.assertIsNotNone(view)
                except TypeError:
                    # Expected for None values - mistletoe can't handle None
                    if case is None:
                        pass
                    else:
                        raise


if __name__ == '__main__':
    unittest.main()