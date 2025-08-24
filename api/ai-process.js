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
    const { title, content, subreddit } = req.body || {};
    
    if (!title || !content) {
      return res.status(400).json({
        success: false,
        error: 'Title and content are required'
      });
    }
    
    const openaiApiKey = process.env.OPENAI_API_KEY;
    
    if (!openaiApiKey) {
      return res.status(200).json({
        success: true,
        data: {
          processed: true,
          message: 'OpenAI API key not configured - using mock enhancement',
          enhanced_title: `Enhanced: ${title}`,
          enhanced_content: content + '\n\n[Enhanced with AI processing]',
          tags: ['reddit', 'ai-enhanced', subreddit || 'general'],
          mock_mode: true,
          note: 'Configure OPENAI_API_KEY in Vercel environment variables'
        }
      });
    }
    
    // 실제 OpenAI API 호출 구현
    try {
      const { OpenAI } = require('openai');
      
      const openai = new OpenAI({
        apiKey: openaiApiKey
      });
      
      // 한국어 요약 생성
      const summaryPrompt = `다음 Reddit 게시글을 한국어로 요약해주세요:

제목: ${title}

내용:
${content}

요약 요구사항:
1. 핵심 내용을 3-5문장으로 간결하게 요약
2. 자연스러운 한국어로 작성
3. 원문의 맥락과 톤을 유지
4. 기술적 용어는 한국어로 번역하되 필요시 영어 병기
5. 객관적이고 중립적인 톤 유지

요약:`;

      const summaryResponse = await openai.chat.completions.create({
        model: 'gpt-4o-mini',
        messages: [
          {
            role: 'system',
            content: '당신은 Reddit 게시글을 한국어로 요약하는 전문가입니다. 정확하고 간결하며 이해하기 쉬운 요약을 제공합니다.'
          },
          {
            role: 'user',
            content: summaryPrompt
          }
        ],
        max_tokens: 500,
        temperature: 0.3
      });
      
      const koreanSummary = summaryResponse.choices[0].message.content.trim();
      
      // 태그 추출
      const tagPrompt = `다음 Reddit 게시글에서 3-5개의 태그를 추출해주세요:

제목: ${title}

내용:
${content}

태그 추출 요구사항:
1. 3개에서 5개의 태그 추출
2. 모든 태그는 소문자로 작성
3. 한글 태그 우선, 필요시 영어 사용
4. 검색 최적화를 위한 키워드 선택
5. 일관된 표기 규칙 적용 (띄어쓰기 없이, 하이픈 사용 가능)
6. 쉼표로 구분하여 나열

예시: 개발, 프로그래밍, 웹개발, 기술, 튜토리얼

태그:`;

      const tagResponse = await openai.chat.completions.create({
        model: 'gpt-4o-mini',
        messages: [
          {
            role: 'system',
            content: '당신은 Reddit 게시글에서 검색 최적화된 태그를 추출하는 전문가입니다. 일관된 표기 규칙을 따라 3-5개의 태그를 제공합니다.'
          },
          {
            role: 'user',
            content: tagPrompt
          }
        ],
        max_tokens: 200,
        temperature: 0.2
      });
      
      const tagsText = tagResponse.choices[0].message.content.trim();
      const tags = tagsText.split(',').map(tag => tag.trim().toLowerCase()).slice(0, 5);
      
      // 토큰 사용량 계산
      const totalTokens = summaryResponse.usage.total_tokens + tagResponse.usage.total_tokens;
      const estimatedCost = (totalTokens / 1000) * 0.00015; // GPT-4o-mini 비용
      
      return res.status(200).json({
        success: true,
        data: {
          processed: true,
          korean_summary: koreanSummary,
          tags: tags,
          token_usage: {
            summary_tokens: summaryResponse.usage.total_tokens,
            tag_tokens: tagResponse.usage.total_tokens,
            total_tokens: totalTokens,
            estimated_cost_usd: estimatedCost
          },
          timestamp: new Date().toISOString(),
          next_steps: 'Ready for Ghost publishing'
        }
      });
      
    } catch (apiError) {
      console.error('OpenAI API error:', apiError);
      
      // Fallback to enhanced mock data if API fails
      return res.status(200).json({
        success: true,
        data: {
          processed: true,
          message: 'OpenAI API error - falling back to enhanced mock mode',
          korean_summary: `${title}에 대한 요약: ${content.substring(0, 200)}...`,
          tags: ['reddit', subreddit || 'general', '기술', '개발'],
          error: apiError.message,
          timestamp: new Date().toISOString(),
          note: 'Check OpenAI API key and rate limits'
        }
      });
    }
    
  } catch (error) {
    console.error('AI processing error:', error);
    return res.status(500).json({
      success: false,
      error: error.message,
      fallback_action: 'Check OpenAI API credentials and try again'
    });
  }
};