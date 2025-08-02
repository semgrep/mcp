#!/usr/bin/env node

const { spawn } = require('child_process');

// Test the MCP server by running a security scan
async function testScan() {
  console.log('Testing Semgrep scan functionality...');
  
  const server = spawn('node', ['dist/index.js'], {
    stdio: ['pipe', 'pipe', 'pipe']
  });
  
  // Test request for security_check tool
  const request = {
    jsonrpc: '2.0',
    id: 1,
    method: 'tools/call',
    params: {
      name: 'security_check',
      arguments: {
        code_files: [
          {
            filename: 'test.py',
            content: 'import subprocess\nsubprocess.call("ls", shell=True)'
          }
        ]
      }
    }
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
    console.log('Security scan output:', output);
    if (errorOutput) console.log('Server errors:', errorOutput);
    console.log('Server exit code:', code);
  });
  
  // Send the request
  server.stdin.write(JSON.stringify(request) + '\n');
  
  // Wait for response
  setTimeout(() => {
    server.kill();
  }, 10000);
}

testScan().catch(console.error);