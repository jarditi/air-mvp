#!/usr/bin/env node

/**
 * Simple Node.js script to create a test user and get a token from Clerk
 * This is for development/testing purposes only
 */

const https = require('https');

const CLERK_SECRET_KEY = 'sk_test_GxDV2TPWSO8FyjaZigiE8HRb26Sz5WmwC38oUXSeFf';

// Function to make HTTP requests
function makeRequest(options, data = null) {
    return new Promise((resolve, reject) => {
        const req = https.request(options, (res) => {
            let body = '';
            res.on('data', (chunk) => body += chunk);
            res.on('end', () => {
                try {
                    const parsed = JSON.parse(body);
                    resolve({ status: res.statusCode, data: parsed });
                } catch (e) {
                    resolve({ status: res.statusCode, data: body });
                }
            });
        });

        req.on('error', reject);
        
        if (data) {
            req.write(JSON.stringify(data));
        }
        
        req.end();
    });
}

async function createTestUser() {
    console.log('🔐 Creating test user in Clerk...');
    
    const options = {
        hostname: 'api.clerk.com',
        port: 443,
        path: '/v1/users',
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${CLERK_SECRET_KEY}`,
            'Content-Type': 'application/json'
        }
    };

    const userData = {
        email_address: [`test-${Date.now()}@example.com`],
        phone_number: [`+1555${Math.floor(Math.random() * 10000000).toString().padStart(7, '0')}`],
        password: `SecureTest${Date.now()}!@#`,
        first_name: 'Test',
        last_name: 'User'
    };

    try {
        const response = await makeRequest(options, userData);
        
        if (response.status === 200 || response.status === 201) {
            console.log('✅ User created successfully!');
            console.log('📧 Email:', userData.email_address[0]);
            console.log('🔑 Password:', userData.password);
            console.log('👤 User ID:', response.data.id);
            return response.data;
        } else {
            console.log('❌ Failed to create user:', response.status, response.data);
            return null;
        }
    } catch (error) {
        console.log('❌ Error creating user:', error.message);
        return null;
    }
}

async function createSession(userId) {
    console.log('\n🎫 Creating session for user...');
    
    const options = {
        hostname: 'api.clerk.com',
        port: 443,
        path: '/v1/sessions',
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${CLERK_SECRET_KEY}`,
            'Content-Type': 'application/json'
        }
    };

    const sessionData = {
        user_id: userId
    };

    try {
        const response = await makeRequest(options, sessionData);
        
        if (response.status === 200 || response.status === 201) {
            console.log('✅ Session created successfully!');
            console.log('🎫 Session ID:', response.data.id);
            return response.data;
        } else {
            console.log('❌ Failed to create session:', response.status, response.data);
            return null;
        }
    } catch (error) {
        console.log('❌ Error creating session:', error.message);
        return null;
    }
}

async function getSessionToken(sessionId) {
    console.log('\n🔑 Getting session token...');
    
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

    try {
        const response = await makeRequest(options);
        
        if (response.status === 200 || response.status === 201) {
            console.log('✅ Token generated successfully!');
            return response.data.jwt;
        } else {
            console.log('❌ Failed to get token:', response.status, response.data);
            return null;
        }
    } catch (error) {
        console.log('❌ Error getting token:', error.message);
        return null;
    }
}

async function testAPI(token) {
    console.log('\n🧪 Testing API with token...');
    
    const options = {
        hostname: 'localhost',
        port: 8000,
        path: '/api/v1/integrations/oauth/initiate',
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        }
    };

    const testData = {
        integration_type: 'google_calendar'
    };

    try {
        const response = await makeRequest(options, testData);
        console.log('📊 API Response Status:', response.status);
        console.log('📋 API Response:', response.data);
        
        if (response.status === 200) {
            console.log('🎉 API test successful!');
        } else {
            console.log('⚠️  API test completed with status:', response.status);
        }
    } catch (error) {
        console.log('❌ Error testing API:', error.message);
        console.log('💡 Make sure your backend is running on localhost:8000');
    }
}

async function main() {
    console.log('🚀 Clerk Token Generator');
    console.log('========================\n');
    
    // Create test user
    const user = await createTestUser();
    if (!user) {
        console.log('❌ Cannot proceed without user');
        return;
    }
    
    // Create session
    const session = await createSession(user.id);
    if (!session) {
        console.log('❌ Cannot proceed without session');
        return;
    }
    
    // Get token
    const token = await getSessionToken(session.id);
    if (!token) {
        console.log('❌ Cannot proceed without token');
        return;
    }
    
    console.log('\n🎯 SUCCESS! Your JWT Token:');
    console.log('=' .repeat(50));
    console.log(token);
    console.log('=' .repeat(50));
    
    console.log('\n📋 Use this token in your API requests:');
    console.log(`curl -X POST "http://localhost:8000/api/v1/integrations/oauth/initiate" \\`);
    console.log(`  -H "Content-Type: application/json" \\`);
    console.log(`  -H "Authorization: Bearer ${token}" \\`);
    console.log(`  -d '{"integration_type": "google_calendar"}'`);
    
    // Test the API
    await testAPI(token);
}

// Run the script
main().catch(console.error); 