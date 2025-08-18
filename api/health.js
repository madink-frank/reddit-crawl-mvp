// Vercel Serverless Function - Health Check
export default async function handler(req, res) {
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
    // Supabase 연결 테스트 (환경 변수 필요)
    const supabaseUrl = process.env.SUPABASE_URL;
    const supabaseKey = process.env.SUPABASE_ANON_KEY;
    
    let dbHealthy = false;
    
    if (supabaseUrl && supabaseKey) {
      try {
        const response = await fetch(`${supabaseUrl}/rest/v1/posts?select=count&limit=1`, {
          headers: {
            'apikey': supabaseKey,
            'Authorization': `Bearer ${supabaseKey}`
          }
        });
        dbHealthy = response.ok;
      } catch (error) {
        console.log('Database connection test failed:', error.message);
      }
    }
    
    const healthData = {
      success: true,
      data: {
        api_server: {
          healthy: true,
          status: 'healthy'
        },
        database: {
          healthy: dbHealthy
        },
        overall_status: dbHealthy ? 'healthy' : 'degraded',
        services: {
          database: { status: dbHealthy ? 'healthy' : 'degraded' },
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