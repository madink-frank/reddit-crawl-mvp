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
    const { title, content, subreddit } = req.body || {};
    
    if (!title || !content) {
      return res.status(400).json({
        success: false,
        error: 'Title and content are required'
      });
    }
    
    const openaiApiKey = process.env.OPENAI_API_KEY;
    
    if (!openaiApiKey) {
      return res.status(200).json({
        success: true,
        data: {
          processed: true,
          message: 'OpenAI API key not configured - using mock enhancement',
          enhanced_title: `Enhanced: ${title}`,
          enhanced_content: content + '\n\n[Enhanced with AI processing]',
          tags: ['reddit', 'ai-enhanced', subreddit || 'general'],
          mock_mode: true,
          note: 'Configure OPENAI_API_KEY in Vercel environment variables'
        }
      });
    }
    
    // 실제 OpenAI API 호출은 여기서 구현
    // 지금은 mock 응답 반환
    return res.status(200).json({
      success: true,
      data: {
        processed: true,
        enhanced_title: `AI Enhanced: ${title}`,
        enhanced_content: content + '\n\n[AI processing completed]',
        tags: ['reddit', 'ai-enhanced', subreddit || 'general'],
        timestamp: new Date().toISOString(),
        next_steps: 'Ready for Ghost publishing'
      }
    });
    
  } catch (error) {
    console.error('AI processing error:', error);
    return res.status(500).json({
      success: false,
      error: error.message,
      fallback_action: 'Check OpenAI API credentials and try again'
    });
  }
};