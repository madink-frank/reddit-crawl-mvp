const fs = require('fs');
const path = require('path');

module.exports = (req, res) => {
  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-API-Key, X-Requested-With');
  
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }
  
  // Serve the dashboard HTML
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
};