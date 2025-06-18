#!/usr/bin/env node

/**
 * Setup script to configure Clerk environment variables for proper JWT verification
 */

const https = require('https');
const fs = require('fs');

const CLERK_SECRET_KEY = 'sk_test_GxDV2TPWSO8FyjaZigiE8HRb26Sz5WmwC38oUXSeFf';
const CLERK_PUBLISHABLE_KEY = 'pk_test_bGl2aW5nLWRvZS04MC5jbGVyay5hY2NvdW50cy5kZXY$'; // Need to get this

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

async function getClerkInstance() {
    console.log('🔍 Getting Clerk instance information...');
    
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
            console.log('✅ Instance information retrieved!');
            console.log('- Environment:', response.data.environment_type);
            console.log('- Domain:', response.data.home_url);
            
            // Extract the Frontend API URL (used for JWKS)
            const frontendApiUrl = response.data.home_url; // This is actually the frontend URL
            const jwksUrl = `${frontendApiUrl}/.well-known/jwks.json`;
            
            console.log('- JWKS URL:', jwksUrl);
            
            return {
                frontendApiUrl,
                jwksUrl,
                instanceData: response.data
            };
        } else {
            console.log('❌ Failed to get instance info:', response.status, response.data);
            return null;
        }
    } catch (error) {
        console.log('❌ Error getting instance info:', error.message);
        return null;
    }
}

async function getJWKS(jwksUrl) {
    console.log('\n🔑 Fetching JWKS public keys...');
    
    const url = new URL(jwksUrl);
    const options = {
        hostname: url.hostname,
        port: 443,
        path: url.pathname,
        method: 'GET',
        headers: {
            'Accept': 'application/json'
        }
    };

    try {
        const response = await makeRequest(options);
        
        if (response.status === 200) {
            console.log('✅ JWKS keys retrieved successfully!');
            console.log('Keys found:', response.data.keys.length);
            
            // Extract the first key and convert to PEM format
            if (response.data.keys && response.data.keys.length > 0) {
                const firstKey = response.data.keys[0];
                console.log('- Key ID:', firstKey.kid);
                console.log('- Algorithm:', firstKey.alg);
                console.log('- Key Type:', firstKey.kty);
                
                // For Clerk, we can use the JWKS URL directly
                return {
                    jwks: response.data,
                    jwksUrl: jwksUrl
                };
            }
        } else {
            console.log('❌ Failed to get JWKS:', response.status, response.data);
        }
    } catch (error) {
        console.log('❌ Error fetching JWKS:', error.message);
    }
    
    return null;
}

async function createEnvFile(instanceInfo, jwksInfo) {
    console.log('\n📝 Creating environment configuration...');
    
    const envContent = `# Clerk Configuration
CLERK_SECRET_KEY=${CLERK_SECRET_KEY}
CLERK_PUBLISHABLE_KEY=pk_test_bGl2aW5nLWRvZS04MC5jbGVyay5hY2NvdW50cy5kZXY$
CLERK_FRONTEND_API=${instanceInfo.frontendApiUrl}
CLERK_JWT_VERIFICATION_KEY=${instanceInfo.jwksUrl}

# For manual JWT verification, you can also use the JWKS URL:
# CLERK_JWKS_URL=${jwksInfo.jwksUrl}

# Other required environment variables (keep existing values)
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://postgres:password@db:5432/airmvp
REDIS_URL=redis://redis:6379
WEAVIATE_URL=http://weaviate:8080
OPENAI_API_KEY=your-openai-key-here
CELERY_BROKER_URL=redis://redis:6379
CELERY_RESULT_BACKEND=redis://redis:6379
`;

    try {
        fs.writeFileSync('.env.clerk', envContent);
        console.log('✅ Environment file created: .env.clerk');
        console.log('\n📋 Next steps:');
        console.log('1. Copy the Clerk variables from .env.clerk to your main .env file');
        console.log('2. Restart your Docker containers: docker-compose restart');
        console.log('3. Test the conversation threading API with proper Clerk authentication');
        
        return true;
    } catch (error) {
        console.log('❌ Error creating env file:', error.message);
        return false;
    }
}

async function main() {
    console.log('🚀 Clerk Environment Setup');
    console.log('==========================\n');
    
    // Get instance information
    const instanceInfo = await getClerkInstance();
    if (!instanceInfo) {
        console.log('❌ Cannot proceed without instance information');
        return;
    }
    
    // Get JWKS information  
    const jwksInfo = await getJWKS(instanceInfo.jwksUrl);
    if (!jwksInfo) {
        console.log('❌ Cannot proceed without JWKS information');
        return;
    }
    
    // Create environment file
    const success = await createEnvFile(instanceInfo, jwksInfo);
    if (success) {
        console.log('\n🎉 Clerk environment setup complete!');
        console.log('\nFor testing, you can use the JWT token from get-clerk-token.js:');
        console.log('Bearer eyJhbGci...[your-jwt-token-here]');
    }
}

if (require.main === module) {
    main().catch(console.error);
} 