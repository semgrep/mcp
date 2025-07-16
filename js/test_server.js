#!/usr/bin/env node

const { spawn } = require('child_process');

// Test the MCP server by sending a simple request
async function testServer() {
  console.log('Testing Semgrep MCP TypeScript server...');
  
  const server = spawn('node', ['dist/index.js'], {
    stdio: ['pipe', 'pipe', 'pipe']
  });
  
  // Simple MCP request to list tools
  const request = {
    jsonrpc: '2.0',
    id: 1,
    method: 'tools/list',
    params: {}
  };
  
  let output = '';
  let errorOutput = '';
  
  server.stdout.on('data', (data) => {
    output += data.toString();
  });
  
  server.stderr.on('data', (data) => {
    errorOutput += data.toString();
  });
  
  server.on('close', (code) => {
    console.log('Server output:', output);
    console.log('Server errors:', errorOutput);
    console.log('Server exit code:', code);
  });
  
  // Send the request
  server.stdin.write(JSON.stringify(request) + '\n');
  
  // Wait a moment for response
  setTimeout(() => {
    server.kill();
  }, 3000);
}

testServer().catch(console.error);