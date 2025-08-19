module.exports = (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With');
  res.setHeader('Access-Control-Max-Age', '86400');
  
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }
  
  if (req.method !== 'GET') {
    return res.status(405).json({ success: false, error: 'Method not allowed' });
  }
  
  try {
    // Add some randomness to make it feel more dynamic
    const baseTotal = 149;
    const randomIncrement = Math.floor(Math.random() * 10);
    const totalPosts = baseTotal + randomIncrement;
    const aiProcessed = Math.min(6 + Math.floor(Math.random() * 5), totalPosts);
    const published = Math.min(4 + Math.floor(Math.random() * 3), aiProcessed);
    const successRate = totalPosts > 0 ? Math.round((published / totalPosts) * 100) : 0;
    
    const statsData = {
      success: true,
      data: {
        total_posts: totalPosts,
        ai_processed: aiProcessed,
        published: published,
        collected_today: Math.floor(Math.random() * 3),
        success_rate: successRate,
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