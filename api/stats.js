// Vercel Serverless Function - Statistics
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
    const supabaseUrl = process.env.SUPABASE_URL;
    const supabaseKey = process.env.SUPABASE_ANON_KEY;
    
    if (!supabaseUrl || !supabaseKey) {
      // 모의 데이터 반환
      const mockStats = {
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
      
      return res.status(200).json(mockStats);
    }
    
    // 실제 Supabase 데이터 조회
    const headers = {
      'apikey': supabaseKey,
      'Authorization': `Bearer ${supabaseKey}`,
      'Content-Type': 'application/json'
    };
    
    // 전체 포스트 수
    const totalResponse = await fetch(`${supabaseUrl}/rest/v1/posts?select=count`, {
      headers: { ...headers, 'Prefer': 'count=exact' }
    });
    
    // AI 처리된 포스트 수
    const aiResponse = await fetch(`${supabaseUrl}/rest/v1/posts?select=count&summary_ko=not.is.null`, {
      headers: { ...headers, 'Prefer': 'count=exact' }
    });
    
    // 발행된 포스트 수
    const publishedResponse = await fetch(`${supabaseUrl}/rest/v1/posts?select=count&ghost_url=not.is.null`, {
      headers: { ...headers, 'Prefer': 'count=exact' }
    });
    
    // 오늘 수집된 포스트 수
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const todayResponse = await fetch(`${supabaseUrl}/rest/v1/posts?select=count&created_at=gte.${today.toISOString()}`, {
      headers: { ...headers, 'Prefer': 'count=exact' }
    });
    
    // 최근 포스트
    const recentResponse = await fetch(`${supabaseUrl}/rest/v1/posts?select=reddit_post_id,title,subreddit,score,num_comments,summary_ko,ghost_url,created_at&order=created_at.desc&limit=5`, {
      headers
    });
    
    const totalCount = parseInt(totalResponse.headers.get('content-range')?.split('/')[1] || '0');
    const aiCount = parseInt(aiResponse.headers.get('content-range')?.split('/')[1] || '0');
    const publishedCount = parseInt(publishedResponse.headers.get('content-range')?.split('/')[1] || '0');
    const todayCount = parseInt(todayResponse.headers.get('content-range')?.split('/')[1] || '0');
    const recentPosts = await recentResponse.json();
    
    const successRate = totalCount > 0 ? Math.round((publishedCount / totalCount) * 100 * 10) / 10 : 0;
    
    const statsData = {
      success: true,
      data: {
        total_posts: totalCount,
        ai_processed: aiCount,
        published: publishedCount,
        collected_today: todayCount,
        success_rate: successRate,
        recent_posts: (recentPosts || []).map(post => ({
          id: post.reddit_post_id,
          title: post.title?.length > 60 ? post.title.substring(0, 60) + '...' : post.title,
          subreddit: post.subreddit,
          score: post.score,
          comments: post.num_comments,
          processed: !!post.summary_ko,
          published: !!post.ghost_url,
          ghost_url: post.ghost_url,
          created_at: post.created_at
        }))
      },
      timestamp: new Date().toISOString()
    };
    
    res.status(200).json(statsData);
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
}