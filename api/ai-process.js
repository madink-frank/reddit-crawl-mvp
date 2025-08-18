// Vercel Serverless Function - AI Content Processing
export default async function handler(req, res) {
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
    const { posts, processing_type = 'enhance' } = req.body || {};
    
    if (!posts || !Array.isArray(posts) || posts.length === 0) {
      return res.status(400).json({
        success: false,
        error: 'No posts provided for processing'
      });
    }
    
    // OpenAI API 설정
    const openaiApiKey = process.env.OPENAI_API_KEY;
    
    if (!openaiApiKey) {
      return res.status(200).json({
        success: true,
        data: {
          processed_posts: posts.length,
          posts: posts.map(post => ({
            ...post,
            ai_processed: false,
            enhanced_title: post.title + ' [Mock Enhancement]',
            summary: `Mock AI summary for: ${post.title}`,
            tags: ['mock', 'ai-processing', post.subreddit],
            processing_note: 'OpenAI API key not configured - using mock processing'
          })),
          note: 'Configure OPENAI_API_KEY in Vercel environment variables for real AI processing'
        }
      });
    }
    
    const processedPosts = [];
    
    // 각 포스트를 AI로 처리 (비용 고려하여 최대 3개만)
    for (const post of posts.slice(0, 3)) {
      try {
        const prompt = `
Task: Enhance this Reddit post for a tech blog publication.

Original Post:
Title: ${post.title}
Subreddit: r/${post.subreddit}
Content: ${post.selftext || 'Link post - no text content'}
Score: ${post.score} | Comments: ${post.comments}

Instructions:
1. Create an engaging, SEO-friendly title (max 60 chars)
2. Write a brief summary (2-3 sentences)
3. Generate 3-5 relevant tags
4. Assess content quality (1-10)
5. Suggest blog category

Respond in JSON format:
{
  "enhanced_title": "...",
  "summary": "...",
  "tags": ["tag1", "tag2", "tag3"],
  "quality_score": 8,
  "category": "Technology",
  "publish_ready": true/false
}`;

        const aiResponse = await fetch('https://api.openai.com/v1/chat/completions', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${openaiApiKey}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            model: 'gpt-4o-mini',
            messages: [{
              role: 'user',
              content: prompt
            }],
            max_tokens: 500,
            temperature: 0.7
          })
        });
        
        if (!aiResponse.ok) {
          throw new Error(`OpenAI API error: ${aiResponse.status}`);
        }
        
        const aiData = await aiResponse.json();
        const aiContent = aiData.choices[0].message.content;
        
        // JSON 파싱 시도
        let aiResult;
        try {
          aiResult = JSON.parse(aiContent);
        } catch {
          // JSON 파싱 실패 시 기본값 사용
          aiResult = {
            enhanced_title: post.title,
            summary: `AI-enhanced summary for ${post.title}`,
            tags: [post.subreddit, 'tech', 'reddit'],
            quality_score: 7,
            category: 'Technology',
            publish_ready: true
          };
        }
        
        processedPosts.push({
          ...post,
          ai_processed: true,
          enhanced_title: aiResult.enhanced_title,
          summary: aiResult.summary,
          tags: aiResult.tags,
          quality_score: aiResult.quality_score,
          category: aiResult.category,
          publish_ready: aiResult.publish_ready,
          tokens_used: aiData.usage?.total_tokens || 0,
          processing_time: Date.now()
        });
        
      } catch (error) {
        console.error(`AI processing error for post ${post.id}:`, error);
        
        // 에러 시 기본 처리 결과 반환
        processedPosts.push({
          ...post,
          ai_processed: false,
          enhanced_title: post.title,
          summary: `Failed to process: ${error.message}`,
          tags: [post.subreddit],
          quality_score: 5,
          category: 'Technology',
          publish_ready: false,
          error: error.message
        });
      }
    }
    
    const totalTokens = processedPosts.reduce((sum, post) => sum + (post.tokens_used || 0), 0);
    const successfulProcessing = processedPosts.filter(post => post.ai_processed).length;
    
    res.status(200).json({
      success: true,
      data: {
        processed_posts: processedPosts.length,
        successful_ai_processing: successfulProcessing,
        posts: processedPosts,
        total_tokens_used: totalTokens,
        estimated_cost_usd: totalTokens * 0.00015 / 1000, // GPT-4o-mini cost
        timestamp: new Date().toISOString(),
        next_steps: successfulProcessing > 0 ? 'Ready for Ghost publishing' : 'Review processing errors'
      }
    });
    
  } catch (error) {
    console.error('AI processing error:', error);
    res.status(500).json({
      success: false,
      error: error.message,
      fallback_action: 'Check OpenAI API key and try again'
    });
  }
}