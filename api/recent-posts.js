module.exports = async (req, res) => {
  // Enhanced CORS headers
  const allowedOrigins = [
    'https://american-trends.ghost.io',
    'https://www.american-trends.ghost.io',
    'https://reddit-crawl-mvp.vercel.app',
    'http://localhost:3000',
    'http://localhost:8000',
    'http://localhost:8083'
  ];
  
  const origin = req.headers.origin;
  if (allowedOrigins.includes(origin)) {
    res.setHeader('Access-Control-Allow-Origin', origin);
  } else {
    res.setHeader('Access-Control-Allow-Origin', '*');
  }
  
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-API-Key, X-Requested-With');
  res.setHeader('Access-Control-Allow-Credentials', 'true');
  res.setHeader('Access-Control-Max-Age', '86400');
  
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }
  
  if (req.method !== 'GET') {
    return res.status(405).json({ success: false, error: 'Method not allowed' });
  }
  
  try {
    const { limit = 5 } = req.query;
    
    // Try Supabase first
    const supabaseUrl = process.env.SUPABASE_URL;
    const supabaseKey = process.env.SUPABASE_ANON_KEY;
    
    if (supabaseUrl && supabaseKey) {
      try {
        const response = await fetch(`${supabaseUrl}/rest/v1/posts?select=*&order=created_at.desc&limit=${limit}`, {
          headers: {
            'apikey': supabaseKey,
            'Authorization': `Bearer ${supabaseKey}`,
            'Content-Type': 'application/json'
          }
        });
        
        if (response.ok) {
          const posts = await response.json();
          
          return res.status(200).json({
            success: true,
            posts: posts.map(post => ({
              id: post.reddit_post_id || post.id,
              title: post.title,
              subreddit: post.subreddit,
              score: post.score || 0,
              num_comments: post.num_comments || 0,
              created_at: post.created_at,
              ghost_url: post.ghost_url,
              processed: !!post.summary_ko
            })),
            data_source: 'supabase'
          });
        }
      } catch (supabaseError) {
        console.log('Supabase query failed:', supabaseError.message);
      }
    }
    
    // Try PostgreSQL
    const databaseUrl = process.env.DATABASE_URL;
    
    if (databaseUrl) {
      try {
        const { Pool } = require('pg');
        
        const pool = new Pool({
          connectionString: databaseUrl,
          ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false
        });
        
        const query = `
          SELECT 
            reddit_post_id,
            title,
            subreddit,
            score,
            num_comments,
            created_at,
            ghost_url,
            summary_ko IS NOT NULL as processed
          FROM posts 
          ORDER BY created_at DESC 
          LIMIT $1
        `;
        
        const result = await pool.query(query, [parseInt(limit)]);
        await pool.end();
        
        return res.status(200).json({
          success: true,
          posts: result.rows.map(post => ({
            id: post.reddit_post_id,
            title: post.title,
            subreddit: post.subreddit,
            score: post.score || 0,
            num_comments: post.num_comments || 0,
            created_at: post.created_at,
            ghost_url: post.ghost_url,
            processed: post.processed
          })),
          data_source: 'postgresql'
        });
        
      } catch (dbError) {
        console.log('PostgreSQL query failed:', dbError.message);
      }
    }
    
    // Fallback to mock data
    const mockPosts = [
      {
        id: 'mock_1',
        title: 'Apple accidentally leaked its own top secret hardware in software code',
        subreddit: 'technology',
        score: 1250,
        num_comments: 234,
        created_at: new Date(Date.now() - 3600000).toISOString(), // 1 hour ago
        ghost_url: null,
        processed: false
      },
      {
        id: 'mock_2',
        title: 'Volkswagen locks horsepower behind paid subscription',
        subreddit: 'cars',
        score: 890,
        num_comments: 156,
        created_at: new Date(Date.now() - 7200000).toISOString(), // 2 hours ago
        ghost_url: 'https://american-trends.ghost.io/sample-mock-2',
        processed: true
      },
      {
        id: 'mock_3',
        title: 'AI experts return from China stunned: The U.S. grid is so weak',
        subreddit: 'artificial',
        score: 2100,
        num_comments: 445,
        created_at: new Date(Date.now() - 10800000).toISOString(), // 3 hours ago
        ghost_url: 'https://american-trends.ghost.io/sample-mock-3',
        processed: true
      }
    ];
    
    return res.status(200).json({
      success: true,
      posts: mockPosts.slice(0, parseInt(limit)),
      data_source: 'mock_data'
    });
    
  } catch (error) {
    console.error('Recent posts API error:', error);
    return res.status(500).json({
      success: false,
      error: error.message
    });
  }
};