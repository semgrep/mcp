#!/usr/bin/env node

const { spawn } = require('child_process');

// Test the semgrep_rule_schema function and validate schema content
async function testSchemaValidation() {
  console.log('🧪 Testing semgrep_rule_schema validation...\n');
  
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
  let hasResponse = false;
  
  server.stdout.on('data', (data) => {
    output += data.toString();
    
    try {
      const lines = output.split('\n');
      for (const line of lines) {
        if (line.trim() && line.includes('"jsonrpc"')) {
          const response = JSON.parse(line);
          if (response.id === 1) {
            hasResponse = true;
            
            if (response.result && response.result.content) {
              const content = response.result.content[0];
              if (content.type === 'text' && content.text) {
                const schema = content.text;
                
                console.log('✅ Schema retrieved successfully');
                console.log(`   Length: ${schema.length} characters`);
                
                // Validate schema content
                const validations = [
                  {
                    name: 'Contains JSON schema markers',
                    test: schema.includes('$schema') || schema.includes('properties') || schema.includes('definitions')
                  },
                  {
                    name: 'Contains Semgrep rule structure',
                    test: schema.includes('rules') && schema.includes('id') && schema.includes('pattern')
                  },
                  {
                    name: 'Contains message field',
                    test: schema.includes('message')
                  },
                  {
                    name: 'Contains severity field',
                    test: schema.includes('severity')
                  },
                  {
                    name: 'Contains languages field',
                    test: schema.includes('languages')
                  },
                  {
                    name: 'Contains metavariable info',
                    test: schema.includes('metavariable') || schema.includes('pattern')
                  }
                ];
                
                console.log('\n📋 Schema validation results:');
                let passed = 0;
                for (const validation of validations) {
                  const status = validation.test ? '✅' : '❌';
                  console.log(`   ${status} ${validation.name}`);
                  if (validation.test) passed++;
                }
                
                console.log(`\n📊 Validation score: ${passed}/${validations.length} (${Math.round(passed/validations.length*100)}%)`);
                
                if (passed === validations.length) {
                  console.log('🎉 Schema validation PASSED!');
                } else {
                  console.log('⚠️  Schema validation partially failed');
                }
              }
            } else if (response.error) {
              console.log(`❌ Error: ${response.error.message}`);
            }
            
            server.kill();
            return;
          }
        }
      }
    } catch (e) {
      // Still parsing
    }
  });
  
  server.stderr.on('data', (data) => {
    if (!data.toString().includes('running on stdio')) {
      console.log(`stderr: ${data.toString().trim()}`);
    }
  });
  
  server.on('close', (code) => {
    if (!hasResponse) {
      console.log('❌ No response received');
    }
  });
  
  // Send the request
  server.stdin.write(JSON.stringify(request) + '\n');
  
  // Wait for response
  setTimeout(() => {
    if (!hasResponse) {
      console.log('❌ Timeout waiting for schema response');
      server.kill();
    }
  }, 15000);
}

testSchemaValidation().catch(console.error);