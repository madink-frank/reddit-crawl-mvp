module.exports = async (req, res) => {
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
    const { title, content, tags = [] } = req.body || {};
    
    if (!title || !content) {
      return res.status(400).json({
        success: false,
        error: 'Title and content are required'
      });
    }
    
    const ghostAdminKey = process.env.GHOST_ADMIN_KEY;
    const ghostApiUrl = process.env.GHOST_API_URL || 'https://american-trends.ghost.io';
    
    if (!ghostAdminKey) {
      return res.status(200).json({
        success: true,
        data: {
          published: false,
          message: 'Ghost API key not configured - mock publish mode',
          mock_data: {
            title: title,
            content_length: content.length,
            tags: tags,
            ghost_url: `${ghostApiUrl}/mock-post-${Date.now()}`,
            note: 'Configure GHOST_ADMIN_KEY in Vercel environment variables'
          }
        }
      });
    }
    
    // 실제 Ghost API 호출 구현
    try {
      const jwt = require('jsonwebtoken');
      
      // Ghost Admin Key 파싱 (key_id:secret 형식)
      const [keyId, secret] = ghostAdminKey.split(':');
      
      if (!keyId || !secret) {
        throw new Error('Invalid Ghost Admin Key format. Expected key_id:secret');
      }
      
      // JWT 토큰 생성
      const iat = Math.floor(Date.now() / 1000);
      const exp = iat + 300; // 5분 후 만료
      
      const token = jwt.sign(
        {
          iat: iat,
          exp: exp,
          aud: '/v4/admin/'
        },
        Buffer.from(secret, 'hex'),
        {
          algorithm: 'HS256',
          header: {
            kid: keyId
          }
        }
      );
      
      // Ghost API URL 구성
      const apiUrl = `${ghostApiUrl}/ghost/api/v4/admin/posts/`;
      
      // HTML 콘텐츠 생성 (Markdown to HTML 변환)
      const htmlContent = content.replace(/\n/g, '<br>');
      
      // 출처 고지 추가
      const sourceFooter = `
        <hr>
        <p><strong>Source:</strong> <a href="#" target="_blank">Reddit</a></p>
        <p><em>Media and usernames belong to their respective owners.</em></p>
        <p><em>Takedown requests will be honored.</em></p>
      `;
      
      const fullHtmlContent = htmlContent + sourceFooter;
      
      // Ghost 게시글 데이터 구성
      const postData = {
        posts: [{
          title: title,
          html: fullHtmlContent,
          status: 'published',
          tags: tags.map(tag => ({ name: tag })),
          excerpt: content.substring(0, 300) + '...',
          created_at: new Date().toISOString()
        }]
      };
      
      // Ghost API 호출
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Authorization': `Ghost ${token}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify(postData)
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(`Ghost API error ${response.status}: ${JSON.stringify(errorData)}`);
      }
      
      const result = await response.json();
      
      if (result.posts && result.posts[0]) {
        const publishedPost = result.posts[0];
        
        return res.status(200).json({
          success: true,
          data: {
            published: true,
            ghost_post_id: publishedPost.id,
            ghost_url: publishedPost.url,
            ghost_slug: publishedPost.slug,
            title: publishedPost.title,
            status: publishedPost.status,
            tags: publishedPost.tags ? publishedPost.tags.map(tag => tag.name) : [],
            published_at: publishedPost.published_at,
            timestamp: new Date().toISOString()
          }
        });
      } else {
        throw new Error('Unexpected response format from Ghost API');
      }
      
    } catch (apiError) {
      console.error('Ghost API error:', apiError);
      
      // Fallback to mock data if API fails
      return res.status(200).json({
        success: true,
        data: {
          published: false,
          message: 'Ghost API error - falling back to mock mode',
          error: apiError.message,
          mock_data: {
            title: title,
            content_length: content.length,
            tags: tags,
            ghost_url: `${ghostApiUrl}/mock-post-${Date.now()}`,
            note: 'Check Ghost Admin Key and API URL'
          },
          timestamp: new Date().toISOString()
        }
      });
    }
    
  } catch (error) {
    console.error('Ghost publishing error:', error);
    return res.status(500).json({
      success: false,
      error: error.message,
      fallback_action: 'Check Ghost API credentials and try again'
    });
  }
};