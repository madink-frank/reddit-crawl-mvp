#!/usr/bin/env python3
"""
간단한 Ghost 페이지 업로드 스크립트
Ghost Admin Key가 필요하지만, 일단 HTML 파일을 Ghost 형식으로 준비
"""
import json
import os
from datetime import datetime

def prepare_ghost_page():
    """Ghost 페이지용 HTML 준비"""
    
    # HTML 파일 읽기
    html_file = 'working_admin_dashboard.html'
    if not os.path.exists(html_file):
        print(f"❌ {html_file} 파일을 찾을 수 없습니다.")
        return False
    
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Ghost 형식으로 변환
    ghost_ready_html = f"""
<!-- Working Admin Dashboard for Reddit Ghost Publisher -->
{html_content}
<!-- End of Dashboard -->
"""
    
    # Ghost 업로드용 JSON 데이터 준비
    page_data = {
        "pages": [{
            "title": "Working Admin Dashboard",
            "slug": "working-admin-dashboard", 
            "html": ghost_ready_html,
            "status": "published",
            "visibility": "public",
            "meta_title": "Reddit Ghost Publisher - Working Dashboard",
            "meta_description": "Fully functional admin dashboard with real-time API integration",
            "custom_excerpt": "Working admin dashboard with Vercel API integration for Reddit Ghost Publisher system monitoring and control.",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }]
    }
    
    # JSON 파일로 저장
    output_file = 'ghost_upload_data.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(page_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Ghost 업로드 데이터 준비 완료: {output_file}")
    print(f"📄 HTML 길이: {len(html_content):,} 문자")
    print(f"📊 페이지 제목: {page_data['pages'][0]['title']}")
    print(f"🔗 슬러그: {page_data['pages'][0]['slug']}")
    
    return True

def show_manual_instructions():
    """수동 업로드 방법 안내"""
    print("\n" + "="*60)
    print("📋 Ghost CMS 수동 업로드 방법")
    print("="*60)
    print("1. Ghost Admin 패널로 이동: https://american-trends.ghost.io/ghost/")
    print("2. Pages > New page 클릭")
    print("3. 제목: 'Working Admin Dashboard' 입력")
    print("4. 설정(⚙️) > Page URL > 'working-admin-dashboard' 설정")
    print("5. + 버튼 > HTML 카드 추가")
    print("6. working_admin_dashboard.html 내용 전체 복사/붙여넣기")
    print("7. Publish 클릭")
    print("\n접근 URL: https://american-trends.ghost.io/working-admin-dashboard/")
    print("="*60)

if __name__ == "__main__":
    print("🚀 Ghost 페이지 업로드 준비 시작...")
    
    if prepare_ghost_page():
        show_manual_instructions()
        
        print("\n💡 자동 업로드를 위해서는 Ghost Admin Key가 필요합니다.")
        print("   Ghost Admin > Settings > Integrations > Add custom integration")
        print("   에서 'Reddit Publisher Admin' integration을 만들어주세요.")
    else:
        print("❌ 업로드 준비 실패")