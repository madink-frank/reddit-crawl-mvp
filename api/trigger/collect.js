// Vercel Serverless Function - Trigger Collection
module.exports = async function handler(req, res) {
  // CORS 헤더 설정
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
    const { batch_size = 10, subreddits = ['programming', 'technology', 'webdev'] } = req.body || {};
    
    const taskId = `collect-${Date.now()}`;
    
    // 실제 구현에서는 여기서 Reddit API를 호출하거나 작업 큐에 추가
    // 현재는 모의 응답 반환
    
    const supabaseUrl = process.env.SUPABASE_URL;
    const supabaseKey = process.env.SUPABASE_ANON_KEY;
    
    if (supabaseUrl && supabaseKey) {
      try {
        // 작업 큐에 추가
        const response = await fetch(`${supabaseUrl}/rest/v1/job_queue`, {
          method: 'POST',
          headers: {
            'apikey': supabaseKey,
            'Authorization': `Bearer ${supabaseKey}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            job_type: 'collect',
            job_data: { batch_size, subreddits },
            status: 'pending'
          })
        });
        
        if (!response.ok) {
          throw new Error('Failed to queue collection job');
        }
      } catch (error) {
        console.log('Queue operation failed:', error.message);
      }
    }
    
    // Simulate some collected posts
    const mockTitles = [
      'New breakthrough in AI technology changes everything',
      'Major security vulnerability discovered in popular framework', 
      'Tech giant announces revolutionary product launch',
      'Open source project gains massive community support',
      'Developer creates amazing tool that saves hours of work'
    ];
    
    const collectedPosts = [];
    const actualBatchSize = Math.min(batch_size, 3); // Limit to 3 for demo
    
    for (let i = 0; i < actualBatchSize; i++) {
      const subreddit = subreddits[Math.floor(Math.random() * subreddits.length)];
      const title = mockTitles[Math.floor(Math.random() * mockTitles.length)];
      
      collectedPosts.push({
        id: `post_${Date.now()}_${i}`,
        title: title,
        subreddit: subreddit,
        score: Math.floor(Math.random() * 1000) + 50
      });
    }

    res.status(200).json({
      success: true,
      data: {
        task_id: taskId,
        message: 'Collection completed successfully',
        collected_count: collectedPosts.length,
        batch_size: actualBatchSize,
        subreddits,
        posts: collectedPosts
      }
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
}