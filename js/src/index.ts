#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ErrorCode,
  ListToolsRequestSchema,
  McpError,
  GetPromptRequestSchema,
  ListPromptsRequestSchema,
  ListResourcesRequestSchema,
  ReadResourceRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { spawn } from 'child_process';
import { mkdtemp, writeFile, rmdir } from 'fs/promises';
import { join, dirname, resolve, normalize, relative, isAbsolute } from 'path';
import { tmpdir } from 'os';
import { existsSync } from 'fs';
import { promisify } from 'util';

import { 
  CodeFile, 
  SemgrepScanResult, 
  Finding, 
  CodeWithLanguage 
} from './models.js';

const VERSION = '0.4.1';
const DEFAULT_TIMEOUT = 300000; // 5 minutes in milliseconds

const SEMGREP_URL = process.env.SEMGREP_URL || 'https://semgrep.dev';
const SEMGREP_API_URL = `${SEMGREP_URL}/api`;
const SEMGREP_API_VERSION = 'v1';

// Global variables
let semgrepExecutable: string | null = null;
let deploymentSlug: string | null = null;

// Utilities
function safeJoin(baseDir: string, untrustedPath: string): string {
  const basePath = resolve(baseDir);
  
  if (!untrustedPath || untrustedPath === '.' || untrustedPath.trim().replace(/\//g, '') === '') {
    return basePath;
  }
  
  if (isAbsolute(untrustedPath)) {
    throw new Error('Untrusted path must be relative');
  }
  
  const fullPath = resolve(basePath, untrustedPath);
  
  if (!fullPath.startsWith(basePath)) {
    throw new Error(`Untrusted path escapes the base directory: ${untrustedPath}`);
  }
  
  return fullPath;
}

function validateAbsolutePath(pathToValidate: string, paramName: string): string {
  if (!isAbsolute(pathToValidate)) {
    throw new McpError(
      ErrorCode.InvalidParams,
      `${paramName} must be an absolute path. Received: ${pathToValidate}`
    );
  }
  
  const normalizedPath = normalize(pathToValidate);
  
  if (resolve(normalizedPath) !== normalizedPath) {
    throw new McpError(
      ErrorCode.InvalidParams,
      `${paramName} contains invalid path traversal sequences`
    );
  }
  
  return normalizedPath;
}

function validateConfig(config?: string): string | undefined {
  if (!config || config.startsWith('p/') || config.startsWith('r/') || config === 'auto') {
    return config;
  }
  
  return validateAbsolutePath(config, 'config');
}

function findSemgrepPath(): string | null {
  const commonPaths = [
    'semgrep',
    '/usr/local/bin/semgrep',
    '/usr/bin/semgrep',
    '/opt/homebrew/bin/semgrep',
    '/opt/semgrep/bin/semgrep',
    '/home/linuxbrew/.linuxbrew/bin/semgrep',
    '/snap/bin/semgrep',
  ];
  
  if (process.platform === 'win32') {
    const appData = process.env.APPDATA;
    if (appData) {
      commonPaths.push(
        join(appData, 'Python', 'Scripts', 'semgrep.exe'),
        join(appData, 'npm', 'semgrep.cmd')
      );
    }
  }
  
  for (const semgrepPath of commonPaths) {
    if (semgrepPath === 'semgrep') {
      try {
        const result = spawn('semgrep', ['--version'], { stdio: 'pipe' });
        if (result.pid) {
          return semgrepPath;
        }
      } catch {
        continue;
      }
    }
    
    if (isAbsolute(semgrepPath) && existsSync(semgrepPath)) {
      return semgrepPath;
    }
  }
  
  return null;
}

async function ensureSemgrepAvailable(): Promise<string> {
  if (semgrepExecutable) {
    return semgrepExecutable;
  }
  
  const semgrepPath = findSemgrepPath();
  
  if (!semgrepPath) {
    throw new McpError(
      ErrorCode.InternalError,
      'Semgrep is not installed or not in your PATH. ' +
      'Please install Semgrep manually before using this tool. ' +
      'Installation options: ' +
      'pip install semgrep, ' +
      'macOS: brew install semgrep, ' +
      'Or refer to https://semgrep.dev/docs/getting-started/'
    );
  }
  
  semgrepExecutable = semgrepPath;
  return semgrepPath;
}

async function createTempFilesFromCodeContent(codeFiles: CodeFile[]): Promise<string> {
  const tempDir = await mkdtemp(join(tmpdir(), 'semgrep_scan_'));
  
  try {
    for (const fileInfo of codeFiles) {
      if (!fileInfo.filename) {
        continue;
      }
      
      const tempFilePath = safeJoin(tempDir, fileInfo.filename);
      const dirPath = dirname(tempFilePath);
      
      // Create directory if it doesn't exist
      await import('fs').then(fs => fs.promises.mkdir(dirPath, { recursive: true }));
      
      await writeFile(tempFilePath, fileInfo.content);
    }
    
    return tempDir;
  } catch (error) {
    await rmdir(tempDir, { recursive: true });
    throw new McpError(
      ErrorCode.InternalError,
      `Failed to create temporary files: ${error}`
    );
  }
}

function getSemgrepScanArgs(tempDir: string, config?: string): string[] {
  const args = ['scan', '--json', '--experimental'];
  if (config) {
    args.push('--config', config);
  }
  args.push(tempDir);
  return args;
}

function validateCodeFiles(codeFiles: CodeFile[]): void {
  if (!codeFiles || codeFiles.length === 0) {
    throw new McpError(
      ErrorCode.InvalidParams,
      'code_files must be a non-empty list of file objects'
    );
  }
  
  for (const file of codeFiles) {
    if (!file.filename || !file.content) {
      throw new McpError(
        ErrorCode.InvalidParams,
        'Each code file must have filename and content properties'
      );
    }
    
    if (isAbsolute(file.filename)) {
      throw new McpError(
        ErrorCode.InvalidParams,
        'code_files.filename must be a relative path'
      );
    }
  }
}

async function runSemgrep(args: string[]): Promise<string> {
  const semgrepPath = await ensureSemgrepAvailable();
  
  return new Promise((resolve, reject) => {
    const process = spawn(semgrepPath, args, { stdio: 'pipe' });
    
    let stdout = '';
    let stderr = '';
    
    process.stdout?.on('data', (data) => {
      stdout += data.toString();
    });
    
    process.stderr?.on('data', (data) => {
      stderr += data.toString();
    });
    
    process.on('close', (code) => {
      if (code !== 0) {
        reject(new McpError(
          ErrorCode.InternalError,
          `Error running semgrep: (${code}) ${stderr}`
        ));
      } else {
        resolve(stdout);
      }
    });
    
    process.on('error', (error) => {
      reject(new McpError(
        ErrorCode.InternalError,
        `Failed to spawn semgrep process: ${error}`
      ));
    });
  });
}

function removeTempDirFromResults(results: SemgrepScanResult, tempDir: string): void {
  for (const finding of results.results) {
    if (finding.path) {
      try {
        finding.path = relative(tempDir, finding.path);
      } catch {
        // Skip if path is not relative to temp_dir
      }
    }
  }
  
  if (results.paths.scanned) {
    results.paths.scanned = results.paths.scanned.map((path: string) => 
      relative(tempDir, path)
    );
  }
  
  if (results.paths.skipped) {
    results.paths.skipped = results.paths.skipped.map((path: string) => 
      relative(tempDir, path)
    );
  }
}

async function getDeploymentSlug(): Promise<string> {
  if (deploymentSlug) {
    return deploymentSlug;
  }
  
  const apiToken = process.env.SEMGREP_API_TOKEN;
  if (!apiToken) {
    throw new McpError(
      ErrorCode.InvalidParams,
      'SEMGREP_API_TOKEN environment variable must be set to use this tool'
    );
  }
  
  const url = `${SEMGREP_API_URL}/v1/deployments`;
  const response = await fetch(url, {
    headers: {
      'Authorization': `Bearer ${apiToken}`,
      'Accept': 'application/json',
    },
  });
  
  if (!response.ok) {
    if (response.status === 401) {
      throw new McpError(
        ErrorCode.InvalidParams,
        'Invalid API token: check your SEMGREP_API_TOKEN environment variable.'
      );
    }
    throw new McpError(
      ErrorCode.InternalError,
      `Error fetching deployments: ${await response.text()}`
    );
  }
  
  const data = await response.json() as any;
  const deployments = data.deployments || [];
  
  if (deployments.length === 0) {
    throw new McpError(
      ErrorCode.InternalError,
      'No deployments found for this API token'
    );
  }
  
  deploymentSlug = deployments[0].slug;
  return deploymentSlug!;
}

// Server setup
const server = new Server(
  {
    name: 'semgrep-mcp',
    version: VERSION,
  },
  {
    capabilities: {
      tools: {},
      prompts: {},
      resources: {},
    },
  }
);

// Tool handlers
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: 'semgrep_scan',
        description: 'Runs a Semgrep scan on provided code content and returns the findings in JSON format',
        inputSchema: {
          type: 'object',
          properties: {
            code_files: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  filename: { type: 'string' },
                  content: { type: 'string' },
                },
                required: ['filename', 'content'],
              },
              description: 'List of dictionaries with filename and content keys',
            },
            config: {
              type: 'string',
              description: 'Optional Semgrep configuration string (e.g. p/docker, p/xss, auto)',
            },
          },
          required: ['code_files'],
        },
      },
      {
        name: 'semgrep_scan_with_custom_rule',
        description: 'Runs a Semgrep scan with a custom rule on provided code content',
        inputSchema: {
          type: 'object',
          properties: {
            code_files: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  filename: { type: 'string' },
                  content: { type: 'string' },
                },
                required: ['filename', 'content'],
              },
              description: 'List of dictionaries with filename and content keys',
            },
            rule: {
              type: 'string',
              description: 'Semgrep YAML rule string',
            },
          },
          required: ['code_files', 'rule'],
        },
      },
      {
        name: 'security_check',
        description: 'Runs a fast security check on code and returns any issues found',
        inputSchema: {
          type: 'object',
          properties: {
            code_files: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  filename: { type: 'string' },
                  content: { type: 'string' },
                },
                required: ['filename', 'content'],
              },
              description: 'List of dictionaries with filename and content keys',
            },
          },
          required: ['code_files'],
        },
      },
      {
        name: 'semgrep_findings',
        description: 'Fetches findings from the Semgrep AppSec Platform Findings API',
        inputSchema: {
          type: 'object',
          properties: {
            issue_type: {
              type: 'array',
              items: { type: 'string' },
              description: 'Filter findings by type (e.g., [sast], [sca])',
            },
            status: {
              type: 'string',
              description: 'Filter findings by status (e.g., open for unresolved findings)',
            },
            repos: {
              type: 'array',
              items: { type: 'string' },
              description: 'List of repository names to filter results',
            },
            severities: {
              type: 'array',
              items: { type: 'string' },
              description: 'Filter findings by severity (e.g., [critical, high])',
            },
            confidence: {
              type: 'array',
              items: { type: 'string' },
              description: 'Filter findings by confidence level (e.g., [high])',
            },
            autotriage_verdict: {
              type: 'string',
              description: 'Filter findings by auto-triage verdict (e.g., true_positive)',
            },
            page: {
              type: 'integer',
              description: 'Page number for paginated results',
            },
            page_size: {
              type: 'integer',
              description: 'Number of findings per page (default: 100, max: 3000)',
              default: 100,
            },
          },
        },
      },
      {
        name: 'get_supported_languages',
        description: 'Returns a list of supported languages by Semgrep',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
      {
        name: 'get_abstract_syntax_tree',
        description: 'Returns the Abstract Syntax Tree (AST) for the provided code file in JSON format',
        inputSchema: {
          type: 'object',
          properties: {
            code: {
              type: 'string',
              description: 'The code to get the AST for',
            },
            language: {
              type: 'string',
              description: 'The programming language of the code',
            },
          },
          required: ['code', 'language'],
        },
      },
      {
        name: 'semgrep_rule_schema',
        description: 'Get the schema for a Semgrep rule',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
    ],
  };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  
  try {
    switch (name) {
      case 'semgrep_scan': {
        const { code_files, config } = args as { code_files: CodeFile[]; config?: string };
        validateCodeFiles(code_files);
        const validatedConfig = validateConfig(config);
        
        const tempDir = await createTempFilesFromCodeContent(code_files);
        try {
          const scanArgs = getSemgrepScanArgs(tempDir, validatedConfig);
          const output = await runSemgrep(scanArgs);
          const results: SemgrepScanResult = JSON.parse(output);
          removeTempDirFromResults(results, tempDir);
          return { content: [{ type: 'text', text: JSON.stringify(results, null, 2) }] };
        } finally {
          await rmdir(tempDir, { recursive: true });
        }
      }
      
      case 'semgrep_scan_with_custom_rule': {
        const { code_files, rule } = args as { code_files: CodeFile[]; rule: string };
        validateCodeFiles(code_files);
        
        const tempDir = await createTempFilesFromCodeContent(code_files);
        try {
          const ruleFilePath = join(tempDir, 'rule.yaml');
          await writeFile(ruleFilePath, rule);
          
          const scanArgs = getSemgrepScanArgs(tempDir, ruleFilePath);
          const output = await runSemgrep(scanArgs);
          const results: SemgrepScanResult = JSON.parse(output);
          removeTempDirFromResults(results, tempDir);
          return { content: [{ type: 'text', text: JSON.stringify(results, null, 2) }] };
        } finally {
          await rmdir(tempDir, { recursive: true });
        }
      }
      
      case 'security_check': {
        const { code_files } = args as { code_files: CodeFile[] };
        validateCodeFiles(code_files);
        
        const tempDir = await createTempFilesFromCodeContent(code_files);
        try {
          const scanArgs = getSemgrepScanArgs(tempDir);
          const output = await runSemgrep(scanArgs);
          const results: SemgrepScanResult = JSON.parse(output);
          removeTempDirFromResults(results, tempDir);
          
          if (results.results.length > 0) {
            const message = `${results.results.length} security issues found in the code.

Here are the details of the security issues found:

<security-issues>
${JSON.stringify(results, null, 2)}
</security-issues>`;
            return { content: [{ type: 'text', text: message }] };
          } else {
            return { content: [{ type: 'text', text: 'No security issues found in the code!' }] };
          }
        } finally {
          await rmdir(tempDir, { recursive: true });
        }
      }
      
      case 'semgrep_findings': {
        const {
          issue_type = ['sast', 'sca'],
          status,
          repos,
          severities,
          confidence,
          autotriage_verdict,
          page,
          page_size = 100,
        } = args as {
          issue_type?: string[];
          status?: string;
          repos?: string[];
          severities?: string[];
          confidence?: string[];
          autotriage_verdict?: string;
          page?: number;
          page_size?: number;
        };
        
        const allowedIssueTypes = new Set(['sast', 'sca']);
        const invalidTypes = issue_type.filter(type => !allowedIssueTypes.has(type));
        if (invalidTypes.length > 0) {
          throw new McpError(
            ErrorCode.InvalidParams,
            `Invalid issue_type(s): ${invalidTypes.join(', ')}. Allowed values are 'sast' and 'sca'.`
          );
        }
        
        if (page_size < 100 || page_size > 3000) {
          throw new McpError(
            ErrorCode.InvalidParams,
            'page_size must be between 100 and 3000.'
          );
        }
        
        const deployment = await getDeploymentSlug();
        const apiToken = process.env.SEMGREP_API_TOKEN;
        
        const url = `https://semgrep.dev/api/v1/deployments/${deployment}/findings`;
        const params = new URLSearchParams();
        
        issue_type.forEach(type => params.append('issue_type', type));
        if (status) params.append('status', status);
        if (repos) repos.forEach(repo => params.append('repos', repo));
        if (severities) severities.forEach(sev => params.append('severities', sev));
        if (confidence) confidence.forEach(conf => params.append('confidence', conf));
        if (autotriage_verdict) params.append('autotriage_verdict', autotriage_verdict);
        if (page) params.append('page', page.toString());
        params.append('page_size', page_size.toString());
        
        const response = await fetch(`${url}?${params.toString()}`, {
          headers: {
            'Authorization': `Bearer ${apiToken}`,
            'Accept': 'application/json',
          },
        });
        
        if (!response.ok) {
          if (response.status === 401) {
            throw new McpError(
              ErrorCode.InvalidParams,
              'Invalid API token: check your SEMGREP_API_TOKEN environment variable.'
            );
          } else if (response.status === 404) {
            throw new McpError(
              ErrorCode.InvalidParams,
              `Deployment '${deployment}' not found or you don't have access to it.`
            );
          } else {
            throw new McpError(
              ErrorCode.InternalError,
              `Error fetching findings: ${await response.text()}`
            );
          }
        }
        
        const data = await response.json() as any;
        const findings = data.findings || [];
        return { content: [{ type: 'text', text: JSON.stringify(findings, null, 2) }] };
      }
      
      case 'get_supported_languages': {
        const args = ['show', 'supported-languages', '--experimental'];
        const output = await runSemgrep(args);
        const languages = output.trim().split('\n').map(lang => lang.trim()).filter(lang => lang);
        return { content: [{ type: 'text', text: JSON.stringify(languages, null, 2) }] };
      }
      
      case 'get_abstract_syntax_tree': {
        const { code, language } = args as { code: string; language: string };
        
        const tempDir = await mkdtemp(join(tmpdir(), 'semgrep_ast_'));
        try {
          const tempFilePath = join(tempDir, 'code.txt');
          await writeFile(tempFilePath, code);
          
          const astArgs = [
            '--experimental',
            '--dump-ast',
            '-l',
            language,
            '--json',
            tempFilePath,
          ];
          
          const output = await runSemgrep(astArgs);
          return { content: [{ type: 'text', text: output }] };
        } finally {
          await rmdir(tempDir, { recursive: true });
        }
      }
      
      case 'semgrep_rule_schema': {
        const response = await fetch(`${SEMGREP_API_URL}/schema_url`);
        if (!response.ok) {
          throw new McpError(
            ErrorCode.InternalError,
            'Error getting schema URL from Semgrep API'
          );
        }
        
        const data = await response.json() as any;
        const schemaResponse = await fetch(data.schema_url);
        if (!schemaResponse.ok) {
          throw new McpError(
            ErrorCode.InternalError,
            'Error fetching schema from Semgrep'
          );
        }
        
        const schema = await schemaResponse.text();
        return { content: [{ type: 'text', text: schema }] };
      }
      
      default:
        throw new McpError(
          ErrorCode.MethodNotFound,
          `Unknown tool: ${name}`
        );
    }
  } catch (error) {
    if (error instanceof McpError) {
      throw error;
    }
    throw new McpError(
      ErrorCode.InternalError,
      `Error executing tool ${name}: ${error}`
    );
  }
});

