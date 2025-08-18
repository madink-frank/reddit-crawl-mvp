import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from 'jsr:@supabase/supabase-js@2';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
};

interface DatabaseConfig {
  supabaseUrl: string;
  supabaseKey: string;
}

// Supabase 클라이언트 초기화
function createSupabaseClient(): any {
  const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
  const supabaseKey = Deno.env.get('SUPABASE_ANON_KEY')!;
  
  return createClient(supabaseUrl, supabaseKey);
}

// 헬스체크 엔드포인트
async function handleHealth(): Promise<Response> {
  try {
    const supabase = createSupabaseClient();
    
    // 데이터베이스 연결 테스트
    const { data, error } = await supabase
      .from('posts')
      .select('count')
      .limit(1);
    
    const dbHealthy = !error;
    
    const healthData = {
      success: true,
      data: {
        api_server: {
          healthy: true,
          status: 'healthy'
        },
        database: {
          healthy: dbHealthy
        },
        overall_status: dbHealthy ? 'healthy' : 'degraded',
        services: {
          database: { status: dbHealthy ? 'healthy' : 'degraded' },
          supabase: { status: 'healthy' },
          edge_functions: { status: 'healthy' }
        }
      },
      timestamp: new Date().toISOString()
    };
    
    return new Response(JSON.stringify(healthData), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      status: 200,
    });
  } catch (error) {
    return new Response(JSON.stringify({
      success: false,
      error: error.message
    }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      status: 500,
    });
  }
}

// 통계 데이터 조회
async function handleStats(): Promise<Response> {
  try {
    const supabase = createSupabaseClient();
    
    // 전체 통계 조회
    const { data: totalPosts, error: totalError } = await supabase
      .from('posts')
      .select('*', { count: 'exact', head: true });
    
    const { data: aiProcessed, error: aiError } = await supabase
      .from('posts')
      .select('*', { count: 'exact', head: true })
      .not('summary_ko', 'is', null);
    
    const { data: published, error: publishedError } = await supabase
      .from('posts')
      .select('*', { count: 'exact', head: true })
      .not('ghost_url', 'is', null);
    
    const { data: todayPosts, error: todayError } = await supabase
      .from('posts')
      .select('*', { count: 'exact', head: true })
      .gte('created_at', new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString());
    
    // 최근 포스트 조회
    const { data: recentPosts, error: recentError } = await supabase
      .from('posts')
      .select('reddit_post_id, title, subreddit, score, num_comments, summary_ko, ghost_url, created_at')
      .order('created_at', { ascending: false })
      .limit(5);
    
    if (totalError || aiError || publishedError || todayError) {
      throw new Error('Database query failed');
    }
    
    const total = totalPosts?.count || 0;
    const processed = aiProcessed?.count || 0;
    const publishedCount = published?.count || 0;
    const today = todayPosts?.count || 0;
    
    const successRate = total > 0 ? Math.round((publishedCount / total) * 100 * 10) / 10 : 0;
    
    const statsData = {
      success: true,
      data: {
        total_posts: total,
        ai_processed: processed,
        published: publishedCount,
        collected_today: today,
        success_rate: successRate,
        recent_posts: (recentPosts || []).map(post => ({
          id: post.reddit_post_id,
          title: post.title?.length > 60 ? post.title.substring(0, 60) + '...' : post.title,
          subreddit: post.subreddit,
          score: post.score,
          comments: post.num_comments,
          processed: !!post.summary_ko,
          published: !!post.ghost_url,
          ghost_url: post.ghost_url,
          created_at: post.created_at
        }))
      },
      timestamp: new Date().toISOString()
    };
    
    return new Response(JSON.stringify(statsData), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      status: 200,
    });
  } catch (error) {
    return new Response(JSON.stringify({
      success: false,
      error: error.message
    }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      status: 500,
    });
  }
}

// Reddit 수집 트리거
async function handleTriggerCollect(request: Request): Promise<Response> {
  try {
    const body = await request.json();
    const { batch_size = 10, subreddits = ['programming', 'technology', 'webdev'] } = body;
    
    // 실제 구현에서는 여기서 Reddit API를 호출하고 데이터를 수집
    // 현재는 모의 응답 반환
    const taskId = `collect-${Date.now()}`;
    
    // 작업 큐에 추가 (실제 구현)
    const supabase = createSupabaseClient();
    const { error } = await supabase
      .from('job_queue')
      .insert({
        job_type: 'collect',
        job_data: { batch_size, subreddits },
        status: 'pending'
      });
    
    if (error) {
      throw new Error('Failed to queue collection job');
    }
    
    return new Response(JSON.stringify({
      success: true,
      data: {
        task_id: taskId,
        message: 'Collection job queued successfully',
        batch_size,
        subreddits
      }
    }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      status: 200,
    });
  } catch (error) {
    return new Response(JSON.stringify({
      success: false,
      error: error.message
    }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      status: 500,
    });
  }
}

// 파이프라인 트리거
async function handleTriggerPipeline(request: Request): Promise<Response> {
  try {
    const body = await request.json();
    const { batch_size = 3 } = body;
    
    const taskId = `pipeline-${Date.now()}`;
    
    // 파이프라인 작업 큐에 추가
    const supabase = createSupabaseClient();
    const { error } = await supabase
      .from('job_queue')
      .insert({
        job_type: 'pipeline',
        job_data: { batch_size },
        status: 'pending'
      });
    
    if (error) {
      throw new Error('Failed to queue pipeline job');
    }
    
    return new Response(JSON.stringify({
      success: true,
      data: {
        task_id: taskId,
        message: 'Full pipeline job queued successfully',
        batch_size
      }
    }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      status: 200,
    });
  } catch (error) {
    return new Response(JSON.stringify({
      success: false,
      error: error.message
    }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      status: 500,
    });
  }
}

// 메인 핸들러
Deno.serve(async (req) => {
  // CORS preflight 처리
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders });
  }
  
  const url = new URL(req.url);
  const path = url.pathname;
  
  try {
    // 라우팅
    if (path === '/api/health' && req.method === 'GET') {
      return await handleHealth();
    }
    
    if (path === '/api/stats' && req.method === 'GET') {
      return await handleStats();
    }
    
    if (path === '/api/trigger/collect' && req.method === 'POST') {
      return await handleTriggerCollect(req);
    }
    
    if (path === '/api/trigger/pipeline' && req.method === 'POST') {
      return await handleTriggerPipeline(req);
    }
    
    // 404 처리
    return new Response(JSON.stringify({
      success: false,
      error: 'Endpoint not found'
    }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      status: 404,
    });
    
  } catch (error) {
    return new Response(JSON.stringify({
      success: false,
      error: error.message
    }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      status: 500,
    });
  }
});