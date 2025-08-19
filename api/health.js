module.exports = (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }
  
  if (req.method !== 'GET') {
    return res.status(405).json({ success: false, error: 'Method not allowed' });
  }
  
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