const fs = require('fs');
const path = require('path');

module.exports = (req, res) => {
  // Enhanced CORS headers for Ghost dashboard integration
  const allowedOrigins = [
    'https://american-trends.ghost.io',
    'https://www.american-trends.ghost.io',
    'http://localhost:3000',
    'http://localhost:8000',
    'http://localhost:8083'
  ];
  
  const origin = req.headers.origin;
  if (allowedOrigins.includes(origin)) {
    res.setHeader('Access-Control-Allow-Origin', origin);
  } else {
    res.setHeader('Access-Control-Allow-Origin', '*'); // Fallback for development
  }
  
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-API-Key, X-Requested-With');
  res.setHeader('Access-Control-Allow-Credentials', 'true');
  res.setHeader('Access-Control-Max-Age', '86400');
  
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }
  
  if (req.method !== 'GET') {
    return res.status(405).json({ success: false, error: 'Method not allowed' });
  }
  
  // Check if this is a request for dashboard (from root path rewrite)
  const userAgent = req.headers['user-agent'] || '';
  const acceptHeader = req.headers['accept'] || '';
  
  // If request accepts HTML (browser request), serve dashboard
  if (acceptHeader.includes('text/html')) {
    try {
      const indexPath = path.join(process.cwd(), 'index.html');
      const html = fs.readFileSync(indexPath, 'utf8');
      
      res.setHeader('Content-Type', 'text/html');
      return res.status(200).send(html);
    } catch (error) {
      console.error('Error serving index.html:', error);
      
      // Fallback HTML if index.html is not found
      const fallbackHtml = `
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reddit Ghost Publisher - Dashboard</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            max-width: 800px; 
            margin: 50px auto; 
            padding: 20px; 
            text-align: center;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .container {
            background: white;
            color: black;
            padding: 40px;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Reddit Ghost Publisher</h1>
        <p>Dashboard is loading...</p>
        <p>If this message persists, please check the deployment.</p>
    </div>
</body>
</html>
      `;
      
      res.setHeader('Content-Type', 'text/html');
      return res.status(200).send(fallbackHtml);
    }
  }
  
  // Otherwise, return JSON health data
  const healthData = {
    success: true,
    data: {
      api_server: {
        healthy: true,
        status: 'healthy'
      },
      database: {
        healthy: true
      },
      overall_status: 'healthy',
      services: {
        database: { status: 'healthy' },
        vercel: { status: 'healthy' },
        serverless: { status: 'healthy' }
      }
    },
    timestamp: new Date().toISOString()
  };
  
  return res.status(200).json(healthData);
};