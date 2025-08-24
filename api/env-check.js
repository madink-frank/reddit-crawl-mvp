module.exports = (req, res) => {
  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-API-Key, X-Requested-With');
  
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }
  
  if (req.method !== 'GET') {
    return res.status(405).json({ success: false, error: 'Method not allowed' });
  }
  
  // Check environment variables (without exposing sensitive data)
  const envCheck = {
    success: true,
    data: {
      environment_variables: {
        REDDIT_CLIENT_ID: !!process.env.REDDIT_CLIENT_ID,
        REDDIT_CLIENT_SECRET: !!process.env.REDDIT_CLIENT_SECRET,
        OPENAI_API_KEY: !!process.env.OPENAI_API_KEY,
        GHOST_ADMIN_KEY: !!process.env.GHOST_ADMIN_KEY,
        GHOST_API_URL: !!process.env.GHOST_API_URL,
        SUPABASE_URL: !!process.env.SUPABASE_URL,
        SUPABASE_ANON_KEY: !!process.env.SUPABASE_ANON_KEY,
        NODE_ENV: process.env.NODE_ENV || 'development'
      },
      partial_values: {
        REDDIT_CLIENT_ID: process.env.REDDIT_CLIENT_ID ? process.env.REDDIT_CLIENT_ID.substring(0, 8) + '...' : 'not set',
        OPENAI_API_KEY: process.env.OPENAI_API_KEY ? process.env.OPENAI_API_KEY.substring(0, 8) + '...' : 'not set',
        GHOST_ADMIN_KEY: process.env.GHOST_ADMIN_KEY ? process.env.GHOST_ADMIN_KEY.substring(0, 8) + '...' : 'not set',
        GHOST_API_URL: process.env.GHOST_API_URL || 'not set'
      }
    },
    timestamp: new Date().toISOString()
  };
  
  return res.status(200).json(envCheck);
};