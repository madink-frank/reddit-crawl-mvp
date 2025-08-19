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
    const { title, content, tags = [] } = req.body || {};
    
    if (!title || !content) {
      return res.status(400).json({
        success: false,
        error: 'Title and content are required'
      });
    }
    
    const ghostAdminKey = process.env.GHOST_ADMIN_KEY;
    const ghostApiUrl = process.env.GHOST_API_URL || 'https://american-trends.ghost.io';
    
    if (!ghostAdminKey) {
      return res.status(200).json({
        success: true,
        data: {
          published: false,
          message: 'Ghost API key not configured - mock publish mode',
          mock_data: {
            title: title,
            content_length: content.length,
            tags: tags,
            ghost_url: `${ghostApiUrl}/mock-post-${Date.now()}`,
            note: 'Configure GHOST_ADMIN_KEY in Vercel environment variables'
          }
        }
      });
    }
    
    // 실제 Ghost API 호출은 여기서 구현
    // 지금은 mock 응답 반환
    return res.status(200).json({
      success: true,
      data: {
        published: true,
        ghost_post_id: `mock_${Date.now()}`,
        ghost_url: `${ghostApiUrl}/mock-published-post/`,
        title: title,
        content_preview: content.substring(0, 100) + '...',
        tags: tags,
        timestamp: new Date().toISOString(),
        status: 'Mock published successfully'
      }
    });
    
  } catch (error) {
    console.error('Ghost publishing error:', error);
    return res.status(500).json({
      success: false,
      error: error.message,
      fallback_action: 'Check Ghost API credentials and try again'
    });
  }
};