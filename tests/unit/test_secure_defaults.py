"""
Unit tests for secure_defaults module.
"""

import json

import pytest

from semgrep_mcp.secure_defaults import (
    format_recommendation,
    load_secure_defaults,
    search_secure_defaults,
)


class TestLoadSecureDefaults:
    """Tests for load_secure_defaults function"""

    def test_load_returns_list(self):
        """Test that load_secure_defaults returns a list"""
        result = load_secure_defaults()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_load_returns_valid_structure(self):
        """Test that loaded data has correct structure"""
        result = load_secure_defaults()
        first_lib = result[0]

        # Check required fields
        assert "name" in first_lib
        assert "url" in first_lib
        assert "description" in first_lib
        assert "languages" in first_lib
        assert "category" in first_lib
        assert "keywords" in first_lib

        # Check field types
        assert isinstance(first_lib["name"], str)
        assert isinstance(first_lib["url"], str)
        assert isinstance(first_lib["description"], str)
        assert isinstance(first_lib["languages"], list)
        assert isinstance(first_lib["category"], str)
        assert isinstance(first_lib["keywords"], list)

    def test_load_uses_cache(self):
        """Test that load_secure_defaults caches results"""
        result1 = load_secure_defaults()
        result2 = load_secure_defaults()

        # Should return the same object (cached)
        assert result1 is result2

    def test_all_libraries_have_urls(self):
        """Test that all libraries have valid GitHub URLs"""
        libraries = load_secure_defaults()
        for lib in libraries:
            assert lib["url"].startswith("http")
            assert "github" in lib["url"] or "git.hardenedbsd.org" in lib["url"]


