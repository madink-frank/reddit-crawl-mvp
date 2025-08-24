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
  
  if (req.method !== 'GET') {
    return res.status(405).json({ success: false, error: 'Method not allowed' });
  }
  
  try {
    // 먼저 Supabase 연결 시도
    const supabaseUrl = process.env.SUPABASE_URL;
    const supabaseKey = process.env.SUPABASE_ANON_KEY;
    
    if (supabaseUrl && supabaseKey) {
      try {
        // Supabase에서 통계 가져오기
        const response = await fetch(`${supabaseUrl}/rest/v1/posts?select=*&order=created_at.desc&limit=100`, {
          headers: {
            'apikey': supabaseKey,
            'Authorization': `Bearer ${supabaseKey}`,
            'Content-Type': 'application/json'
          }
        });
        
        if (response.ok) {
          const posts = await response.json();
          
          const totalPosts = posts.length;
          const aiProcessed = posts.filter(post => post.summary_ko).length;
          const published = posts.filter(post => post.ghost_url).length;
          
          const today = new Date().toISOString().split('T')[0];
          const collectedToday = posts.filter(post => 
            post.created_at && post.created_at.startsWith(today)
          ).length;
          
          const successRate = totalPosts > 0 ? Math.round((published / totalPosts) * 100) : 0;
          
          const recentPosts = posts.slice(0, 5).map(post => ({
            id: post.reddit_post_id || post.id,
            title: post.title,
            subreddit: post.subreddit,
            score: post.score || 0,
            comments: post.num_comments || 0,
            processed: !!post.summary_ko,
            published: !!post.ghost_url,
            ghost_url: post.ghost_url,
            created_at: post.created_at
          }));
          
          return res.status(200).json({
            success: true,
            total_posts: totalPosts,
            processed_posts: aiProcessed,
            published_posts: published,
            collected_today: collectedToday,
            success_rate: successRate,
            recent_posts: recentPosts,
            data_source: 'supabase',
            timestamp: new Date().toISOString()
          });
        }
      } catch (supabaseError) {
        console.log('Supabase connection failed:', supabaseError.message);
      }
    }
    
    // PostgreSQL 연결 시도
    const databaseUrl = process.env.DATABASE_URL;
    
    if (databaseUrl) {
      try {
        const { Pool } = require('pg');
        
        const pool = new Pool({
          connectionString: databaseUrl,
          ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false
        });
        
        // Get real statistics from database
        const statsQuery = `
          SELECT 
            COUNT(*) as total_posts,
            COUNT(CASE WHEN summary_ko IS NOT NULL THEN 1 END) as ai_processed,
            COUNT(CASE WHEN ghost_url IS NOT NULL THEN 1 END) as published,
            COUNT(CASE WHEN DATE(created_at) = CURRENT_DATE THEN 1 END) as collected_today
          FROM posts
        `;
        
        const recentPostsQuery = `
          SELECT 
            id,
            reddit_post_id,
            title,
            subreddit,
            score,
            num_comments,
            summary_ko IS NOT NULL as processed,
            ghost_url IS NOT NULL as published,
            ghost_url,
            created_at
          FROM posts 
          ORDER BY created_at DESC 
          LIMIT 5
        `;
        
        const [statsResult, postsResult] = await Promise.all([
          pool.query(statsQuery),
          pool.query(recentPostsQuery)
        ]);
        
        const stats = statsResult.rows[0];
        const totalPosts = parseInt(stats.total_posts);
        const aiProcessed = parseInt(stats.ai_processed);
        const published = parseInt(stats.published);
        const collectedToday = parseInt(stats.collected_today);
        const successRate = totalPosts > 0 ? Math.round((published / totalPosts) * 100) : 0;
        
        const recentPosts = postsResult.rows.map(post => ({
          id: post.reddit_post_id,
          title: post.title,
          subreddit: post.subreddit,
          score: post.score,
          comments: post.num_comments,
          processed: post.processed,
          published: post.published,
          ghost_url: post.ghost_url,
          created_at: post.created_at
        }));
        
        await pool.end();
        
        return res.status(200).json({
          success: true,
          total_posts: totalPosts,
          processed_posts: aiProcessed,
          published_posts: published,
          collected_today: collectedToday,
          success_rate: successRate,
          recent_posts: recentPosts,
          data_source: 'postgresql',
          timestamp: new Date().toISOString()
        });
        
      } catch (dbError) {
        console.error('PostgreSQL connection error:', dbError);
      }
    }
    
    // 데이터베이스 연결 실패 시 빈 데이터 반환
    return res.status(200).json({
      success: true,
      total_posts: 0,
      processed_posts: 0,
      published_posts: 0,
      collected_today: 0,
      success_rate: 0,
      recent_posts: [],
      data_source: 'no_database_connection',
      message: 'No database connection available. Configure SUPABASE_URL/DATABASE_URL.',
      timestamp: new Date().toISOString()
    });
    
    // Real PostgreSQL database integration
    try {
      const { Pool } = require('pg');
      
      const pool = new Pool({
        connectionString: databaseUrl,
        ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false
      });
      
      // Get real statistics from database
      const statsQuery = `
        SELECT 
          COUNT(*) as total_posts,
          COUNT(CASE WHEN summary_ko IS NOT NULL THEN 1 END) as ai_processed,
          COUNT(CASE WHEN ghost_url IS NOT NULL THEN 1 END) as published,
          COUNT(CASE WHEN DATE(created_at) = CURRENT_DATE THEN 1 END) as collected_today
        FROM posts
      `;
      
      const recentPostsQuery = `
        SELECT 
          id,
          reddit_post_id,
          title,
          subreddit,
          score,
          num_comments,
          summary_ko IS NOT NULL as processed,
          ghost_url IS NOT NULL as published,
          ghost_url,
          created_at
        FROM posts 
        ORDER BY created_at DESC 
        LIMIT 5
      `;
      
      const [statsResult, postsResult] = await Promise.all([
        pool.query(statsQuery),
        pool.query(recentPostsQuery)
      ]);
      
      const stats = statsResult.rows[0];
      const totalPosts = parseInt(stats.total_posts);
      const aiProcessed = parseInt(stats.ai_processed);
      const published = parseInt(stats.published);
      const collectedToday = parseInt(stats.collected_today);
      const successRate = totalPosts > 0 ? Math.round((published / totalPosts) * 100) : 0;
      
      const recentPosts = postsResult.rows.map(post => ({
        id: post.reddit_post_id,
        title: post.title,
        subreddit: post.subreddit,
        score: post.score,
        comments: post.num_comments,
        processed: post.processed,
        published: post.published,
        ghost_url: post.ghost_url,
        created_at: post.created_at
      }));
      
      await pool.end();
      
      const statsData = {
        success: true,
        data: {
          total_posts: totalPosts,
          ai_processed: aiProcessed,
          published: published,
          collected_today: collectedToday,
          success_rate: successRate,
          recent_posts: recentPosts,
          data_source: 'postgresql'
        },
        timestamp: new Date().toISOString()
      };
      
      return res.status(200).json(statsData);
      
    } catch (dbError) {
      console.error('Database connection error:', dbError);
      
      // 데이터베이스 연결 실패 시 에러 반환
      return res.status(500).json({
        success: false,
        error: 'Database connection failed',
        db_error: dbError.message,
        message: 'Configure DATABASE_URL or SUPABASE_URL environment variables',
        timestamp: new Date().toISOString()
      });
    }
  } catch (error) {
    console.error('Stats error:', error);
    return res.status(500).json({
      success: false,
      error: error.message
    });
  }
};