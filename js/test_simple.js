#!/usr/bin/env node

const { spawn } = require('child_process');

// Test the MCP server by getting supported languages
async function testSimple() {
  console.log('Testing get_supported_languages...');
  
  const server = spawn('node', ['dist/index.js'], {
    stdio: ['pipe', 'pipe', 'pipe']
  });
  
  // Test request for get_supported_languages tool
  const request = {
    jsonrpc: '2.0',
    id: 1,
    method: 'tools/call',
    params: {
      name: 'get_supported_languages',
      arguments: {}
    }
  };
  
  let output = '';
  let errorOutput = '';
  let hasResponse = false;
  
  server.stdout.on('data', (data) => {
    output += data.toString();
    if (output.includes('"result"')) {
      hasResponse = true;
      console.log('✅ Received response:', output);
      server.kill();
    }
  });
  
  server.stderr.on('data', (data) => {
    errorOutput += data.toString();
    console.log('Server stderr:', data.toString());
  });
  
  server.on('close', (code) => {
    if (!hasResponse) {
      console.log('❌ No response received');
      console.log('Full output:', output);
      console.log('Error output:', errorOutput);
    }
    console.log('Server exit code:', code);
  });
  
  // Send the request
  server.stdin.write(JSON.stringify(request) + '\n');
  
  // Wait for response
  setTimeout(() => {
    if (!hasResponse) {
      console.log('❌ Timeout waiting for response');
      server.kill();
    }
  }, 5000);
}

testSimple().catch(console.error);