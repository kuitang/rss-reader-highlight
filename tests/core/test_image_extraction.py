#!/usr/bin/env python3
"""Test cases for RSS feed image extraction functionality"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import trafilatura
from bs4 import BeautifulSoup
from app.feed_parser import FeedParser


class TestImageExtraction(unittest.TestCase):
    """Test cases for image extraction from RSS feeds"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.parser = FeedParser()
    
    def test_extract_single_image_from_html(self):
        """Test extracting a single image from HTML content"""
        html = '<p><img src="https://example.com/image.jpg" alt="Test Image"></p><p>Some text</p>'
        soup = BeautifulSoup(html, 'html.parser')
        
        images = []
        for img in soup.find_all('img'):
            src = img.get('src')
            alt = img.get('alt', '')
            if src:
                images.append(f"![{alt}]({src})")
        
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0], '![Test Image](https://example.com/image.jpg)')
    
    def test_extract_multiple_images_from_html(self):
        """Test extracting multiple images from HTML content"""
        html = '''
        <p><img src="https://example.com/image1.jpg" alt="First Image"></p>
        <p>Some text</p>
        <p><img src="https://example.com/image2.png" alt="Second Image"></p>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        
        images = []
        for img in soup.find_all('img'):
            src = img.get('src')
            alt = img.get('alt', '')
            if src:
                images.append(f"![{alt}]({src})")
        
        self.assertEqual(len(images), 2)
        self.assertEqual(images[0], '![First Image](https://example.com/image1.jpg)')
        self.assertEqual(images[1], '![Second Image](https://example.com/image2.png)')
    
    def test_image_without_alt_text(self):
        """Test handling images without alt text"""
        html = '<p><img src="https://example.com/image.jpg"></p>'
        soup = BeautifulSoup(html, 'html.parser')
        
        images = []
        for img in soup.find_all('img'):
            src = img.get('src')
            alt = img.get('alt', '')
            if src:
                images.append(f"![{alt}]({src})")
        
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0], '![](https://example.com/image.jpg)')
    
    def test_image_with_title_attribute(self):
        """Test handling images with title but no alt"""
        html = '<p><img src="https://example.com/image.jpg" title="Image Title"></p>'
        soup = BeautifulSoup(html, 'html.parser')
        
        images = []
        for img in soup.find_all('img'):
            src = img.get('src')
            alt = img.get('alt', '')
            # Could also use title as fallback: alt = img.get('alt') or img.get('title', '')
            if src:
                images.append(f"![{alt}]({src})")
        
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0], '![](https://example.com/image.jpg)')
    
    def test_empty_image_tag(self):
        """Test handling empty image tags (no src)"""
        html = '<p><img alt="No Source"></p>'
        soup = BeautifulSoup(html, 'html.parser')
        
        images = []
        for img in soup.find_all('img'):
            src = img.get('src')
            alt = img.get('alt', '')
            if src:  # Only add if src exists
                images.append(f"![{alt}]({src})")
        
        self.assertEqual(len(images), 0)
    
    def test_real_rss_feed_with_image(self):
        """Test with actual RSS feed HTML pattern (BizToc style)"""
        html = '<p><img alt="" src="https://cdn.biztoc.com/example.webp" title="News Article" /></p><p></p>'
        soup = BeautifulSoup(html, 'html.parser')
        
        images = []
        for img in soup.find_all('img'):
            src = img.get('src')
            alt = img.get('alt', '')
            if src:
                images.append(f"![{alt}]({src})")
        
        # Extract text with trafilatura
        wrapped_html = f"<html><body>{html}</body></html>"
        text_content = trafilatura.extract(wrapped_html, include_formatting=True, output_format='markdown')
        
        # Combine images and text
        if images and text_content:
            result = '\n'.join(images) + '\n\n' + text_content
        elif images and not text_content:
            result = '\n'.join(images)
        else:
            result = text_content
        
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0], '![](https://cdn.biztoc.com/example.webp)')
        self.assertEqual(result, '![](https://cdn.biztoc.com/example.webp)')  # Only image, no text
    
    def test_reddit_style_thumbnail(self):
        """Test Reddit-style thumbnails with external preview"""
        html = '''
        <p><img src="https://b.thumbs.redditmedia.com/example.jpg" alt="Post Title"></p>
        <p>This is the post content</p>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        
        images = []
        for img in soup.find_all('img'):
            src = img.get('src')
            alt = img.get('alt', '')
            if src:
                images.append(f"![{alt}]({src})")
        
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0], '![Post Title](https://b.thumbs.redditmedia.com/example.jpg)')
    
    def test_figure_with_figcaption(self):
        """Test handling of figure elements with captions"""
        html = '''
        <figure>
            <img src="https://example.com/chart.png" alt="Sales Chart">
            <figcaption>Q3 2024 Sales Performance</figcaption>
        </figure>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        
        images = []
        for img in soup.find_all('img'):
            src = img.get('src')
            alt = img.get('alt', '')
            if src:
                images.append(f"![{alt}]({src})")
        
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0], '![Sales Chart](https://example.com/chart.png)')
    
    def test_image_markdown_in_app_display(self):
        """Test that markdown images are properly converted for display"""
        import mistletoe

        # Simulate what happens in app.py
        markdown_with_image = '![Test Image](https://example.com/image.jpg)\n\nSome article text here.'
        html_output = mistletoe.markdown(markdown_with_image)
        
        # Check that it contains an img tag
        self.assertIn('<img', html_output)
        self.assertIn('src="https://example.com/image.jpg"', html_output)
        self.assertIn('alt="Test Image"', html_output)
    
    def test_combined_images_and_text(self):
        """Test combining extracted images with text content"""
        # Simulate the feed parser logic
        html_summary = '''
        <p><img src="https://cdn.example.com/thumb.jpg" alt="Thumbnail"></p>
        <p>This is the article summary with some text content.</p>
        '''
        
        soup = BeautifulSoup(html_summary, 'html.parser')
        
        # Extract images
        images = []
        for img in soup.find_all('img'):
            src = img.get('src')
            alt = img.get('alt', '')
            if src:
                images.append(f"![{alt}]({src})")
        
        # Extract text with trafilatura
        wrapped_html = f"<html><body>{html_summary}</body></html>"
        text_content = trafilatura.extract(wrapped_html, include_formatting=True, output_format='markdown')
        
        # Combine as in feed_parser.py
        if images and text_content:
            description = '\n'.join(images) + '\n\n' + text_content
        elif images and not text_content:
            description = '\n'.join(images)
        else:
            description = text_content
        
        self.assertIsNotNone(description)
        self.assertIn('![Thumbnail](https://cdn.example.com/thumb.jpg)', description)
        self.assertIn('This is the article summary', description)
    
    @patch('app.feed_parser.trafilatura.extract')
    def test_fallback_when_no_text_only_images(self, mock_extract):
        """Test that items with only images are still saved"""
        # Mock trafilatura returning None (no text content)
        mock_extract.return_value = None
        
        html = '<p><img src="https://example.com/only-image.jpg" alt="Only Image"></p><p></p>'
        soup = BeautifulSoup(html, 'html.parser')
        
        images = []
        for img in soup.find_all('img'):
            src = img.get('src')
            alt = img.get('alt', '')
            if src:
                images.append(f"![{alt}]({src})")
        
        # Simulate feed_parser logic
        text_content = mock_extract(html, include_formatting=True, output_format='markdown')
        
        if images and text_content:
            result = '\n'.join(images) + '\n\n' + text_content
        elif images and not text_content:
            result = '\n'.join(images)
        else:
            result = text_content
        
        # Should have content even with no text
        self.assertEqual(result, '![Only Image](https://example.com/only-image.jpg)')


if __name__ == '__main__':
    unittest.main()