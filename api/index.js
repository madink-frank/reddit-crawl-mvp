export default function handler(req, res) {
  // Set CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-API-Key, X-Requested-With');

  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }

  // API Documentation HTML
  const html = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reddit Ghost Publisher API</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        h1 { color: #2c3e50; }
        .endpoint { background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .method { background: #007bff; color: white; padding: 3px 8px; border-radius: 3px; font-size: 12px; }
        a { color: #007bff; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <h1>🤖 Reddit Ghost Publisher API</h1>
    <p>Serverless API for Reddit content collection, AI processing, and Ghost publishing.</p>
    
    <h2>API Endpoints</h2>
    <div class="endpoint">
        <span class="method">GET</span> <a href="/api/health">/api/health</a> - Health Check
    </div>
    <div class="endpoint">
        <span class="method">GET</span> <a href="/api/stats">/api/stats</a> - Statistics
    </div>
    <div class="endpoint">
        <span class="method">GET</span> <a href="/api/test">/api/test</a> - Test API
    </div>
    
    <h2>Dashboard</h2>
    <p>Visit the admin dashboard at: <a href="https://american-trends.ghost.io/admin-dashboard-app/">american-trends.ghost.io/admin-dashboard-app</a></p>
    
    <h2>Status</h2>
    <p>✅ API Server: Active</p>
    <p>✅ Serverless Functions: Deployed</p>
    <p>✅ CORS: Enabled</p>
    
    <hr>
    <p><small>Powered by Vercel & Hono</small></p>
</body>
</html>
  `;

  res.setHeader('Content-Type', 'text/html');
  res.status(200).send(html);
}