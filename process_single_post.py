#!/usr/bin/env python3
"""
단일 포스트 처리 스크립트
특정 Reddit 포스트를 AI로 처리하고 Ghost에 발행합니다.
"""
import os
import openai
import psycopg2
import requests
import json
import jwt
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv(override=True)

# 설정
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'reddit_publisher',
    'user': 'reddit_publisher',
    'password': 'reddit_publisher_prod_2024'
}

def get_unprocessed_post():
    """처리되지 않은 포스트 하나를 가져옵니다"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        query = """
        SELECT id, reddit_post_id, title, subreddit, score, num_comments, content, selftext, url
        FROM posts 
        WHERE summary_ko IS NULL 
        AND score >= 100 
        ORDER BY score DESC 
        LIMIT 1
        """
        
        cursor.execute(query)
        row = cursor.fetchone()
        
        if row:
            post = {
                'id': row[0],
                'reddit_post_id': row[1],
                'title': row[2],
                'subreddit': row[3],
                'score': row[4],
                'num_comments': row[5],
                'content': row[6],
                'selftext': row[7],
                'url': row[8]
            }
            conn.close()
            return post
        
        conn.close()
        return None
        
    except Exception as e:
        print(f"❌ 데이터베이스 조회 오류: {e}")
        return None

def process_with_ai(post):
    """포스트를 AI로 처리합니다"""
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        client = openai.OpenAI(api_key=api_key)
        
        # 콘텐츠 준비
        content = f"Title: {post['title']}\n"
        if post['selftext']:
            content += f"Content: {post['selftext']}\n"
        content += f"URL: {post['url']}\n"
        content += f"Subreddit: r/{post['subreddit']}\n"
        content += f"Score: {post['score']}, Comments: {post['num_comments']}"
        
        print(f"📝 AI 처리 중: {post['title'][:50]}...")
        
        # 1. 한국어 요약 생성
        summary_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 Reddit 포스트를 한국어로 요약하는 전문가입니다. 핵심 내용을 2-3문장으로 간결하고 이해하기 쉽게 요약해주세요."},
                {"role": "user", "content": f"다음 Reddit 포스트를 한국어로 요약해주세요:\n\n{content}"}
            ],
            max_tokens=300
        )
        
        summary_ko = summary_response.choices[0].message.content.strip()
        print(f"✅ 요약 생성 완료: {summary_ko[:50]}...")
        
        # 2. 태그 생성
        tags_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "다음 내용에 적합한 3-5개의 태그를 한국어로 생성해주세요. 각 태그는 쉼표로 구분하여 제공해주세요."},
                {"role": "user", "content": content}
            ],
            max_tokens=100
        )
        
        tags_text = tags_response.choices[0].message.content.strip()
        tags = [tag.strip() for tag in tags_text.split(',')]
        print(f"✅ 태그 생성 완료: {tags}")
        
        # 3. 데이터베이스 업데이트
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        update_query = """
        UPDATE posts 
        SET summary_ko = %s, tags = %s, updated_at = NOW()
        WHERE id = %s
        """
        
        cursor.execute(update_query, (summary_ko, json.dumps(tags), post['id']))
        conn.commit()
        conn.close()
        
        print("✅ 데이터베이스 업데이트 완료")
        
        return {
            'summary_ko': summary_ko,
            'tags': tags
        }
        
    except Exception as e:
        print(f"❌ AI 처리 오류: {e}")
        return None

def publish_to_ghost(post, ai_result):
    """Ghost CMS에 포스트를 발행합니다"""
    try:
        # Ghost 설정
        ghost_api_url = os.getenv('GHOST_API_URL')
        ghost_admin_key = os.getenv('GHOST_ADMIN_KEY')
        
        if ':' not in ghost_admin_key:
            print("❌ Ghost Admin Key 형식 오류")
            return False
        
        key_id, secret = ghost_admin_key.split(':', 1)
        
        # JWT 토큰 생성
        iat = int(time.time())
        exp = iat + 300  # 5분
        
        payload = {
            'iat': iat,
            'exp': exp,
            'aud': '/admin/'
        }
        
        token = jwt.encode(payload, bytes.fromhex(secret), algorithm='HS256', headers={'kid': key_id})
        
        # Ghost API 헤더
        headers = {
            'Authorization': f'Ghost {token}',
            'Content-Type': 'application/json'
        }
        
        # 포스트 내용 생성
        html_content = f"""
        <h2>📊 Reddit 인사이트</h2>
        <p><strong>출처:</strong> <a href="{post['url']}" target="_blank">r/{post['subreddit']}</a></p>
        <p><strong>점수:</strong> {post['score']}점 | <strong>댓글:</strong> {post['num_comments']}개</p>
        
        <h3>🔍 요약</h3>
        <p>{ai_result['summary_ko']}</p>
        
        <h3>📝 원문</h3>
        <h4>{post['title']}</h4>
        """
        
        if post['selftext']:
            html_content += f"<p>{post['selftext'][:500]}...</p>"
        
        html_content += f"""
        <p><a href="{post['url']}" target="_blank">전체 내용 보기 →</a></p>
        
        <hr>
        <p><small>이 글은 Reddit에서 자동 수집되어 AI로 요약된 내용입니다.</small></p>
        """
        
        # Ghost 포스트 데이터
        post_data = {
            "posts": [{
                "title": f"[Reddit] {post['title'][:80]}",
                "html": html_content,
                "tags": ai_result['tags'][:5],  # 최대 5개 태그
                "status": "published",
                "meta_description": ai_result['summary_ko'][:160],
                "custom_excerpt": ai_result['summary_ko'][:300]
            }]
        }
        
        print(f"👻 Ghost 발행 중...")
        
        # Ghost API 호출
        response = requests.post(
            f"{ghost_api_url}/ghost/api/admin/posts/",
            headers=headers,
            json=post_data,
            timeout=30
        )
        
        if response.status_code == 201:
            result = response.json()
            ghost_post = result['posts'][0]
            ghost_url = ghost_post['url']
            ghost_id = ghost_post['id']
            
            print(f"✅ Ghost 발행 성공!")
            print(f"   URL: {ghost_url}")
            
            # 데이터베이스 업데이트
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            
            update_query = """
            UPDATE posts 
            SET ghost_url = %s, ghost_post_id = %s, published_at = NOW(), updated_at = NOW()
            WHERE id = %s
            """
            
            cursor.execute(update_query, (ghost_url, ghost_id, post['id']))
            conn.commit()
            conn.close()
            
            return ghost_url
            
        else:
            print(f"❌ Ghost 발행 실패: {response.status_code}")
            print(f"   응답: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Ghost 발행 오류: {e}")
        return False

def main():
    """메인 실행 함수"""
    print("🚀 단일 포스트 AI 처리 및 Ghost 발행")
    print("=" * 50)
    
    # 1. 처리할 포스트 가져오기
    post = get_unprocessed_post()
    
    if not post:
        print("❌ 처리할 포스트가 없습니다.")
        return
    
    print(f"📋 선택된 포스트:")
    print(f"   제목: {post['title']}")
    print(f"   서브레딧: r/{post['subreddit']}")
    print(f"   점수: {post['score']}점, 댓글: {post['num_comments']}개")
    
    # 2. AI 처리
    ai_result = process_with_ai(post)
    
    if not ai_result:
        print("❌ AI 처리 실패")
        return
    
    # 3. Ghost 발행
    ghost_url = publish_to_ghost(post, ai_result)
    
    if ghost_url:
        print(f"\n🎉 성공적으로 완료!")
        print(f"📝 요약: {ai_result['summary_ko']}")
        print(f"🏷️ 태그: {', '.join(ai_result['tags'])}")
        print(f"🔗 발행 URL: {ghost_url}")
    else:
        print("❌ Ghost 발행 실패")

if __name__ == "__main__":
    main()