# Secure Defaults Tool Documentation

## Overview

The `secure_defaults` tool is a new MCP (Model Context Protocol) tool that provides security-focused library recommendations and Semgrep rulesets based on user queries. It leverages the curated list from the [awesome-secure-defaults](https://github.com/tldrsec/awesome-secure-defaults) repository to recommend secure-by-default libraries.

## Features

- **Library Recommendations**: Suggests secure libraries based on security requirements
- **Semgrep Ruleset Matching**: Provides relevant Semgrep rulesets for secure implementation
- **Best Practice Notes**: Includes security best practices relevant to the query
- **Smart Caching**: Caches GitHub data for 24 hours to improve performance
- **Confidence Scoring**: Provides confidence scores for recommendations

## Usage

### Tool Signature

```python
@mcp.tool()
async def secure_defaults(
    query: str = Field(description="Query describing the security requirement or library needed"),
) -> SecureDefaultRecommendation
```

### Example Queries

```python
# JWT/Authentication
"I'm looking for a secure default auth library for flask that uses JWT"

# XSS Prevention
"What's a good XSS prevention library for React?"

# Password Hashing
"Recommend secure password hashing for Python"

# CSRF Protection
"Need CSRF protection for Django application"

# SQL Injection Prevention
"Looking for secure SQL query builder for Node.js"

# Encryption
"Need encryption library for storing sensitive data in Java"
```

## Response Structure

The tool returns a `SecureDefaultRecommendation` object containing:

```python
class SecureDefaultRecommendation(BaseModel):
    query: str                                    # Original user query
    recommended_libraries: list[SecureLibrary]    # Top 5 matching libraries
    semgrep_rulesets: list[SemgrepRuleset]       # Top 3 relevant rulesets
    best_practice_notes: list[str]               # Up to 5 best practices
    confidence_score: float                      # Confidence score (0-1)
```

### SecureLibrary Structure

```python
class SecureLibrary(BaseModel):
    name: str                        # Library name
    description: str                 # What the library does
    repository_url: HttpUrl | None  # GitHub repository URL
    languages: list[str]            # Supported programming languages
    category: str                   # Security category (e.g., 'XSS Prevention')
    github_stars: int | None        # Number of GitHub stars
    last_updated: str | None        # Last update date
```

### SemgrepRuleset Structure

```python
class SemgrepRuleset(BaseModel):
    name: str                  # Ruleset name
    url: HttpUrl | None       # URL to the ruleset
    description: str          # What the ruleset covers
    relevance_score: float    # Relevance to query (0-1)
```

## Implementation Details

### Data Source

The tool fetches data from the [awesome-secure-defaults](https://github.com/tldrsec/awesome-secure-defaults) repository, which contains a curated list of security-focused libraries across multiple programming languages.

### Matching Algorithm

1. **Query Processing**: Extracts keywords from the user query
2. **Library Scoring**: Scores libraries based on:
   - Name match (40% weight)
   - Description match (30% weight)
   - Category match (20% weight)
   - Language match (10% weight)
3. **Ruleset Matching**: Matches Semgrep rulesets based on:
   - Query keywords
   - Recommended library languages
   - Security category relevance

### Caching Strategy

- Data is cached for 24 hours to reduce API calls
- Cache is automatically refreshed when expired
- Falls back to cached data if GitHub is unavailable

### Best Practices Generation

The tool generates contextual best practices based on detected security topics:
- JWT/Token security
- Password hashing
- XSS prevention
- SQL injection prevention
- CSRF protection
- Cryptography

## Error Handling

The tool includes comprehensive error handling for:
- Network failures (HTTP errors)
- Parsing errors
- Invalid queries
- GitHub API unavailability

## Testing

A test script is provided at `/test_secure_defaults.py` that validates:
- Various query types
- Cache functionality
- Error handling
- Response structure

## Future Enhancements

Potential improvements for future versions:
1. Support for additional data sources beyond awesome-secure-defaults
2. Machine learning-based relevance scoring
3. Integration with vulnerability databases
4. Custom ruleset generation based on library choice
5. Language-specific best practices
6. Version compatibility checking