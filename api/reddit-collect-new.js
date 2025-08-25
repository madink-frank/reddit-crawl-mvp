// 완전히 새로운 Reddit 수집 API
module.exports = async (req, res) => {
  // CORS 설정
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }
  
  if (req.method !== 'POST') {
    return res.status(405).json({ success: false, error: 'Method not allowed' });
  }
  
  try {
    // 요청 파라미터 파싱
    const body = req.body || {};
    const subreddits = body.subreddits || ['programming', 'technology', 'webdev'];
    const limit = Math.min(body.limit || 10, 25);
    
    const results = {
      success: true,
      timestamp: new Date().toISOString(),
      requested_subreddits: subreddits,
      requested_limit: limit,
      collected_posts: 0,
      posts: [],
      debug_log: []
    };
    
    results.debug_log.push(`Starting collection from ${subreddits.length} subreddits`);
    
    // 각 서브레딧에서 데이터 수집
    for (let i = 0; i < subreddits.length; i++) {
      const subreddit = subreddits[i];
      results.debug_log.push(`Processing subreddit ${i + 1}/${subreddits.length}: r/${subreddit}`);
      
      try {
        const url = `https://www.reddit.com/r/${subreddit}/hot.json?limit=10`;
        results.debug_log.push(`Fetching: ${url}`);
        
        // fetch API 사용
        const response = await fetch(url, {
          headers: {
            'User-Agent': 'reddit-ghost-publisher/2.0.0 (by /u/publisher)'
          }
        });
        
        results.debug_log.push(`Response status: ${response.status}`);
        
        if (!response.ok) {
          results.debug_log.push(`HTTP error: ${response.status} ${response.statusText}`);
          continue;
        }
        
        const data = await response.json();
        results.debug_log.push(`JSON parsed successfully`);
        
        if (data && data.data && data.data.children && Array.isArray(data.data.children)) {
          results.debug_log.push(`Found ${data.data.children.length} posts in r/${subreddit}`);
          
          for (const child of data.data.children) {
            if (results.collected_posts >= limit) {
              results.debug_log.push(`Reached limit of ${limit} posts`);
              break;
            }
            
            const post = child.data;
            if (!post || !post.title) {
              results.debug_log.push(`Skipping invalid post`);
              continue;
            }
            
            // 필터링
            if (post.over_18) {
              results.debug_log.push(`Skipping NSFW: ${post.title.substring(0, 50)}...`);
              continue;
            }
            
            if (post.stickied) {
              results.debug_log.push(`Skipping stickied: ${post.title.substring(0, 50)}...`);
              continue;
            }
            
            // 게시글 데이터 생성
            const postData = {
              reddit_post_id: post.id,
              title: post.title,
              subreddit: post.subreddit,
              author: post.author,
              score: post.score || 0,
              num_comments: post.num_comments || 0,
              created_utc: post.created_utc,
              url: post.url,
              selftext: post.selftext || '',
              permalink: `https://reddit.com${post.permalink}`,
              over_18: post.over_18 || false,
              domain: post.domain || '',
              is_video: post.is_video || false
            };
            
            results.posts.push(postData);
            results.collected_posts++;
            results.debug_log.push(`✅ Collected: "${post.title.substring(0, 50)}..." (score: ${post.score})`);
          }
        } else {
          results.debug_log.push(`Invalid data structure from r/${subreddit}`);
          results.debug_log.push(`Data keys: ${Object.keys(data || {}).join(', ')}`);
        }
        
      } catch (subredditError) {
        results.debug_log.push(`❌ Error with r/${subreddit}: ${subredditError.message}`);
      }
      
      if (results.collected_posts >= limit) {
        break;
      }
    }
    
    results.debug_log.push(`🏁 Collection complete: ${results.collected_posts} posts collected`);
    
    return res.status(200).json({
      success: true,
      data: {
        collected_posts: results.collected_posts,
        message: `Reddit collection completed: ${results.collected_posts} posts collected`,
        subreddits_processed: subreddits,
        posts: results.posts,
        timestamp: results.timestamp,
        next_steps: results.collected_posts > 0 ? 'Ready for AI processing' : 'No posts collected - check debug info',
        debug_info: results.debug_log
      }
    });
    
  } catch (error) {
    return res.status(500).json({
      success: false,
      error: error.message,
      stack: error.stack,
      timestamp: new Date().toISOString()
    });
  }
};