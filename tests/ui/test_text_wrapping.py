"""Test text wrapping and URL handling to prevent horizontal scrolling on mobile"""

import pytest

class TestTextWrapping:
    """Test text wrapping and URL handling functionality - standalone tests"""
    
    def test_comprehensive_ui_fixes(self):
        """Comprehensive test of all UI fixes implemented"""
        # Test URL processing function with contrived long URLs
        from app import process_urls_in_content
        
        # Create test content with multiple scenarios
        test_cases = [
            # Long URLs that would cause horizontal scrolling
            "Check this out: https://example.com/this-is-an-extremely-long-url-path-that-goes-on-and-on-and-would-definitely-cause-horizontal-scrolling-on-mobile-devices-if-not-handled-properly/path/to/resource?param1=very-long-parameter-value&param2=another-long-value",
            
            # Multiple URLs in one text
            """Here are multiple problematic URLs:
            First: https://super-long-domain-name.com/very/long/path/structure/that/could/break/layout
            Second: https://another-example.org/supercalifragilisticexpialidocious-url-name/more/paths
            Third: https://final-test.net/extremely-long-query-string?param=value&another=very-long-parameter-value""",
            
            # Mixed content with URLs
            "Normal text with a problematic URL https://test.com/very-very-very-long-url-that-should-be-replaced and more text after.",
        ]
        
        for i, test_content in enumerate(test_cases):
            print(f"\nTesting case {i+1}: {test_content[:50]}...")
            
            # Process the content
            processed = process_urls_in_content(test_content)
            
            # Verify URL replacement occurred
            assert '🔗' in processed, f"Case {i+1}: Should contain external link emoji"
            assert '📋' in processed, f"Case {i+1}: Should contain copy button emoji"
            assert 'cursor-pointer' in processed, f"Case {i+1}: Should be clickable"
            assert 'uk-btn' in processed, f"Case {i+1}: Should use MonsterUI button classes"
            
            # Verify original plain URLs are not visible (unless in href attributes)
            import re
            url_pattern = r'https?://[^\s<>"\']+(?=[^>]*(?:<|$))'
            plain_urls = re.findall(url_pattern, processed)
            # URLs should only appear in href attributes now
            for url in plain_urls:
                assert f'href="{url}"' in processed, f"Case {i+1}: URL {url} should be in href attribute"
            
            print(f"✓ Case {i+1} passed")
        
        # Test edge cases
        edge_cases = [
            "",  # Empty content
            "No URLs here",  # No URLs
            "Just text",  # Plain text
            "https://short.com",  # Short URL
        ]
        
        for edge_case in edge_cases:
            processed = process_urls_in_content(edge_case)
            # Should not crash and should return something reasonable
            assert isinstance(processed, str), f"Should return string for: {edge_case}"
        
        print("✓ All URL processing tests passed")
    
    def test_css_rules_applied(self):
        """Test that CSS rules for text wrapping and touch targets exist"""
        # Verify that viewport_styles function contains the right CSS rules
        from app import viewport_styles
        
        css_style = viewport_styles()
        css_content = str(css_style)
        
        # Check for text wrapping rules
        assert 'word-wrap: break-word' in css_content, "Should have word-wrap rule"
        assert 'overflow-wrap: break-word' in css_content, "Should have overflow-wrap rule"
        assert 'word-break: break-word' in css_content, "Should have word-break rule"
        assert 'max-width: 100%' in css_content, "Should have max-width rule"
        
        # Check for horizontal scroll prevention
        assert 'overflow-x: hidden' in css_content, "Should prevent horizontal overflow"
        assert 'max-width: 100vw' in css_content, "Should limit to viewport width"
        
        # Check for minimum touch target size
        assert 'min-height: 44px' in css_content, "Should have minimum height for touch targets"
        assert 'min-width: 44px' in css_content, "Should have minimum width for touch targets"
        
        print("✓ All CSS rules are properly implemented")
    
    def test_monsterui_components_used(self):
        """Test that MonsterUI components are used instead of raw HTML"""
        from app import process_urls_in_content
        
        test_url = "https://example.com/test"
        processed = process_urls_in_content(f"Check this: {test_url}")
        
        # Should use MonsterUI components, not raw HTML strings
        assert 'DivLAligned' in str(processed) or 'uk-btn' in processed, "Should use MonsterUI Button components"
        assert '🔗' in processed, "Should use emoji for external link"
        
        # Should not contain raw HTML strings
        assert '<svg class="w-4 h-4"' not in processed, "Should not contain raw HTML SVG"
        
        print("✓ MonsterUI components are used correctly")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])