class TestSearchSecureDefaults:
    """Tests for search_secure_defaults function"""

    def test_search_without_filters_returns_all(self):
        """Test searching without filters returns limited results"""
        result = search_secure_defaults(max_results=100)
        assert len(result) > 0
        assert len(result) <= 100

    def test_search_with_max_results(self):
        """Test max_results parameter limits output"""
        result = search_secure_defaults(max_results=5)
        assert len(result) <= 5

    def test_search_by_language_python(self):
        """Test filtering by Python language"""
        result = search_secure_defaults(language="Python")
        assert len(result) > 0

        for lib in result:
            languages_lower = [lang.lower() for lang in lib["languages"]]
            assert any("python" in lang for lang in languages_lower)

    def test_search_by_language_javascript(self):
        """Test filtering by JavaScript language"""
        result = search_secure_defaults(language="JavaScript")
        assert len(result) > 0

        for lib in result:
            languages_lower = [lang.lower() for lang in lib["languages"]]
            assert any("javascript" in lang or "nodejs" in lang for lang in languages_lower)

    def test_search_by_language_go(self):
        """Test filtering by Go language"""
        result = search_secure_defaults(language="Go")
        assert len(result) > 0

        for lib in result:
            languages_lower = [lang.lower() for lang in lib["languages"]]
            assert any("go" in lang for lang in languages_lower)

    def test_search_by_language_case_insensitive(self):
        """Test language search is case-insensitive"""
        result_lower = search_secure_defaults(language="python")
        result_upper = search_secure_defaults(language="PYTHON")
        result_mixed = search_secure_defaults(language="Python")

        assert len(result_lower) > 0
        assert len(result_lower) == len(result_upper)
        assert len(result_lower) == len(result_mixed)

    def test_search_by_category_xss(self):
        """Test filtering by XSS category"""
        result = search_secure_defaults(category="XSS")
        assert len(result) > 0

        # Should include libraries with XSS-related categories
        categories_found = {lib["category"] for lib in result}
        assert any("XSS" in cat or "HTML Sanitizer" in cat for cat in categories_found)

    def test_search_by_category_csrf(self):
        """Test filtering by CSRF category"""
        result = search_secure_defaults(category="CSRF")
        assert len(result) > 0

        for lib in result:
            assert "csrf" in lib["category"].lower()

    def test_search_by_category_headers(self):
        """Test filtering by Headers category"""
        result = search_secure_defaults(category="Headers")
        assert len(result) > 0

        for lib in result:
            assert "headers" in lib["category"].lower()

    def test_search_by_category_fuzzy_match(self):
        """Test category search uses fuzzy matching"""
        # "Header" should match "Headers"
        result = search_secure_defaults(category="Header")
        assert len(result) > 0

    def test_search_by_query_xss(self):
        """Test query search for XSS"""
        result = search_secure_defaults(query="XSS")
        assert len(result) > 0

        # Should find libraries related to XSS
        found_bleach = any("bleach" in lib["name"].lower() for lib in result)
        found_dompurify = any("dompurify" in lib["name"].lower() for lib in result)
        assert found_bleach or found_dompurify

    def test_search_by_query_cryptography(self):
        """Test query search for cryptography"""
        result = search_secure_defaults(query="cryptography")
        assert len(result) > 0

        # Should find crypto-related libraries
        categories_found = {lib["category"] for lib in result}
        assert any("crypt" in cat.lower() for cat in categories_found)

    def test_search_by_query_sanitize(self):
        """Test query search for sanitization"""
        result = search_secure_defaults(query="sanitize")
        assert len(result) > 0

        # Should find sanitizer libraries
        descriptions = " ".join(lib["description"] for lib in result).lower()
        assert "sanitiz" in descriptions

    def test_search_by_query_fuzzy_match(self):
        """Test query search handles typos with fuzzy matching"""
        # "santize" (typo) should still find sanitization libraries
        result = search_secure_defaults(query="santize")
        assert len(result) > 0

    def test_search_combined_query_and_language(self):
        """Test combining query and language filters"""
        result = search_secure_defaults(query="sanitize", language="Python")
        assert len(result) > 0

        # Should find Python sanitizer libraries
        for lib in result:
            languages_lower = [lang.lower() for lang in lib["languages"]]
            assert any("python" in lang for lang in languages_lower)

        # Should include bleach or similar
        found_relevant = any(
            "bleach" in lib["name"].lower() or "sanitiz" in lib["description"].lower()
            for lib in result
        )
        assert found_relevant

    def test_search_combined_category_and_language(self):
        """Test combining category and language filters"""
        result = search_secure_defaults(category="Headers", language="Python")
        assert len(result) > 0

        for lib in result:
            assert "headers" in lib["category"].lower()
            languages_lower = [lang.lower() for lang in lib["languages"]]
            assert any("python" in lang for lang in languages_lower)

    def test_search_combined_all_filters(self):
        """Test combining query, category, and language filters"""
        result = search_secure_defaults(query="header", category="Headers", language="Python")

        if len(result) > 0:
            for lib in result:
                assert "headers" in lib["category"].lower()
                languages_lower = [lang.lower() for lang in lib["languages"]]
                assert any("python" in lang for lang in languages_lower)

    def test_search_no_results(self):
        """Test search returns empty list when no matches"""
        result = search_secure_defaults(language="NonexistentLanguage")
        assert result == []

    def test_search_query_no_results(self):
        """Test query search returns empty list when no matches"""
        result = search_secure_defaults(query="xyznonexistentlibrary123")
        assert result == []