// Prompt handlers
server.setRequestHandler(ListPromptsRequestSchema, async () => {
  return {
    prompts: [
      {
        name: 'write_custom_semgrep_rule',
        description: 'Write a custom Semgrep rule for the provided code and language',
        arguments: [
          {
            name: 'code',
            description: 'The code to analyze',
            required: true,
          },
          {
            name: 'language',
            description: 'The programming language of the code',
            required: true,
          },
        ],
      },
    ],
  };
});

server.setRequestHandler(GetPromptRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  
  if (name === 'write_custom_semgrep_rule') {
    const { code, language } = args as { code: string; language: string };
    
    const promptTemplate = `You are an expert at writing Semgrep rules.

Your task is to analyze a given piece of code and create a Semgrep rule
that can detect specific patterns or issues within that code.
Semgrep is a lightweight static analysis tool that uses pattern matching
to find bugs and enforce code standards.

Here is the code you need to analyze:

<code>
${code}
</code>

The code is written in the following programming language:

<language>
${language}
</language>

To write an effective Semgrep rule, follow these guidelines:
1. Identify a specific pattern, vulnerability, or coding standard violation in the given code.
2. Create a rule that matches this pattern as precisely as possible.
3. Use Semgrep's pattern syntax, which is similar to the target language but with metavariables and ellipsis operators where appropriate.
4. Consider the context and potential variations of the pattern you're trying to match.
5. Provide a clear and concise message that explains what the rule detects.
6. The value of the \`severity\` must be one of: "ERROR", "WARNING", "INFO", "INVENTORY", "EXPERIMENT", "CRITICAL", "HIGH", "MEDIUM", "LOW"
7. The value of the \`languages\` must be a list of languages that the rule is applicable to and include the language given in <language> tags.

Write your Semgrep rule in YAML format. The rule should include at least the following keys:
- rules
- id
- pattern
- message
- severity
- languages

Before providing the rule, briefly explain in a few sentences what specific issue or
pattern your rule is designed to detect and why it's important.

Then, output your Semgrep rule inside <semgrep_rule> tags.

Ensure that the rule is properly formatted in YAML.
Make sure to include all the required keys and values in the rule.`;
    
    return {
      messages: [
        {
          role: 'user',
          content: {
            type: 'text',
            text: promptTemplate,
          },
        },
      ],
    };
  }
  
  throw new McpError(
    ErrorCode.MethodNotFound,
    `Unknown prompt: ${name}`
  );
});

// Resource handlers
server.setRequestHandler(ListResourcesRequestSchema, async () => {
  return {
    resources: [
      {
        uri: 'semgrep://rule/schema',
        name: 'Semgrep Rule Schema',
        description: 'Specification of the Semgrep rule YAML syntax using JSON schema',
        mimeType: 'application/yaml',
      },
    ],
  };
});

server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const { uri } = request.params;
  
  if (uri === 'semgrep://rule/schema') {
    const schemaUrl = 'https://raw.githubusercontent.com/semgrep/semgrep-interfaces/refs/heads/main/rule_schema_v1.yaml';
    const response = await fetch(schemaUrl);
    
    if (!response.ok) {
      throw new McpError(
        ErrorCode.InternalError,
        'Error loading Semgrep rule schema'
      );
    }
    
    const schema = await response.text();
    return {
      contents: [
        {
          uri,
          mimeType: 'application/yaml',
          text: schema,
        },
      ],
    };
  }
  
  throw new McpError(
    ErrorCode.MethodNotFound,
    `Unknown resource: ${uri}`
  );
});

// Start the server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('Semgrep MCP server running on stdio');
}

if (require.main === module) {
  main().catch((error) => {
    console.error('Fatal error in main():', error);
    process.exit(1);
  });
}