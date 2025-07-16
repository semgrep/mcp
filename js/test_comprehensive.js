#!/usr/bin/env node

const { spawn } = require('child_process');

// Test multiple MCP server functions
async function testComprehensive() {
  console.log('🧪 Running comprehensive tests...\n');
  
  const tests = [
    {
      name: 'List Tools',
      request: {
        jsonrpc: '2.0',
        id: 1,
        method: 'tools/list',
        params: {}
      }
    },
    {
      name: 'Get Supported Languages',
      request: {
        jsonrpc: '2.0',
        id: 2,
        method: 'tools/call',
        params: {
          name: 'get_supported_languages',
          arguments: {}
        }
      }
    },
    {
      name: 'Get Semgrep Rule Schema',
      request: {
        jsonrpc: '2.0',
        id: 3,
        method: 'tools/call',
        params: {
          name: 'semgrep_rule_schema',
          arguments: {}
        }
      }
    },
    {
      name: 'List Prompts',
      request: {
        jsonrpc: '2.0',
        id: 4,
        method: 'prompts/list',
        params: {}
      }
    },
    {
      name: 'List Resources',
      request: {
        jsonrpc: '2.0',
        id: 5,
        method: 'resources/list',
        params: {}
      }
    }
  ];
  
  for (const test of tests) {
    console.log(`\n📋 Running test: ${test.name}`);
    
    const server = spawn('node', ['dist/index.js'], {
      stdio: ['pipe', 'pipe', 'pipe']
    });
    
    let output = '';
    let hasResponse = false;
    
    server.stdout.on('data', (data) => {
      output += data.toString();
      
      // Check if we have a complete JSON response
      try {
        const lines = output.split('\n');
        for (const line of lines) {
          if (line.trim() && line.includes('"jsonrpc"')) {
            const response = JSON.parse(line);
            if (response.id === test.request.id) {
              hasResponse = true;
              
              if (response.result) {
                console.log(`✅ ${test.name}: SUCCESS`);
                if (test.name === 'List Tools') {
                  console.log(`   Found ${response.result.tools.length} tools`);
                } else if (test.name === 'Get Semgrep Rule Schema') {
                  const content = response.result.content?.[0];
                  if (content?.text) {
                    console.log(`   Schema length: ${content.text.length} characters`);
                  }
                }
              } else if (response.error) {
                console.log(`❌ ${test.name}: ERROR - ${response.error.message}`);
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
      // Ignore the "running on stdio" message
      if (!data.toString().includes('running on stdio')) {
        console.log(`   stderr: ${data.toString()}`);
      }
    });
    
    server.on('close', (code) => {
      if (!hasResponse) {
        console.log(`❌ ${test.name}: No response received`);
      }
    });
    
    // Send the request
    server.stdin.write(JSON.stringify(test.request) + '\n');
    
    // Wait for response (longer timeout for schema)
    const timeout = test.name === 'Get Semgrep Rule Schema' ? 15000 : 5000;
    await new Promise(resolve => {
      setTimeout(() => {
        if (!hasResponse) {
          console.log(`❌ ${test.name}: Timeout`);
          server.kill();
        }
        resolve();
      }, timeout);
    });
  }
  
  console.log('\n🎉 Comprehensive testing completed!');
}

testComprehensive().catch(console.error);