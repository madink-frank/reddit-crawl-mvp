// 로컬 Reddit RSS 테스트
const https = require('https');

async function testRedditRSS() {
  console.log('🔍 로컬 Reddit RSS 테스트 시작...');
  
  try {
    // Reddit RSS URL
    const rssUrl = 'https://www.reddit.com/r/programming/hot/.rss?limit=5';
    console.log('RSS URL:', rssUrl);
    
    // 브라우저 User-Agent 사용
    const response = await fetch(rssUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/rss+xml, application/xml, text/xml',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache'
      }
    });
    
    console.log('Response status:', response.status);
    console.log('Response headers:', Object.fromEntries(response.headers.entries()));
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const rssText = await response.text();
    console.log('RSS text length:', rssText.length);
    console.log('RSS preview:', rssText.substring(0, 300) + '...');
    
    // Atom 피드 파싱 (Reddit은 Atom 형식 사용)
    console.log('\\n=== Atom 피드 분석 ===');
    
    // entry 태그 찾기 (Atom의 개별 항목)
    const entryMatches = rssText.match(/<entry>(.*?)<\/entry>/gs);
    console.log('Entry matches found:', entryMatches ? entryMatches.length : 0);
    
    if (entryMatches && entryMatches.length > 0) {
      console.log('\\n=== 추출된 게시글들 ===');
      entryMatches.forEach((entry, index) => {
        // 제목 추출 (Atom 형식)
        const titleMatch = entry.match(/<title[^>]*>(.*?)<\/title>/s);
        const linkMatch = entry.match(/<link[^>]*href="([^"]*)"[^>]*>/);
        const idMatch = entry.match(/<id[^>]*>(.*?)<\/id>/);
        
        if (titleMatch && titleMatch[1]) {
          const title = titleMatch[1].trim();
          const link = linkMatch ? linkMatch[1] : 'No link';
          const id = idMatch ? idMatch[1] : 'No ID';
          
          console.log(`${index + 1}. 제목: ${title}`);
          console.log(`   링크: ${link}`);
          console.log(`   ID: ${id}`);
          console.log('');
        }
      });
    }
    
    // 전체 구조 확인
    console.log('\\n=== XML 구조 샘플 ===');
    const lines = rssText.split('\\n');
    lines.slice(0, 20).forEach((line, index) => {
      console.log(`${index + 1}: ${line.trim()}`);
    });
    
    console.log('\\n✅ 로컬 RSS 테스트 성공!');
    return true;
    
  } catch (error) {
    console.error('❌ 로컬 RSS 테스트 실패:', error.message);
    console.error('Stack:', error.stack);
    return false;
  }
}

// 테스트 실행
testRedditRSS().then(success => {
  console.log('\\n테스트 결과:', success ? '성공' : '실패');
  process.exit(success ? 0 : 1);
});