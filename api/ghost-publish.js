// Vercel Serverless Function - Ghost CMS Publishing
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
    const { posts, publish_status = 'draft' } = req.body || {};
    
    if (!posts || !Array.isArray(posts) || posts.length === 0) {
      return res.status(400).json({
        success: false,
        error: 'No posts provided for publishing'
      });
    }
    
    // Ghost API 설정
    const ghostApiUrl = process.env.GHOST_API_URL || 'https://american-trends.ghost.io';
    const ghostAdminKey = process.env.GHOST_ADMIN_KEY;
    
    if (!ghostAdminKey) {
      return res.status(200).json({
        success: true,
        data: {
          published_posts: 0,
          posts: posts.map(post => ({
            ...post,
            published: false,
            ghost_url: null,
            publishing_note: 'Ghost Admin Key not configured - using mock mode',
            mock_url: `${ghostApiUrl}/${post.title.toLowerCase().replace(/\s+/g, '-')}/`
          })),
          note: 'Configure GHOST_ADMIN_KEY in Vercel environment variables for real publishing'
        }
      });
    }
    
    // JWT 토큰 생성 함수
    function generateGhostJWT(adminKey) {
      const [keyId, secret] = adminKey.split(':');
      const now = Math.floor(Date.now() / 1000);
      
      const payload = {
        iat: now,
        exp: now + 300, // 5분
        aud: '/admin/'
      };
      
      const header = { alg: 'HS256', typ: 'JWT', kid: keyId };
      
      // 간단한 JWT 구현 (실제로는 라이브러리 사용 권장)
      const jwt = require('jsonwebtoken');
      return jwt.sign(payload, Buffer.from(secret, 'hex'), { 
        algorithm: 'HS256',
        header: { kid: keyId }
      });
    }
    
    let publishedPosts = [];
    let failedPosts = [];
    
    // JWT 토큰 생성 시도
    let ghostToken;
    try {
      ghostToken = generateGhostJWT(ghostAdminKey);
    } catch (error) {
      return res.status(200).json({
        success: true,
        data: {
          published_posts: 0,
          posts: posts.map(post => ({
            ...post,
            published: false,
            error: 'Invalid Ghost Admin Key format',
            note: 'Ghost Admin Key should be in format: keyId:keySecret'
          }))
        }
      });
    }
    
    // Ghost API 헤더
    const headers = {
      'Authorization': `Ghost ${ghostToken}`,
      'Content-Type': 'application/json',
      'Accept-Version': 'v5.0'
    };
    
    // 각 포스트를 Ghost에 발행 (최대 2개)
    for (const post of posts.slice(0, 2)) {
      try {
        // HTML 콘텐츠 생성
        const htmlContent = `
          <div class="reddit-post-meta">
            <p><strong>원본 포스트:</strong> <a href="https://reddit.com${post.permalink}" target="_blank">r/${post.subreddit}</a></p>
            <p><strong>점수:</strong> ${post.score} | <strong>댓글:</strong> ${post.comments}</p>
          </div>
          
          <div class="post-summary">
            ${post.summary || 'AI-generated summary not available.'}
          </div>
          
          ${post.selftext ? `
          <div class="original-content">
            <h3>원본 내용</h3>
            <p>${post.selftext.substring(0, 1000)}${post.selftext.length > 1000 ? '...' : ''}</p>
          </div>` : ''}
          
          <div class="reddit-link">
            <p><a href="https://reddit.com${post.permalink}" target="_blank" class="reddit-link-button">Reddit에서 전체 토론 보기 →</a></p>
          </div>
        `;
        
        // Ghost 포스트 데이터
        const ghostPostData = {
          posts: [{
            title: post.enhanced_title || post.title,
            html: htmlContent,
            status: publish_status,
            visibility: 'public',
            featured: post.quality_score >= 8,
            tags: (post.tags || [post.subreddit]).map(tag => ({ name: tag })),
            meta_title: post.enhanced_title || post.title,
            meta_description: post.summary,
            custom_excerpt: post.summary?.substring(0, 300),
            published_at: publish_status === 'published' ? new Date().toISOString() : null
          }]
        };
        
        // Ghost API 호출
        const response = await fetch(`${ghostApiUrl}/ghost/api/admin/posts/`, {
          method: 'POST',
          headers,
          body: JSON.stringify(ghostPostData)
        });
        
        if (response.ok) {
          const result = await response.json();
          const ghostPost = result.posts[0];
          
          publishedPosts.push({
            ...post,
            published: true,
            ghost_id: ghostPost.id,
            ghost_url: ghostPost.url,
            ghost_slug: ghostPost.slug,
            publish_status: ghostPost.status,
            published_at: ghostPost.published_at
          });
        } else {
          const errorText = await response.text();
          throw new Error(`Ghost API error ${response.status}: ${errorText}`);
        }
        
      } catch (error) {
        console.error(`Ghost publishing error for post ${post.id}:`, error);
        
        failedPosts.push({
          ...post,
          published: false,
          error: error.message,
          ghost_url: null
        });
      }
    }
    
    res.status(200).json({
      success: true,
      data: {
        published_posts: publishedPosts.length,
        failed_posts: failedPosts.length,
        successful_posts: publishedPosts,
        failed_posts: failedPosts,
        total_processed: publishedPosts.length + failedPosts.length,
        ghost_admin_url: `${ghostApiUrl}/ghost/`,
        timestamp: new Date().toISOString(),
        next_steps: publishedPosts.length > 0 ? 'Check Ghost admin for published posts' : 'Review publishing errors'
      }
    });
    
  } catch (error) {
    console.error('Ghost publishing error:', error);
    res.status(500).json({
      success: false,
      error: error.message,
      fallback_action: 'Check Ghost API configuration and try again'
    });
  }
}