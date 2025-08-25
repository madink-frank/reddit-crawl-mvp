// 간단한 Reddit API 테스트
module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }
  
  try {
    console.log('🔍 Starting Reddit API test...');
    
    // Node.js 내장 https 모듈 사용
    const https = require('https');
    
    const testUrl = 'https://www.reddit.com/r/programming/hot.json?limit=3';
    console.log('Test URL:', testUrl);
    
    const result = await new Promise((resolve, reject) => {
      const options = {
        headers: {
          'User-Agent': 'reddit-ghost-publisher/1.0.0 (by /u/reddit-publisher)'
        }
      };
      
      console.log('Making HTTPS request...');
      
      https.get(testUrl, options, (response) => {
        console.log('Response status:', response.statusCode);
        console.log('Response headers:', response.headers);
        
        let data = '';
        
        response.on('data', (chunk) => {
          data += chunk;
          console.log('Received chunk, total length:', data.length);
        });
        
        response.on('end', () => {
          console.log('Response complete, total length:', data.length);
          try {
            const jsonData = JSON.parse(data);
            console.log('JSON parsed successfully');
            console.log('Children count:', jsonData?.data?.children?.length || 0);
            
            if (jsonData?.data?.children?.length > 0) {
              const firstPost = jsonData.data.children[0].data;
              console.log('First post title:', firstPost.title);
              console.log('First post score:', firstPost.score);
            }
            
            resolve({
              success: true,
              statusCode: response.statusCode,
              dataLength: data.length,
              postsFound: jsonData?.data?.children?.length || 0,
              firstPostTitle: jsonData?.data?.children?.[0]?.data?.title || 'N/A',
              rawDataSample: data.substring(0, 500) + '...'
            });
          } catch (parseError) {
            console.error('JSON parse error:', parseError.message);
            resolve({
              success: false,
              error: 'JSON parse error',
              parseError: parseError.message,
              rawDataSample: data.substring(0, 500) + '...'
            });
          }
        });
      }).on('error', (error) => {
        console.error('HTTPS request error:', error.message);
        reject({
          success: false,
          error: 'HTTPS request error',
          message: error.message
        });
      });
    });
    
    console.log('Test completed:', result);
    
    return res.status(200).json({
      success: true,
      message: 'Reddit API test completed',
      result: result,
      timestamp: new Date().toISOString()
    });
    
  } catch (error) {
    console.error('Test error:', error);
    return res.status(500).json({
      success: false,
      error: error.message,
      stack: error.stack
    });
  }
};