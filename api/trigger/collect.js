// Vercel Serverless Function - Trigger Collection
module.exports = async function handler(req, res) {
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
    const { batch_size = 10, subreddits = ['programming', 'technology', 'webdev'] } = req.body || {};
    
    const taskId = `collect-${Date.now()}`;
    
    // 실제 Reddit 수집 실행
    console.log(`Starting Reddit collection: ${subreddits.join(', ')} (batch_size: ${batch_size})`);
    
    const https = require('https');
    
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
    
    let totalCollected = 0;
    const collectedPosts = [];
    const errors = [];
    
    // 각 서브레딧에서 게시글 수집
    for (const subreddit of subreddits) {
      try {
        console.log(`Collecting from r/${subreddit}...`);
        
        // Reddit JSON API 사용 (인증 불필요)
        const redditUrl = `https://www.reddit.com/r/${subreddit}/hot.json?limit=${Math.ceil(batch_size / subreddits.length)}`;
        
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
              id: post.id,
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
              is_video: post.is_video || false,
              collected_at: new Date().toISOString()
            };
            
            collectedPosts.push(postData);
            totalCollected++;
            
            if (totalCollected >= batch_size) {
              break;
            }
          }
        }
        
        if (totalCollected >= batch_size) {
          break;
        }
        
      } catch (subredditError) {
        console.error(`Error collecting from r/${subreddit}:`, subredditError.message);
        errors.push(`r/${subreddit}: ${subredditError.message}`);
        continue;
      }
    }
    
    // 데이터베이스에 저장 시도 (선택적)
    const supabaseUrl = process.env.SUPABASE_URL;
    const supabaseKey = process.env.SUPABASE_ANON_KEY;
    
    if (supabaseUrl && supabaseKey && collectedPosts.length > 0) {
      try {
        // 수집된 게시글을 데이터베이스에 저장
        const response = await fetch(`${supabaseUrl}/rest/v1/posts`, {
          method: 'POST',
          headers: {
            'apikey': supabaseKey,
            'Authorization': `Bearer ${supabaseKey}`,
            'Content-Type': 'application/json',
            'Prefer': 'return=minimal'
          },
          body: JSON.stringify(collectedPosts)
        });
        
        if (response.ok) {
          console.log(`Successfully saved ${collectedPosts.length} posts to database`);
        } else {
          console.log('Failed to save to database, but collection succeeded');
        }
      } catch (dbError) {
        console.log('Database save failed:', dbError.message);
      }
    }

    res.status(200).json({
      success: true,
      data: {
        task_id: taskId,
        message: `Successfully collected ${totalCollected} posts from Reddit`,
        collected_count: totalCollected,
        batch_size: batch_size,
        subreddits_processed: subreddits,
        posts: collectedPosts,
        errors: errors.length > 0 ? errors : undefined,
        timestamp: new Date().toISOString(),
        next_steps: totalCollected > 0 ? 'Posts ready for AI processing' : 'No posts collected'
      }
    });
  } catch (error) {
    console.error('Collection error:', error);
    res.status(500).json({
      success: false,
      error: error.message,
      task_id: `collect-${Date.now()}`,
      timestamp: new Date().toISOString()
    });
  }
}