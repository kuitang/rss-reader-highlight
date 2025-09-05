"""Unit tests for smart_truncate_html function"""

import pytest
from app import smart_truncate_html

class TestSmartTruncateHtml:
    """Test the smart HTML truncation function"""
    
    def test_markdown_image_conversion(self):
        """Test that markdown images get converted to HTML img tags"""
        markdown_text = "![Alt text](https://example.com/very/long/image/url/with/lots/of/parameters.jpg?param1=value1&param2=value2)"
        
        result = smart_truncate_html(markdown_text, 300)
        
        # Should convert to HTML img tag
        assert '<img' in result, "Markdown image should be converted to HTML img tag"
        assert 'alt="Alt text"' in result, "Alt text should be preserved"
        assert 'src="https://example.com' in result, "Image URL should be preserved"
        assert '![' not in result, "Raw markdown syntax should be gone"
        
    def test_image_with_text_truncation(self):
        """Test that text gets truncated but images are preserved"""
        long_text = "This is a very long text that should be truncated. " * 10  # 500+ chars
        markdown_with_image = f"![Test image](https://example.com/image.jpg)\n\n{long_text}"
        
        result = smart_truncate_html(markdown_with_image, 100)  # Short limit
        
        # Image should be preserved regardless of text limit
        assert '<img' in result, "Image should be preserved even with short text limit"
        assert 'src="https://example.com/image.jpg"' in result, "Image URL should be complete"
        
        # Text should be truncated
        assert len(result.replace('<img', '').replace('src=', '')) < len(markdown_with_image), "Text content should be truncated"
        
    def test_multiple_images_preservation(self):
        """Test that multiple images are all preserved"""
        # Remove leading whitespace that causes mistletoe to treat as code block
        markdown_text = """![Image 1](https://example.com/img1.jpg)

Some text between images.

![Image 2](https://example.com/img2.jpg)

More text here that could be truncated."""
        
        result = smart_truncate_html(markdown_text, 50)  # Very short limit
        
        # Both images should be preserved
        assert result.count('<img') == 2, f"Both images should be preserved, got: {result}"
        assert 'img1.jpg' in result, "First image should be preserved"
        assert 'img2.jpg' in result, "Second image should be preserved"
        
    def test_text_only_truncation(self):
        """Test truncation behavior with text-only content"""
        text_only = "This is regular text without images. " * 20  # Long text
        
        result = smart_truncate_html(text_only, 100)
        
        # Should be truncated HTML
        assert len(result) < len(text_only), "Text should be truncated"
        assert '<p>' in result, "Should be wrapped in HTML paragraph"
        assert '...' in result or len(result) <= 120, "Should have truncation indicator or be within limit"
        
    def test_empty_and_none_input(self):
        """Test edge cases with empty/None input"""
        assert smart_truncate_html("") == "No content available"
        assert smart_truncate_html(None) == "No content available"
        
    def test_visible_text_counting(self):
        """Test that truncation counts only visible text, not image URLs"""
        # Long image URL but short visible text
        short_text_long_url = "![Image](https://this-is-a-very-long-image-url-with-many-parameters.example.com/path/to/image.jpg?param1=verylongvalue&param2=anotherlongvalue&param3=evenlonger)\n\nShort text."
        
        result = smart_truncate_html(short_text_long_url, 50)  # Should fit visible text
        
        # Image should be preserved (URL length doesn't matter)
        assert '<img' in result, "Image should be preserved regardless of URL length"
        assert 'Short text' in result, "Short text should be included"
        
        # Get just the text content to verify counting
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(result, 'html.parser')
        visible_text = soup.get_text()
        
        # Visible text should be short (image URL shouldn't count toward limit)
        assert len(visible_text) <= 60, f"Visible text should be short, got: '{visible_text}'"
        
if __name__ == "__main__":
    pytest.main([__file__, "-v"])