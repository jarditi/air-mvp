#!/usr/bin/env node

const https = require('https');

const CLERK_SECRET_KEY = 'sk_test_GxDV2TPWSO8FyjaZigiE8HRb26Sz5WmwC38oUXSeFf';
const USER_ID = 'user_2yZ2mD697whSd0ThTH1Q5BlbDUk'; // Your user ID from the previous output

async function createSession() {
    return new Promise((resolve, reject) => {
        const postData = JSON.stringify({
            user_id: USER_ID
        });

        const options = {
            hostname: 'api.clerk.com',
            port: 443,
            path: '/v1/sessions',
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${CLERK_SECRET_KEY}`,
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(postData)
            }
        };

        const req = https.request(options, (res) => {
            let data = '';
            
            res.on('data', (chunk) => {
                data += chunk;
            });
            
            res.on('end', () => {
                try {
                    const response = JSON.parse(data);
                    if (res.statusCode === 200 || res.statusCode === 201) {
                        console.log('✅ Session created:', response.id);
                        resolve(response);
                    } else {
                        console.log('❌ Session creation failed:', res.statusCode, response);
                        resolve(null);
                    }
                } catch (e) {
                    console.log('❌ Error parsing response:', data);
                    resolve(null);
                }
            });
        });

        req.on('error', (error) => {
            console.log('❌ Request error:', error.message);
            resolve(null);
        });

        req.write(postData);
        req.end();
    });
}

async function getToken(sessionId) {
    return new Promise((resolve, reject) => {
        const options = {
            hostname: 'api.clerk.com',
            port: 443,
            path: `/v1/sessions/${sessionId}/tokens`,
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${CLERK_SECRET_KEY}`,
                'Content-Type': 'application/json'
            }
        };

        const req = https.request(options, (res) => {
            let data = '';
            
            res.on('data', (chunk) => {
                data += chunk;
            });
            
            res.on('end', () => {
                try {
                    const response = JSON.parse(data);
                    if (res.statusCode === 200 || res.statusCode === 201) {
                        console.log('✅ Token generated successfully!');
                        resolve(response.jwt);
                    } else {
                        console.log('❌ Token generation failed:', res.statusCode, response);
                        resolve(null);
                    }
                } catch (e) {
                    console.log('❌ Error parsing token response:', data);
                    resolve(null);
                }
            });
        });

        req.on('error', (error) => {
            console.log('❌ Token request error:', error.message);
            resolve(null);
        });

        req.end();
    });
}

async function testAPI(token) {
    return new Promise((resolve) => {
        const postData = JSON.stringify({
            integration_type: 'google_calendar'
        });

        const options = {
            hostname: 'localhost',
            port: 8000,
            path: '/api/v1/integrations/oauth/initiate',
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(postData)
            }
        };

        const req = https.request(options, (res) => {
            let data = '';
            
            res.on('data', (chunk) => {
                data += chunk;
            });
            
            res.on('end', () => {
                console.log('\n🧪 API Test Results:');
                console.log('Status:', res.statusCode, res.statusMessage);
                console.log('Response:', data);
                resolve();
            });
        });

        req.on('error', (error) => {
            console.log('\n🧪 API Test Results:');
            console.log('❌ Error:', error.message);
            console.log('💡 Make sure your backend is running on localhost:8000');
            resolve();
        });

        req.write(postData);
        req.end();
    });
}

async function main() {
    console.log('🔑 Getting Clerk Token for jarditi@gmail.com');
    console.log('===========================================\n');
    
    console.log('👤 User ID:', USER_ID);
    console.log('🎫 Creating session...');
    
    const session = await createSession();
    if (!session) {
        console.log('❌ Failed to create session');
        return;
    }
    
    console.log('🔑 Getting token...');
    const token = await getToken(session.id);
    if (!token) {
        console.log('❌ Failed to get token');
        return;
    }
    
    console.log('\n🎯 SUCCESS! Your JWT Token:');
    console.log('=' .repeat(80));
    console.log(token);
    console.log('=' .repeat(80));
    
    console.log('\n📋 Copy this curl command to test your API:');
    console.log(`curl -X POST "http://localhost:8000/api/v1/integrations/oauth/initiate" \\`);
    console.log(`  -H "Content-Type: application/json" \\`);
    console.log(`  -H "Authorization: Bearer ${token}" \\`);
    console.log(`  -d '{"integration_type": "google_calendar"}'`);
    
    // Test the API
    await testAPI(token);
}

main().catch(console.error); 