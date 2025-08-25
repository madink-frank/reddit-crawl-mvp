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
    
    // Atom 피드 파서 함수 (Reddit은 Atom 형식 사용)
    function parseAtomFeed(xmlText) {
      const items = [];
      const entryRegex = /<entry>(.*?)<\/entry>/gs;
      let match;
      
      while ((match = entryRegex.exec(xmlText)) !== null) {
        const entryXml = match[1];
        
        // Atom 형식으로 파싱
        const titleMatch = entryXml.match(/<title[^>]*>(.*?)<\/title>/s);
        const linkMatch = entryXml.match(/<link[^>]*href="([^"]*)"[^>]*>/);
        const idMatch = entryXml.match(/<id[^>]*>(.*?)<\/id>/);
        const authorMatch = entryXml.match(/<author><name>([^<]*)<\/name>/);
        const publishedMatch = entryXml.match(/<published[^>]*>(.*?)<\/published>/);
        
        if (titleMatch && titleMatch[1] && linkMatch && linkMatch[1]) {
          const title = titleMatch[1].trim();
          const link = linkMatch[1];
          const postId = idMatch ? idMatch[1].replace('t3_', '') : 'unknown';
          const author = authorMatch ? authorMatch[1].replace('/u/', '') : 'unknown';
          const published = publishedMatch ? publishedMatch[1] : '';
          
          // Reddit 링크에서 서브레딧 추출
          const redditMatch = link.match(/reddit\.com\/r\/(\w+)\//);
          const subreddit = redditMatch ? redditMatch[1] : 'unknown';
          
          items.push({
            reddit_post_id: postId,
            title: title,
            subreddit: subreddit,
            author: author,
            url: link,
            permalink: link,
            published: published,
            source: 'atom'
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
        
        // RSS 피드 가져오기 (브라우저 User-Agent 사용)
        const response = await fetch(rssUrl, {
          headers: {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, text/xml, application/atom+xml',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache'
          }
        });
        
        results.debug_log.push(`RSS response status: ${response.status}`);
        
        if (!response.ok) {
          results.debug_log.push(`❌ RSS HTTP error: ${response.status} ${response.statusText}`);
          continue;
        }
        
        const rssText = await response.text();
        results.debug_log.push(`RSS text received, length: ${rssText.length}`);
        
        // Atom XML 파싱
        const items = parseAtomFeed(rssText);
        results.debug_log.push(`📝 Parsed ${items.length} items from Atom feed`);
        
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
    
    results.debug_log.push(`🏁 Atom feed collection complete: ${results.collected_posts} posts collected`);
    
    return res.status(200).json({
      success: true,
      data: {
        collected_posts: results.collected_posts,
        message: `Atom feed collection completed: ${results.collected_posts} posts collected`,
        subreddits_processed: subreddits,
        posts: results.posts,
        timestamp: results.timestamp,
        next_steps: results.collected_posts > 0 ? 'Ready for AI processing' : 'No posts collected - check debug info',
        debug_info: results.debug_log,
        method: 'Atom'
      }
    });
    
  } catch (error) {
    return res.status(500).json({
      success: false,
      error: error.message,
      stack: error.stack,
      timestamp: new Date().toISOString(),
      method: 'Atom'
    });
  }
};