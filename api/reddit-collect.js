// Vercel Serverless Function - Real Reddit Collection
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
    
    // Reddit OAuth 토큰 가져오기
    const authResponse = await fetch('https://www.reddit.com/api/v1/access_token', {
      method: 'POST',
      headers: {
        'Authorization': `Basic ${Buffer.from(`${redditClientId}:${redditClientSecret}`).toString('base64')}`,
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'RedditGhostPublisher/1.0'
      },
      body: 'grant_type=client_credentials'
    });
    
    if (!authResponse.ok) {
      throw new Error(`Reddit OAuth failed: ${authResponse.status}`);
    }
    
    const authData = await authResponse.json();
    const accessToken = authData.access_token;
    
    // 각 서브레딧에서 포스트 수집
    const collectedPosts = [];
    
    for (const subreddit of subreddits.slice(0, 3)) { // 최대 3개 서브레딧
      try {
        const postsResponse = await fetch(
          `https://oauth.reddit.com/r/${subreddit}/hot.json?limit=${Math.min(limit, 25)}`,
          {
            headers: {
              'Authorization': `Bearer ${accessToken}`,
              'User-Agent': 'RedditGhostPublisher/1.0'
            }
          }
        );
        
        if (postsResponse.ok) {
          const postsData = await postsResponse.json();
          
          for (const post of postsData.data.children) {
            const postData = post.data;
            
            // 품질 필터링
            if (postData.score > 10 && postData.num_comments > 5 && !postData.stickied) {
              collectedPosts.push({
                id: postData.id,
                title: postData.title,
                subreddit: postData.subreddit,
                score: postData.score,
                comments: postData.num_comments,
                url: postData.url,
                selftext: postData.selftext,
                created_utc: postData.created_utc,
                author: postData.author,
                permalink: postData.permalink
              });
            }
          }
        }
      } catch (error) {
        console.log(`Error collecting from r/${subreddit}:`, error.message);
      }
    }
    
    // 점수순으로 정렬
    collectedPosts.sort((a, b) => b.score - a.score);
    
    res.status(200).json({
      success: true,
      data: {
        collected_posts: collectedPosts.length,
        posts: collectedPosts.slice(0, limit),
        subreddits_processed: subreddits,
        timestamp: new Date().toISOString(),
        next_steps: collectedPosts.length > 0 ? 'Ready for AI processing' : 'No qualifying posts found'
      }
    });
    
  } catch (error) {
    console.error('Reddit collection error:', error);
    res.status(500).json({
      success: false,
      error: error.message,
      fallback_action: 'Check Reddit API credentials and try again'
    });
  }
}