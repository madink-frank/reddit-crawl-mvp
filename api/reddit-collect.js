module.exports = (req, res) => {
  // Enhanced CORS headers for Ghost dashboard integration
  const allowedOrigins = [
    'https://american-trends.ghost.io',
    'https://www.american-trends.ghost.io',
    'http://localhost:3000',
    'http://localhost:8000',
    'http://localhost:8083'
  ];
  
  const origin = req.headers.origin;
  if (allowedOrigins.includes(origin)) {
    res.setHeader('Access-Control-Allow-Origin', origin);
  } else {
    res.setHeader('Access-Control-Allow-Origin', '*'); // Fallback for development
  }
  
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-API-Key, X-Requested-With');
  res.setHeader('Access-Control-Allow-Credentials', 'true');
  res.setHeader('Access-Control-Max-Age', '86400');
  
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }
  
  if (req.method !== 'POST') {
    return res.status(405).json({ success: false, error: 'Method not allowed' });
  }
  
  try {
    const { subreddits = ['programming', 'technology', 'webdev'], limit = 10 } = req.body || {};
    
    // Reddit 공개 JSON API 사용 (자격 증명 불필요)
    console.log(`Starting Reddit collection from subreddits: ${subreddits.join(', ')}`);
    console.log(`Target limit: ${limit} posts`);
    
    // 실제 Reddit API 호출 구현
    try {
      // Reddit API 없이 직접 HTTP 요청으로 공개 데이터 수집
      const https = require('https');
      const { URL } = require('url');
      
      let totalCollected = 0;
      const collectedPosts = [];
      
      // 각 서브레딧에서 게시글 수집
      for (const subreddit of subreddits) {
        try {
          console.log(`Collecting from r/${subreddit}...`);
          
          // Reddit JSON API 사용 (인증 불필요)
          const redditUrl = `https://www.reddit.com/r/${subreddit}/hot.json?limit=${Math.ceil(limit / subreddits.length)}`;
          
          const redditData = await fetchRedditData(redditUrl);
          
          if (redditData && redditData.data && redditData.data.children) {
            for (const child of redditData.data.children) {
              const post = child.data;
              
              // NSFW 필터링
              if (post.over_18) {
                continue;
              }
              
              // 스티키 게시글 제외
              if (post.stickied) {
                continue;
              }
              
              // 삭제된 게시글 제외
              if (post.removed_by_category || !post.title) {
                continue;
              }
              
              const postData = {
                reddit_post_id: post.id,
                title: post.title,
                subreddit: post.subreddit,
                author: post.author,
                score: post.score,
                num_comments: post.num_comments,
                created_utc: post.created_utc,
                url: post.url,
                selftext: post.selftext || '',
                permalink: `https://reddit.com${post.permalink}`,
                over_18: post.over_18,
                thumbnail: post.thumbnail !== 'self' && post.thumbnail !== 'default' ? post.thumbnail : null,
                domain: post.domain,
                is_video: post.is_video || false
              };
              
              collectedPosts.push(postData);
              totalCollected++;
              
              if (totalCollected >= limit) {
                break;
              }
            }
          }
          
          if (totalCollected >= limit) {
            break;
          }
          
        } catch (subredditError) {
          console.error(`Error collecting from r/${subreddit}:`, subredditError.message);
          continue;
        }
      }
      
      // Helper function to fetch Reddit data
      function fetchRedditData(url) {
        return new Promise((resolve, reject) => {
          const options = {
            headers: {
              'User-Agent': 'reddit-ghost-publisher/1.0.0 (by /u/reddit-publisher)'
            }
          };
          
          https.get(url, options, (response) => {
            let data = '';
            
            response.on('data', (chunk) => {
              data += chunk;
            });
            
            response.on('end', () => {
              try {
                const jsonData = JSON.parse(data);
                resolve(jsonData);
              } catch (parseError) {
                reject(parseError);
              }
            });
          }).on('error', (error) => {
            reject(error);
          });
        });
      }
      
      return res.status(200).json({
        success: true,
        data: {
          collected_posts: totalCollected,
          message: 'Reddit collection completed successfully',
          subreddits_processed: subreddits,
          posts: collectedPosts,
          timestamp: new Date().toISOString(),
          next_steps: 'Ready for AI processing'
        }
      });
      
    } catch (apiError) {
      console.error('Reddit API error:', apiError);
      
      // Reddit API 실패 시 에러 반환
      return res.status(500).json({
        success: false,
        error: 'Reddit API call failed',
        details: apiError.message,
        subreddits_requested: subreddits,
        timestamp: new Date().toISOString(),
        message: 'Check Reddit API credentials and rate limits'
      });
    }
    
  } catch (error) {
    console.error('Reddit collection error:', error);
    return res.status(500).json({
      success: false,
      error: error.message,
      fallback_action: 'Check Reddit API credentials and try again'
    });
  }
};