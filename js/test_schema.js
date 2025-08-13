#!/usr/bin/env node

const { spawn } = require('child_process');

// Test the semgrep_rule_schema function specifically
async function testSchema() {
  console.log('🧪 Testing semgrep_rule_schema...\n');
  
  const server = spawn('node', ['dist/index.js'], {
    stdio: ['pipe', 'pipe', 'pipe']
  });
  
  const request = {
    jsonrpc: '2.0',
    id: 1,
    method: 'tools/call',
    params: {
      name: 'semgrep_rule_schema',
      arguments: {}
    }
  };
  
  let output = '';
  let errorOutput = '';
  let hasResponse = false;
  let responseComplete = false;
  
  server.stdout.on('data', (data) => {
    output += data.toString();
    
    // Check if we have a complete JSON response
    try {
      const lines = output.split('\n');
      for (const line of lines) {
        if (line.trim() && line.includes('"jsonrpc"')) {
          const response = JSON.parse(line);
          if (response.id === 1) {
            hasResponse = true;
            responseComplete = true;
            
            if (response.result && response.result.content) {
              console.log('✅ semgrep_rule_schema: SUCCESS');
              const content = response.result.content[0];
              if (content.type === 'text' && content.text) {
                const textLength = content.text.length;
                console.log(`   Schema length: ${textLength} characters`);
                
                // Check if it looks like YAML schema
                if (content.text.includes('$schema') || content.text.includes('properties') || content.text.includes('title')) {
                  console.log('   ✅ Response contains valid schema content');
                } else {
                  console.log('   ⚠️  Response may not contain valid schema');
                }
                
                // Show first few lines
                const firstLines = content.text.split('\n').slice(0, 5).join('\n');
                console.log(`   First few lines:\n${firstLines}...`);
              }
            } else if (response.error) {
              console.log(`❌ semgrep_rule_schema: ERROR - ${response.error.message}`);
            }
            
            server.kill();
            return;
          }
        }
      }
    } catch (e) {
      // Still parsing, continue
    }
  });
  
  server.stderr.on('data', (data) => {
    errorOutput += data.toString();
    if (!data.toString().includes('running on stdio')) {
      console.log(`   stderr: ${data.toString().trim()}`);
    }
  });
  
  server.on('close', (code) => {
    if (!hasResponse) {
      console.log('❌ No response received');
      console.log('Output length:', output.length);
      if (output.length > 0) {
        console.log('Raw output (first 500 chars):', output.substring(0, 500));
      }
      if (errorOutput.length > 0) {
        console.log('Error output:', errorOutput);
      }
    }
    console.log('Server exit code:', code);
  });
  
  // Send the request
  console.log('Sending request...');
  server.stdin.write(JSON.stringify(request) + '\n');
  
  // Wait for response (longer timeout for schema)
  setTimeout(() => {
    if (!responseComplete) {
      console.log('❌ Timeout waiting for complete response');
      server.kill();
    }
  }, 15000); // 15 second timeout
}

testSchema().catch(console.error);