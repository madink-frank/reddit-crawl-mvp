// Reddit 수집 API v2 - RSS 기반 (캐시 우회용)
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
    const subreddits = body.subreddits || ['programming'];
    const limit = Math.min(body.limit || 5, 10);
    
    const results = {
      success: true,
      timestamp: new Date().toISOString(),
      version: 'v2-rss',
      collected_posts: 0,
      posts: [],
      debug_log: []
    };
    
    results.debug_log.push(`🚀 Reddit API v2 starting - RSS method`);
    results.debug_log.push(`Subreddits: ${subreddits.join(', ')}`);
    results.debug_log.push(`Limit: ${limit}`);
    
    // 간단한 테스트: 하나의 서브레딧만 처리
    const subreddit = subreddits[0];
    results.debug_log.push(`Processing r/${subreddit}`);
    
    try {
      // Reddit RSS URL
      const rssUrl = `https://www.reddit.com/r/${subreddit}/hot/.rss?limit=5`;
      results.debug_log.push(`RSS URL: ${rssUrl}`);
      
      // RSS 피드 가져오기
      const response = await fetch(rssUrl, {
        headers: {
          'User-Agent': 'reddit-v2-collector/1.0.0'
        }
      });
      
      results.debug_log.push(`Fetch completed - Status: ${response.status}`);
      
      if (!response.ok) {
        results.debug_log.push(`❌ HTTP Error: ${response.status} ${response.statusText}`);
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const rssText = await response.text();
      results.debug_log.push(`RSS text length: ${rssText.length} characters`);
      results.debug_log.push(`RSS preview: ${rssText.substring(0, 200)}...`);
      
      // 간단한 제목 추출 (정규식)
      const titleMatches = rssText.match(/<title><!\[CDATA\[(.*?)\]\]><\/title>/g);
      results.debug_log.push(`Found ${titleMatches ? titleMatches.length : 0} title matches`);
      
      if (titleMatches && titleMatches.length > 0) {
        // 첫 번째 제목은 보통 서브레딧 제목이므로 건너뛰기
        for (let i = 1; i < Math.min(titleMatches.length, limit + 1); i++) {
          const titleMatch = titleMatches[i].match(/<title><!\[CDATA\[(.*?)\]\]><\/title>/);
          if (titleMatch && titleMatch[1]) {
            const title = titleMatch[1].trim();
            
            results.posts.push({
              reddit_post_id: `test_${i}`,
              title: title,
              subreddit: subreddit,
              url: `https://reddit.com/r/${subreddit}`,
              source: 'rss-v2'
            });
            
            results.collected_posts++;
            results.debug_log.push(`✅ Extracted: "${title.substring(0, 50)}..."`);
          }
        }
      }
      
    } catch (fetchError) {
      results.debug_log.push(`❌ Fetch error: ${fetchError.message}`);
    }
    
    results.debug_log.push(`🏁 V2 collection complete: ${results.collected_posts} posts`);
    
    return res.status(200).json({
      success: true,
      data: {
        collected_posts: results.collected_posts,
        message: `V2 RSS collection: ${results.collected_posts} posts`,
        posts: results.posts,
        timestamp: results.timestamp,
        debug_info: results.debug_log,
        version: 'v2-rss'
      }
    });
    
  } catch (error) {
    return res.status(500).json({
      success: false,
      error: error.message,
      stack: error.stack,
      version: 'v2-rss'
    });
  }
};