class TestFormatRecommendation:
    """Tests for format_recommendation function"""

    def test_format_empty_list(self):
        """Test formatting empty library list"""
        result = format_recommendation([])
        assert "No secure default libraries found" in result

    def test_format_single_library(self):
        """Test formatting single library"""
        libraries = [
            {
                "name": "mozilla/bleach",
                "url": "https://github.com/mozilla/bleach",
                "description": "HTML sanitizer",
                "languages": ["Python"],
                "category": "XSS",
                "keywords": ["xss", "sanitizer"],
            }
        ]

        result = format_recommendation(libraries)

        assert "Found 1 secure default library:" in result
        assert "mozilla/bleach" in result
        assert "https://github.com/mozilla/bleach" in result
        assert "HTML sanitizer" in result
        assert "Python" in result
        assert "XSS" in result
        assert "awesome-secure-defaults" in result

    def test_format_multiple_libraries(self):
        """Test formatting multiple libraries"""
        libraries = [
            {
                "name": "mozilla/bleach",
                "url": "https://github.com/mozilla/bleach",
                "description": "HTML sanitizer",
                "languages": ["Python"],
                "category": "XSS",
                "keywords": ["xss"],
            },
            {
                "name": "cure53/DOMPurify",
                "url": "https://github.com/cure53/DOMPurify",
                "description": "XSS sanitizer",
                "languages": ["JavaScript"],
                "category": "XSS",
                "keywords": ["xss"],
            },
        ]

        result = format_recommendation(libraries)

        assert "Found 2 secure default libraries:" in result
        assert "mozilla/bleach" in result
        assert "cure53/DOMPurify" in result
        assert "1." in result
        assert "2." in result

    def test_format_includes_recommendation_text(self):
        """Test that formatted output includes recommendation text"""
        libraries = [
            {
                "name": "test/lib",
                "url": "https://github.com/test/lib",
                "description": "Test library",
                "languages": ["Python"],
                "category": "Test",
                "keywords": ["test"],
            }
        ]

        result = format_recommendation(libraries)

        assert "Recommendation:" in result
        assert "awesome-secure-defaults" in result
        assert "secure-by-default" in result

    def test_format_handles_multiple_languages(self):
        """Test formatting library with multiple languages"""
        libraries = [
            {
                "name": "google/tink",
                "url": "https://github.com/tink-crypto",
                "description": "Multi-language crypto library",
                "languages": ["Java", "C++", "Go", "Python"],
                "category": "Cryptography",
                "keywords": ["crypto"],
            }
        ]

        result = format_recommendation(libraries)

        assert "Java, C++, Go, Python" in result or "Java" in result


class TestIntegration:
    """Integration tests for complete workflows"""

    def test_search_and_format_python_xss(self):
        """Test searching and formatting Python XSS libraries"""
        libraries = search_secure_defaults(query="XSS", language="Python", max_results=5)
        result = format_recommendation(libraries)

        assert len(libraries) > 0
        assert "Found" in result
        assert "secure default librar" in result

    def test_search_and_format_go_csrf(self):
        """Test searching and formatting Go CSRF libraries"""
        libraries = search_secure_defaults(category="CSRF", language="Go")
        result = format_recommendation(libraries)

        assert len(libraries) > 0
        assert "gorilla" in result.lower() or "csrf" in result.lower()

    def test_common_use_case_headers(self):
        """Test common use case: finding security header libraries"""
        libraries = search_secure_defaults(category="Headers", max_results=10)

        assert len(libraries) > 0
        # Should find libraries for multiple languages
        all_languages = set()
        for lib in libraries:
            all_languages.update(lib["languages"])

        # Should have headers libraries for at least a few different languages
        assert len(all_languages) >= 3

    def test_common_use_case_sanitization(self):
        """Test common use case: finding HTML sanitizers"""
        libraries = search_secure_defaults(query="HTML sanitizer", max_results=10)

        assert len(libraries) > 0
        # Should find sanitizers for multiple languages
        languages_found = set()
        for lib in libraries:
            languages_found.update(lib["languages"])

        assert "Python" in languages_found or "JavaScript" in languages_found


class TestEdgeCases:
    """Tests for edge cases and error handling"""

    def test_max_results_zero(self):
        """Test max_results=0 returns empty list"""
        result = search_secure_defaults(max_results=0)
        assert result == []

    def test_max_results_negative(self):
        """Test max_results with negative value"""
        result = search_secure_defaults(max_results=-1)
        # Should handle gracefully (empty list or limited results)
        assert isinstance(result, list)

    def test_empty_query_string(self):
        """Test search with empty query string"""
        result = search_secure_defaults(query="")
        # Empty query should return results (acts like no filter)
        assert isinstance(result, list)

    def test_whitespace_query(self):
        """Test search with whitespace-only query"""
        result = search_secure_defaults(query="   ")
        assert isinstance(result, list)

    def test_special_characters_in_query(self):
        """Test search with special characters"""
        result = search_secure_defaults(query="C++")
        # Should handle special characters gracefully
        assert isinstance(result, list)

    def test_unicode_in_query(self):
        """Test search with unicode characters"""
        result = search_secure_defaults(query="cryptographié")
        # Should handle unicode gracefully
        assert isinstance(result, list)
