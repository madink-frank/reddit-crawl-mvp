#!/usr/bin/env python3
"""
Enhanced Dashboard Test Server
로컬에서 새로운 대시보드를 테스트하기 위한 간단한 서버
"""

import http.server
import socketserver
import webbrowser
import os
from pathlib import Path

PORT = 8080

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # CORS 헤더 추가
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_GET(self):
        if self.path == '/' or self.path == '/dashboard':
            self.path = '/enhanced_dashboard.html'
        return super().do_GET()

def main():
    # 현재 디렉토리에서 서버 실행
    os.chdir(Path(__file__).parent)
    
    with socketserver.TCPServer(("", PORT), CustomHTTPRequestHandler) as httpd:
        print(f"🚀 Enhanced Dashboard Test Server")
        print(f"📍 서버 주소: http://localhost:{PORT}")
        print(f"🌐 대시보드: http://localhost:{PORT}/dashboard")
        print(f"⚡ Vercel API: https://reddit-crawl-mvp.vercel.app")
        print(f"🛑 종료하려면 Ctrl+C를 누르세요")
        
        # 자동으로 브라우저 열기
        webbrowser.open(f'http://localhost:{PORT}/dashboard')
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 서버를 종료합니다...")
            httpd.shutdown()

if __name__ == "__main__":
    main()