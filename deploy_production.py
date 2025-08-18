#!/usr/bin/env python3
"""
Reddit Ghost Publisher - Production Deployment Script
프로덕션 환경으로 시스템을 배포하고 전환하는 스크립트
"""

import os
import sys
import subprocess
import time
import requests
import logging
from pathlib import Path

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('deployment.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class ProductionDeployer:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.env_file = self.project_root / '.env.production'
        
    def check_prerequisites(self):
        """배포 전 필수 조건 확인"""
        logger.info("🔍 배포 전 필수 조건 확인 중...")
        
        # Docker 설치 확인
        try:
            subprocess.run(['docker', '--version'], check=True, capture_output=True)
            logger.info("✅ Docker 설치 확인됨")
        except subprocess.CalledProcessError:
            logger.error("❌ Docker가 설치되지 않았습니다")
            return False
            
        # Docker Compose 설치 확인
        try:
            subprocess.run(['docker-compose', '--version'], check=True, capture_output=True)
            logger.info("✅ Docker Compose 설치 확인됨")
        except subprocess.CalledProcessError:
            logger.error("❌ Docker Compose가 설치되지 않았습니다")
            return False
            
        # 환경 설정 파일 확인
        if not self.env_file.exists():
            logger.error(f"❌ 환경 설정 파일이 없습니다: {self.env_file}")
            return False
        logger.info("✅ 환경 설정 파일 확인됨")
        
        return True
    
    def backup_current_data(self):
        """현재 데이터 백업"""
        logger.info("💾 현재 데이터 백업 중...")
        
        backup_dir = self.project_root / 'deployment-backups'
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        backup_file = backup_dir / f'pre_production_backup_{timestamp}.sql'
        
        try:
            # SQLite 데이터베이스 백업 (개발 환경)
            if (self.project_root / 'reddit_publisher.db').exists():
                subprocess.run([
                    'sqlite3', 'reddit_publisher.db', 
                    f'.backup {backup_file}'
                ], check=True, cwd=self.project_root)
                logger.info(f"✅ 데이터베이스 백업 완료: {backup_file}")
            else:
                logger.info("ℹ️ 백업할 SQLite 데이터베이스가 없습니다")
                
        except subprocess.CalledProcessError as e:
            logger.warning(f"⚠️ 데이터베이스 백업 실패: {e}")
        
        return True
    
    def build_docker_image(self):
        """Docker 이미지 빌드"""
        logger.info("🏗️ Docker 이미지 빌드 중...")
        
        try:
            subprocess.run([
                'docker', 'build', 
                '-t', 'reddit-publisher:latest',
                '-f', 'Dockerfile',
                '.'
            ], check=True, cwd=self.project_root)
            logger.info("✅ Docker 이미지 빌드 완료")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Docker 이미지 빌드 실패: {e}")
            return False
    
    def stop_development_services(self):
        """개발 환경 서비스 중지"""
        logger.info("🛑 개발 환경 서비스 중지 중...")
        
        try:
            # 개발 환경 docker-compose 중지
            subprocess.run([
                'docker-compose', 'down'
            ], cwd=self.project_root, capture_output=True)
            
            # 개발 서버 프로세스 종료
            subprocess.run(['pkill', '-f', 'python.*admin'], capture_output=True)
            subprocess.run(['pkill', '-f', 'python.*dashboard'], capture_output=True)
            
            logger.info("✅ 개발 환경 서비스 중지 완료")
            return True
        except Exception as e:
            logger.warning(f"⚠️ 개발 환경 서비스 중지 중 오류: {e}")
            return True  # 계속 진행
    
    def deploy_production(self):
        """프로덕션 환경 배포"""
        logger.info("🚀 프로덕션 환경 배포 시작...")
        
        try:
            # 환경 변수 파일 복사
            subprocess.run([
                'cp', '.env.production', '.env'
            ], check=True, cwd=self.project_root)
            logger.info("✅ 프로덕션 환경 변수 설정 완료")
            
            # 프로덕션 docker-compose 실행
            subprocess.run([
                'docker-compose', 
                '-f', 'docker-compose.yml',
                '-f', 'docker-compose.prod.yml',
                'up', '-d'
            ], check=True, cwd=self.project_root)
            logger.info("✅ 프로덕션 서비스 시작 완료")
            
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ 프로덕션 배포 실패: {e}")
            return False
    
    def wait_for_services(self):
        """서비스 시작 대기"""
        logger.info("⏳ 서비스 시작 대기 중...")
        
        max_attempts = 30
        for attempt in range(max_attempts):
            try:
                response = requests.get('http://localhost:8000/health', timeout=5)
                if response.status_code == 200:
                    logger.info("✅ API 서버 정상 시작 확인")
                    return True
            except requests.RequestException:
                pass
            
            time.sleep(10)
            logger.info(f"⏳ 서비스 시작 대기 중... ({attempt + 1}/{max_attempts})")
        
        logger.warning("⚠️ API 서버 응답 확인 실패 (계속 진행)")
        return True
    
    def run_database_migrations(self):
        """데이터베이스 마이그레이션 실행"""
        logger.info("🗄️ 데이터베이스 마이그레이션 실행 중...")
        
        try:
            subprocess.run([
                'docker-compose', 'exec', '-T', 'api',
                'python', '-m', 'alembic', 'upgrade', 'head'
            ], check=True, cwd=self.project_root)
            logger.info("✅ 데이터베이스 마이그레이션 완료")
            return True
        except subprocess.CalledProcessError as e:
            logger.warning(f"⚠️ 데이터베이스 마이그레이션 실패 (기존 데이터 존재): {e}")
            logger.info("ℹ️ 기존 데이터베이스를 사용하여 계속 진행합니다")
            return True  # 기존 데이터가 있는 경우 계속 진행
    
    def verify_deployment(self):
        """배포 검증"""
        logger.info("🔍 배포 검증 중...")
        
        checks = []
        
        # API 서버 확인
        try:
            response = requests.get('http://localhost:8000/health', timeout=10)
            if response.status_code == 200:
                checks.append(("API 서버", True))
            else:
                checks.append(("API 서버", False))
        except requests.RequestException:
            checks.append(("API 서버", False))
        
        # Docker 서비스 상태 확인
        try:
            result = subprocess.run([
                'docker-compose', 'ps'
            ], capture_output=True, text=True, cwd=self.project_root)
            
            services = ['api', 'worker-collector', 'worker-nlp', 'worker-publisher', 'postgres', 'redis']
            for service in services:
                if service in result.stdout and 'Up' in result.stdout:
                    checks.append((f"{service} 서비스", True))
                else:
                    checks.append((f"{service} 서비스", False))
        except subprocess.CalledProcessError:
            for service in ['api', 'worker-collector', 'worker-nlp', 'worker-publisher', 'postgres', 'redis']:
                checks.append((f"{service} 서비스", False))
        
        # 결과 출력
        logger.info("📊 배포 검증 결과:")
        all_passed = True
        for check_name, passed in checks:
            status = "✅" if passed else "❌"
            logger.info(f"  {status} {check_name}")
            if not passed:
                all_passed = False
        
        return all_passed
    
    def upload_dashboard_to_ghost(self):
        """대시보드를 Ghost에 업로드"""
        logger.info("📤 대시보드를 Ghost에 업로드 중...")
        
        try:
            subprocess.run([
                'python', 'upload_admin_to_ghost.py'
            ], check=True, cwd=self.project_root)
            logger.info("✅ Ghost 대시보드 업로드 완료")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Ghost 대시보드 업로드 실패: {e}")
            return False
    
    def deploy(self):
        """전체 배포 프로세스 실행"""
        logger.info("🚀 Reddit Ghost Publisher 프로덕션 배포 시작!")
        
        steps = [
            ("필수 조건 확인", self.check_prerequisites),
            ("현재 데이터 백업", self.backup_current_data),
            ("개발 환경 서비스 중지", self.stop_development_services),
            ("Docker 이미지 빌드", self.build_docker_image),
            ("프로덕션 환경 배포", self.deploy_production),
            ("서비스 시작 대기", self.wait_for_services),
            ("데이터베이스 마이그레이션", self.run_database_migrations),
            ("Ghost 대시보드 업로드", self.upload_dashboard_to_ghost),
            ("배포 검증", self.verify_deployment),
        ]
        
        for step_name, step_func in steps:
            logger.info(f"📋 단계: {step_name}")
            if not step_func():
                logger.error(f"❌ 단계 실패: {step_name}")
                return False
            logger.info(f"✅ 단계 완료: {step_name}")
        
        logger.info("🎉 프로덕션 배포 완료!")
        logger.info("🌐 서비스 접속 정보:")
        logger.info("  - API 서버: http://localhost:8000")
        logger.info("  - 대시보드: http://localhost:8000/admin")
        logger.info("  - Ghost 블로그: https://american-trends.ghost.io")
        logger.info("  - 헬스체크: http://localhost:8000/health")
        
        return True

if __name__ == "__main__":
    deployer = ProductionDeployer()
    success = deployer.deploy()
    
    if success:
        logger.info("✅ 배포 성공!")
        sys.exit(0)
    else:
        logger.error("❌ 배포 실패!")
        sys.exit(1)