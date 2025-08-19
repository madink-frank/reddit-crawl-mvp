module.exports = (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }
  
  if (req.method !== 'POST') {
    return res.status(405).json({ success: false, error: 'Method not allowed' });
  }
  
  try {
    const { subreddits = ['programming', 'technology', 'webdev'], limit = 10 } = req.body || {};
    
    // Reddit API 설정
    const redditClientId = process.env.REDDIT_CLIENT_ID;
    const redditClientSecret = process.env.REDDIT_CLIENT_SECRET;
    
    if (!redditClientId || !redditClientSecret) {
      return res.status(200).json({
        success: true,
        data: {
          collected_posts: 0,
          message: 'Reddit API credentials not configured - using mock mode',
          mock_data: {
            subreddits: subreddits,
            expected_posts: limit,
            note: 'Configure REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in Vercel environment variables'
          }
        }
      });
    }
    
    // 실제 Reddit API 호출은 여기서 구현
    // 지금은 mock 응답 반환
    return res.status(200).json({
      success: true,
      data: {
        collected_posts: 3,
        message: 'Reddit collection completed (mock)',
        subreddits_processed: subreddits,
        timestamp: new Date().toISOString(),
        next_steps: 'Ready for AI processing'
      }
    });
    
  } catch (error) {
    console.error('Reddit collection error:', error);
    return res.status(500).json({
      success: false,
      error: error.message,
      fallback_action: 'Check Reddit API credentials and try again'
    });
  }
};