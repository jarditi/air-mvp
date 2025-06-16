#!/usr/bin/env node

const https = require('https');

const CLERK_SECRET_KEY = 'sk_test_GxDV2TPWSO8FyjaZigiE8HRb26Sz5WmwC38oUXSeFf';

function makeRequest(options) {
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
        req.end();
    });
}

async function checkClerkConfig() {
    console.log('🔍 Checking Clerk instance configuration...');
    
    const options = {
        hostname: 'api.clerk.com',
        port: 443,
        path: '/v1/instance',
        method: 'GET',
        headers: {
            'Authorization': `Bearer ${CLERK_SECRET_KEY}`,
            'Content-Type': 'application/json'
        }
    };

    try {
        const response = await makeRequest(options);
        
        if (response.status === 200) {
            console.log('✅ Instance configuration retrieved!');
            console.log('\n📋 Instance Details:');
            console.log('- Environment:', response.data.environment_type);
            console.log('- Domain:', response.data.home_url);
            
            if (response.data.restrictions) {
                console.log('\n🔒 User Creation Restrictions:');
                console.log(JSON.stringify(response.data.restrictions, null, 2));
            }
            
            return response.data;
        } else {
            console.log('❌ Failed to get instance config:', response.status, response.data);
            return null;
        }
    } catch (error) {
        console.log('❌ Error getting instance config:', error.message);
        return null;
    }
}

async function listExistingUsers() {
    console.log('\n👥 Checking existing users...');
    
    const options = {
        hostname: 'api.clerk.com',
        port: 443,
        path: '/v1/users?limit=5',
        method: 'GET',
        headers: {
            'Authorization': `Bearer ${CLERK_SECRET_KEY}`,
            'Content-Type': 'application/json'
        }
    };

    try {
        const response = await makeRequest(options);
        
        if (response.status === 200) {
            console.log(`✅ Found ${response.data.length} existing users`);
            
            if (response.data.length > 0) {
                console.log('\n📋 Existing Users:');
                response.data.forEach((user, index) => {
                    console.log(`${index + 1}. ${user.email_addresses[0]?.email_address || 'No email'} (ID: ${user.id})`);
                });
                
                return response.data;  // Return the full array
            }
            
            return response.data;
        } else {
            console.log('❌ Failed to list users:', response.status, response.data);
            return null;
        }
    } catch (error) {
        console.log('❌ Error listing users:', error.message);
        return null;
    }
}

async function createSessionForUser(userId) {
    console.log(`\n🎫 Creating session for user ${userId}...`);
    
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
        const req = https.request(options, (res) => {
            let body = '';
            res.on('data', (chunk) => body += chunk);
            res.on('end', () => {
                try {
                    const parsed = JSON.parse(body);
                    if (res.statusCode === 200 || res.statusCode === 201) {
                        console.log('✅ Session created successfully!');
                        console.log('🎫 Session ID:', parsed.id);
                        return parsed;
                    } else {
                        console.log('❌ Failed to create session:', res.statusCode, parsed);
                        return null;
                    }
                } catch (e) {
                    console.log('❌ Error parsing session response:', body);
                    return null;
                }
            });
        });

        req.on('error', (error) => {
            console.log('❌ Error creating session:', error.message);
            return null;
        });
        
        req.write(JSON.stringify(sessionData));
        req.end();
        
        return new Promise((resolve) => {
            req.on('response', (res) => {
                let body = '';
                res.on('data', (chunk) => body += chunk);
                res.on('end', () => {
                    try {
                        const parsed = JSON.parse(body);
                        if (res.statusCode === 200 || res.statusCode === 201) {
                            console.log('✅ Session created successfully!');
                            console.log('🎫 Session ID:', parsed.id);
                            resolve(parsed);
                        } else {
                            console.log('❌ Failed to create session:', res.statusCode, parsed);
                            resolve(null);
                        }
                    } catch (e) {
                        console.log('❌ Error parsing session response:', body);
                        resolve(null);
                    }
                });
            });
        });
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

async function main() {
    console.log('🔍 Clerk Configuration Checker');
    console.log('===============================\n');
    
    // Check instance configuration
    await checkClerkConfig();
    
    // List existing users
    const users = await listExistingUsers();
    
    if (users && users.length > 0) {
        const firstUser = users[0];
        
        // Create session for first user
        const session = await createSessionForUser(firstUser.id);
        
        if (session) {
            // Get token
            const token = await getSessionToken(session.id);
            
            if (token) {
                console.log('\n🎯 SUCCESS! Your JWT Token:');
                console.log('=' .repeat(50));
                console.log(token);
                console.log('=' .repeat(50));
                
                console.log('\n📋 Use this token in your API requests:');
                console.log(`curl -X POST "http://localhost:8000/api/v1/integrations/oauth/initiate" \\`);
                console.log(`  -H "Content-Type: application/json" \\`);
                console.log(`  -H "Authorization: Bearer ${token}" \\`);
                console.log(`  -d '{"integration_type": "google_calendar"}'`);
            }
        }
    } else {
        console.log('\n💡 No existing users found. You can:');
        console.log('1. Go to your Clerk Dashboard and create a user manually');
        console.log('2. Set up a frontend app to handle user registration');
        console.log('3. Adjust your Clerk instance settings to allow programmatic user creation');
    }
}

main().catch(console.error); 