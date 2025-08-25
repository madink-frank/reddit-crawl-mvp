// 완전히 새로운 Reddit 수집 API - RSS 기반
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
    
    results.debug_log.push(`🚀 Starting RSS collection from ${subreddits.length} subreddits`);
    results.debug_log.push(`Target limit: ${limit} posts`);
    
    // XML 파서 함수 (간단한 정규식 기반)
    function parseRSSItem(xmlText) {
      const items = [];
      const itemRegex = /<item>(.*?)<\/item>/gs;
      let match;
      
      while ((match = itemRegex.exec(xmlText)) !== null) {
        const itemXml = match[1];
        
        const title = (itemXml.match(/<title><!\[CDATA\[(.*?)\]\]><\/title>/) || [])[1];
        const link = (itemXml.match(/<link>(.*?)<\/link>/) || [])[1];
        const description = (itemXml.match(/<description><!\[CDATA\[(.*?)\]\]><\/description>/) || [])[1];
        const pubDate = (itemXml.match(/<pubDate>(.*?)<\/pubDate>/) || [])[1];
        
        if (title && link) {
          // Reddit 링크에서 정보 추출
          const redditMatch = link.match(/reddit\.com\/r\/(\w+)\/comments\/(\w+)\//);
          const subreddit = redditMatch ? redditMatch[1] : 'unknown';
          const postId = redditMatch ? redditMatch[2] : 'unknown';
          
          items.push({
            reddit_post_id: postId,
            title: title.trim(),
            subreddit: subreddit,
            url: link,
            description: description ? description.trim() : '',
            pub_date: pubDate,
            permalink: link,
            source: 'rss'
          });
        }
      }
      
      return items;
    }
    
    // 각 서브레딧에서 RSS 데이터 수집
    for (let i = 0; i < subreddits.length; i++) {
      const subreddit = subreddits[i];
      results.debug_log.push(`📡 Processing subreddit ${i + 1}/${subreddits.length}: r/${subreddit}`);
      
      try {
        // Reddit RSS URL
        const rssUrl = `https://www.reddit.com/r/${subreddit}/hot/.rss?limit=10`;
        results.debug_log.push(`Fetching RSS: ${rssUrl}`);
        
        // RSS 피드 가져오기
        const response = await fetch(rssUrl, {
          headers: {
            'User-Agent': 'reddit-rss-collector/1.0.0'
          }
        });
        
        results.debug_log.push(`RSS response status: ${response.status}`);
        
        if (!response.ok) {
          results.debug_log.push(`❌ RSS HTTP error: ${response.status} ${response.statusText}`);
          continue;
        }
        
        const rssText = await response.text();
        results.debug_log.push(`RSS text received, length: ${rssText.length}`);
        
        // RSS XML 파싱
        const items = parseRSSItem(rssText);
        results.debug_log.push(`📝 Parsed ${items.length} items from RSS`);
        
        // 게시글 추가
        for (const item of items) {
          if (results.collected_posts >= limit) {
            results.debug_log.push(`🎯 Reached limit of ${limit} posts`);
            break;
          }
          
          // 중복 체크 (같은 post_id)
          if (results.posts.some(p => p.reddit_post_id === item.reddit_post_id)) {
            results.debug_log.push(`⏭️ Skipping duplicate: ${item.title.substring(0, 50)}...`);
            continue;
          }
          
          results.posts.push(item);
          results.collected_posts++;
          results.debug_log.push(`✅ Added: "${item.title.substring(0, 50)}..." from r/${item.subreddit}`);
        }
        
      } catch (subredditError) {
        results.debug_log.push(`❌ Error with r/${subreddit}: ${subredditError.message}`);
      }
      
      if (results.collected_posts >= limit) {
        break;
      }
    }
    
    results.debug_log.push(`🏁 RSS collection complete: ${results.collected_posts} posts collected`);
    
    return res.status(200).json({
      success: true,
      data: {
        collected_posts: results.collected_posts,
        message: `RSS collection completed: ${results.collected_posts} posts collected`,
        subreddits_processed: subreddits,
        posts: results.posts,
        timestamp: results.timestamp,
        next_steps: results.collected_posts > 0 ? 'Ready for AI processing' : 'No posts collected - check debug info',
        debug_info: results.debug_log,
        method: 'RSS'
      }
    });
    
  } catch (error) {
    return res.status(500).json({
      success: false,
      error: error.message,
      stack: error.stack,
      timestamp: new Date().toISOString(),
      method: 'RSS'
    });
  }
};