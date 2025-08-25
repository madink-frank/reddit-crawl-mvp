// 매우 간단한 Reddit API 테스트
module.exports = async (req, res) => {
  // CORS 설정
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }
  
  try {
    // 1. 기본 정보 수집
    const testInfo = {
      timestamp: new Date().toISOString(),
      method: req.method,
      nodeVersion: process.version,
      platform: process.platform
    };
    
    // 2. 간단한 Reddit API 호출 테스트
    const testUrl = 'https://www.reddit.com/r/programming/hot.json?limit=2';
    
    // Node.js 내장 fetch 사용 (Node 18+)
    let fetchResult;
    try {
      const response = await fetch(testUrl, {
        headers: {
          'User-Agent': 'simple-reddit-test/1.0.0'
        }
      });
      
      fetchResult = {
        status: response.status,
        ok: response.ok,
        headers: Object.fromEntries(response.headers.entries())
      };
      
      if (response.ok) {
        const data = await response.json();
        fetchResult.dataReceived = true;
        fetchResult.postsCount = data?.data?.children?.length || 0;
        fetchResult.firstPostTitle = data?.data?.children?.[0]?.data?.title || 'N/A';
      } else {
        fetchResult.dataReceived = false;
        fetchResult.errorText = await response.text();
      }
      
    } catch (fetchError) {
      fetchResult = {
        error: true,
        message: fetchError.message,
        stack: fetchError.stack
      };
    }
    
    return res.status(200).json({
      success: true,
      message: 'Simple Reddit test completed',
      testInfo,
      fetchResult,
      conclusion: fetchResult.postsCount > 0 ? 'SUCCESS: Reddit API working!' : 'FAILED: No posts received'
    });
    
  } catch (error) {
    return res.status(500).json({
      success: false,
      error: error.message,
      stack: error.stack
    });
  }
};