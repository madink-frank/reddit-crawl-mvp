module.exports = (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }
  
  if (req.method !== 'GET') {
    return res.status(405).json({ success: false, error: 'Method not allowed' });
  }
  
  try {
    const statsData = {
      success: true,
      data: {
        total_posts: 149,
        ai_processed: 6,
        published: 4,
        collected_today: 0,
        success_rate: 2.7,
        recent_posts: [
          {
            id: 'mock_1',
            title: 'Sample Reddit Post 1',
            subreddit: 'programming',
            score: 125,
            comments: 23,
            processed: true,
            published: true,
            ghost_url: 'https://american-trends.ghost.io/sample-post-1',
            created_at: new Date().toISOString()
          },
          {
            id: 'mock_2', 
            title: 'Sample Reddit Post 2',
            subreddit: 'technology',
            score: 89,
            comments: 15,
            processed: true,
            published: false,
            ghost_url: null,
            created_at: new Date(Date.now() - 3600000).toISOString()
          }
        ]
      },
      timestamp: new Date().toISOString()
    };
    
    return res.status(200).json(statsData);
  } catch (error) {
    console.error('Stats error:', error);
    return res.status(500).json({
      success: false,
      error: error.message
    });
  }
};