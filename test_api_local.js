// 로컬에서 API 테스트
// Node.js 18+ 내장 fetch 사용

// Reddit RSS API 테스트 함수
async function testRedditRSSAPI() {
  console.log('🧪 Reddit RSS API 로컬 테스트 시작...\n');
  
  try {
    // API 함수 직접 import
    const redditCollectAPI = require('./api/reddit-collect.js');
    
    // Mock request/response 객체 생성
    const mockReq = {
      method: 'POST',
      body: {
        subreddits: ['programming', 'webdev'],
        limit: 5
      }
    };
    
    const mockRes = {
      headers: {},
      statusCode: 200,
      setHeader: function(key, value) {
        this.headers[key] = value;
      },
      status: function(code) {
        this.statusCode = code;
        return this;
      },
      json: function(data) {
        console.log('📊 API Response Status:', this.statusCode);
        console.log('📊 API Response Data:');
        console.log(JSON.stringify(data, null, 2));
        return this;
      },
      end: function() {
        console.log('✅ Response ended');
        return this;
      }
    };
    
    // API 함수 실행
    console.log('🚀 Calling reddit-collect API...');
    await redditCollectAPI(mockReq, mockRes);
    
  } catch (error) {
    console.error('❌ 로컬 테스트 에러:', error.message);
    console.error('Stack:', error.stack);
  }
}

// RSS 직접 테스트 함수
async function testDirectRSS() {
  console.log('\n🔍 Direct RSS 테스트 시작...\n');
  
  try {
    const subreddit = 'programming';
    const rssUrl = `https://www.reddit.com/r/${subreddit}/hot/.rss?limit=5`;
    
    console.log('RSS URL:', rssUrl);
    
    const response = await fetch(rssUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/rss+xml, application/xml, text/xml, application/atom+xml',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache'
      }
    });
    
    console.log('📡 Response Status:', response.status);
    console.log('📡 Response Headers:', Object.fromEntries(response.headers));
    
    if (!response.ok) {
      console.error('❌ HTTP Error:', response.status, response.statusText);
      return;
    }
    
    const rssText = await response.text();
    console.log('📄 RSS Length:', rssText.length);
    console.log('📄 RSS Preview (first 500 chars):');
    console.log(rssText.substring(0, 500));
    
    // Atom 엔트리 찾기
    const entryMatches = rssText.match(/<entry>/g);
    console.log('\n📝 Found entries:', entryMatches ? entryMatches.length : 0);
    
    // 첫 번째 엔트리 파싱 테스트
    const firstEntry = rssText.match(/<entry>(.*?)<\/entry>/s);
    if (firstEntry) {
      console.log('\n🔍 First entry analysis:');
      const entryXml = firstEntry[1];
      
      const titleMatch = entryXml.match(/<title[^>]*>(.*?)<\/title>/s);
      const linkMatch = entryXml.match(/<link[^>]*href="([^"]*)"[^>]*>/);
      
      console.log('Title:', titleMatch ? titleMatch[1] : 'Not found');
      console.log('Link:', linkMatch ? linkMatch[1] : 'Not found');
    }
    
  } catch (error) {
    console.error('❌ Direct RSS 테스트 에러:', error.message);
  }
}

// 테스트 실행
async function runAllTests() {
  console.log('🎯 Reddit API 로컬 테스트 시작\n');
  console.log('=' .repeat(50));
  
  // 1. Direct RSS 테스트
  await testDirectRSS();
  
  console.log('\n' + '='.repeat(50));
  
  // 2. API 함수 테스트
  await testRedditRSSAPI();
  
  console.log('\n🏁 모든 테스트 완료!');
}

runAllTests();