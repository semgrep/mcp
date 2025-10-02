"""
Secure Defaults - Query and recommend security libraries from awesome-secure-defaults.

This module provides functionality to search and recommend secure-by-default libraries
for various programming languages and security categories.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz


@lru_cache(maxsize=1)
def load_secure_defaults() -> list[dict[str, Any]]:
    """
    Load secure defaults data from JSON file.

    Returns:
        List of dictionaries containing library information.
        Each dict has: name, url, description, languages, category, keywords

    Raises:
        FileNotFoundError: If the data file cannot be found
        json.JSONDecodeError: If the data file is invalid JSON
    """
    data_file = Path(__file__).parent / "data" / "secure_defaults.json"

    if not data_file.exists():
        raise FileNotFoundError(f"Secure defaults data file not found: {data_file}")

    with open(data_file) as f:
        return json.load(f)


def search_secure_defaults(
    query: str | None = None,
    language: str | None = None,
    category: str | None = None,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """
    Search for secure default libraries based on query, language, and category.

    Args:
        query: Search query to match against library name, description, category, and keywords.
               Uses fuzzy matching to handle typos.
        language: Filter results by programming language (e.g., "Python", "JavaScript", "Go")
        category: Filter results by security category (e.g., "XSS", "CSRF", "Headers")
        max_results: Maximum number of results to return (default: 10)

    Returns:
        List of matching libraries, sorted by relevance score.
        Each library dict contains: name, url, description, languages, category, keywords

    Examples:
        >>> search_secure_defaults(query="XSS", language="Python")
        [{'name': 'mozilla/bleach', ...}]

        >>> search_secure_defaults(category="CSRF", language="Go")
        [{'name': 'gorilla/csrf', ...}]
    """
    libraries = load_secure_defaults()

    # Filter by language (case-insensitive, supports partial matches)
    if language:
        language_lower = language.lower()
        libraries = [
            lib
            for lib in libraries
            if any(language_lower in lang.lower() for lang in lib["languages"])
        ]

    # Filter by category (fuzzy matching for flexibility)
    if category:
        category_lower = category.lower()
        libraries = [
            lib
            for lib in libraries
            if fuzz.partial_ratio(category_lower, lib["category"].lower()) > 70
        ]

    # Search by query (fuzzy matching across multiple fields)
    if query:
        scored_libraries = []
        query_lower = query.lower()

        for lib in libraries:
            # Build searchable text from library fields
            searchable_text = " ".join(
                [
                    lib["name"],
                    lib["description"],
                    lib["category"],
                    *lib["keywords"],
                ]
            ).lower()

            # Calculate fuzzy match score
            score = fuzz.partial_ratio(query_lower, searchable_text)

            # Boost score if query matches category or name exactly
            if query_lower in lib["category"].lower():
                score += 30
            if query_lower in lib["name"].lower():
                score += 20

            scored_libraries.append((lib, score))

        # Sort by score (descending) and filter out low scores
        scored_libraries.sort(key=lambda x: x[1], reverse=True)
        libraries = [lib for lib, score in scored_libraries if score > 50]

    # Limit results
    return libraries[:max_results]


def format_recommendation(libraries: list[dict[str, Any]]) -> str:
    """
    Format library recommendations for display to users/AI agents.

    Args:
        libraries: List of library dictionaries to format

    Returns:
        Formatted string with library recommendations including:
        - Library name and URL
        - Description
        - Supported languages
        - Security category
        - Usage example (if applicable)

    Examples:
        >>> libs = [{'name': 'mozilla/bleach', 'url': '...', ...}]
        >>> print(format_recommendation(libs))
        Found 1 secure default library:
        ...
    """
    if not libraries:
        return "No secure default libraries found matching your criteria."

    plural = "y" if len(libraries) == 1 else "ies"
    result = [f"Found {len(libraries)} secure default librar{plural}:\n"]

    for i, lib in enumerate(libraries, 1):
        languages_str = ", ".join(lib["languages"])

        result.append(f"{i}. **{lib['name']}**")
        result.append(f"   URL: {lib['url']}")
        result.append(f"   Category: {lib['category']}")
        result.append(f"   Languages: {languages_str}")
        result.append(f"   Description: {lib['description']}")
        result.append("")  # Blank line between entries

    result.append("\nRecommendation:")
    result.append(
        "These libraries are curated from https://github.com/tldrsec/awesome-secure-defaults"
    )
    result.append(
        "They provide secure-by-default implementations that are easier to use correctly "
        "and harder to misuse."
    )

    return "\n".join(result)
