#!/usr/bin/env python3
"""Test script for the secure_defaults MCP tool."""

import asyncio
import json
from semgrep_mcp.server import secure_defaults, fetch_secure_defaults_data


async def test_secure_defaults():
    """Test the secure_defaults tool with various queries."""
    
    test_queries = [
        "I'm looking for a secure default auth library for flask that uses JWT",
        "What's a good XSS prevention library for React?",
        "Recommend secure password hashing for Python",
        "Need CSRF protection for Django application",
        "Looking for secure SQL query builder for Node.js",
        "Need encryption library for storing sensitive data in Java",
    ]
    
    print("Testing secure_defaults tool...")
    print("=" * 60)
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        print("-" * 40)
        
        try:
            result = await secure_defaults(query)
            
            print(f"Confidence Score: {result.confidence_score:.2f}")
            print(f"Recommended Libraries: {len(result.recommended_libraries)}")
            
            for lib in result.recommended_libraries[:2]:  # Show first 2
                print(f"  - {lib.name} ({lib.category})")
                if lib.languages:
                    print(f"    Languages: {', '.join(lib.languages)}")
            
            print(f"Semgrep Rulesets: {len(result.semgrep_rulesets)}")
            for ruleset in result.semgrep_rulesets:
                print(f"  - {ruleset.name} (relevance: {ruleset.relevance_score:.2f})")
            
            if result.best_practice_notes:
                print("Best Practices:")
                for note in result.best_practice_notes[:2]:  # Show first 2
                    print(f"  - {note}")
                    
        except Exception as e:
            print(f"ERROR: {e}")
    
    print("\n" + "=" * 60)
    print("Testing cache functionality...")
    
    # Test cache
    data1 = await fetch_secure_defaults_data()
    data2 = await fetch_secure_defaults_data()  # Should use cache
    
    if data1 == data2:
        print("✓ Cache is working correctly")
    else:
        print("✗ Cache might not be working")
    
    print(f"Total libraries in cache: {len(data1)}")


if __name__ == "__main__":
    asyncio.run(test_secure_defaults())