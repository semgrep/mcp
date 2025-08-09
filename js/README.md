# Semgrep MCP Server - TypeScript Implementation

This is the TypeScript/JavaScript implementation of the Semgrep MCP Server using the official MCP SDK.

## Installation

1. Navigate to the js folder:
   ```bash
   cd js
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Build the project:
   ```bash
   npm run build
   ```

## Usage

Run the server:
```bash
npm start
```

Or for development:
```bash
npm run dev
```

## Available Scripts

- `npm run build` - Build the TypeScript project
- `npm start` - Run the compiled JavaScript server
- `npm run dev` - Run the TypeScript server with tsx
- `npm test` - Run tests
- `npm run lint` - Run ESLint
- `npm run typecheck` - Run TypeScript type checking

## Features

The TypeScript implementation provides the same functionality as the Python version:

### Tools
- `semgrep_scan` - Run Semgrep scan on code content
- `semgrep_scan_with_custom_rule` - Run scan with custom rule
- `security_check` - Fast security check
- `semgrep_findings` - Fetch findings from Semgrep AppSec Platform
- `get_supported_languages` - Get supported languages
- `get_abstract_syntax_tree` - Get AST for code
- `semgrep_rule_schema` - Get Semgrep rule schema

### Prompts
- `write_custom_semgrep_rule` - Generate custom Semgrep rules

### Resources
- `semgrep://rule/schema` - Semgrep rule schema

## Environment Variables

- `SEMGREP_API_TOKEN` - Required for accessing Semgrep AppSec Platform
- `SEMGREP_URL` - Semgrep API URL (defaults to https://semgrep.dev)

## Requirements

- Node.js 18+
- Semgrep CLI installed and available in PATH