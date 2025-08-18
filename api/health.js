// Vercel Serverless Function - Health Check (Mock)
module.exports = async function handler(req, res) {
  // CORS 헤더 설정
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }
  
  if (req.method !== 'GET') {
    return res.status(405).json({ success: false, error: 'Method not allowed' });
  }
  
  try {
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
    
    res.status(200).json(healthData);
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
}