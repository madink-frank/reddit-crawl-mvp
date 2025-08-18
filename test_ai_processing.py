#!/usr/bin/env python3
"""
AI 처리 테스트 스크립트
OpenAI API 연결을 테스트하고 간단한 요약을 생성합니다.
"""
import os
import openai
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv(override=True)

def test_openai_direct():
    """OpenAI API 직접 테스트"""
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        print(f"사용 중인 API 키: {api_key[:20]}...")
        
        # OpenAI 클라이언트 설정
        client = openai.OpenAI(api_key=api_key)
        
        # 간단한 테스트 요청
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": "Hello! Please respond with 'OpenAI API is working correctly.'"}
            ],
            max_tokens=20
        )
        
        result = response.choices[0].message.content
        print(f"✅ OpenAI API 응답: {result}")
        return True
        
    except Exception as e:
        print(f"❌ OpenAI API 오류: {e}")
        return False

def test_reddit_content_processing():
    """Reddit 콘텐츠 AI 처리 테스트"""
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        client = openai.OpenAI(api_key=api_key)
        
        # 샘플 Reddit 포스트 내용
        sample_content = """
        Title: New trend: extreme hours at AI startups
        
        Content: I've been noticing a concerning trend in AI startups where employees are expected to work 80-100 hour weeks. Companies are justifying this by saying they're in a "race against time" to build AGI. 
        
        Is this sustainable? What are your thoughts on work-life balance in the AI industry?
        """
        
        # AI 요약 생성
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 Reddit 포스트를 한국어로 요약하는 전문가입니다. 핵심 내용을 2-3문장으로 간결하게 요약해주세요."},
                {"role": "user", "content": f"다음 Reddit 포스트를 한국어로 요약해주세요:\n\n{sample_content}"}
            ],
            max_tokens=200
        )
        
        summary = response.choices[0].message.content
        print(f"✅ AI 요약 생성 성공:")
        print(f"   {summary}")
        
        # 태그 생성
        tag_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "다음 내용에 적합한 3-5개의 태그를 한국어로 생성해주세요. 태그는 쉼표로 구분하여 제공해주세요."},
                {"role": "user", "content": sample_content}
            ],
            max_tokens=50
        )
        
        tags = tag_response.choices[0].message.content
        print(f"✅ 태그 생성 성공: {tags}")
        
        return True
        
    except Exception as e:
        print(f"❌ 콘텐츠 처리 오류: {e}")
        return False

if __name__ == "__main__":
    print("🤖 AI 처리 테스트 시작")
    print("=" * 40)
    
    if test_openai_direct():
        print("\n📝 Reddit 콘텐츠 처리 테스트...")
        test_reddit_content_processing()
    else:
        print("❌ OpenAI API 연결 실패")