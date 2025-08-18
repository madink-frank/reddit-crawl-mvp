#!/usr/bin/env python3
"""
Celery 작업 직접 테스트
"""
from app.celery_app import celery_app
from workers.collector.tasks import collect_reddit_posts

def test_celery_connection():
    """Celery 연결 테스트"""
    try:
        # Celery 상태 확인
        inspect = celery_app.control.inspect()
        
        # 활성 워커 확인
        active_workers = inspect.active()
        print(f"활성 워커: {active_workers}")
        
        # 등록된 작업 확인
        registered_tasks = inspect.registered()
        print(f"등록된 작업: {registered_tasks}")
        
        # 큐 상태 확인
        stats = inspect.stats()
        print(f"워커 통계: {stats}")
        
        return True
        
    except Exception as e:
        print(f"Celery 연결 오류: {e}")
        return False

def test_direct_task():
    """직접 작업 실행 테스트"""
    try:
        print("직접 Reddit 수집 작업 실행...")
        
        # 작업 실행
        result = collect_reddit_posts.delay(
            subreddits=["programming"],
            limit=3
        )
        
        print(f"작업 ID: {result.id}")
        print(f"작업 상태: {result.status}")
        
        # 결과 대기 (최대 60초)
        try:
            task_result = result.get(timeout=60)
            print(f"작업 결과: {task_result}")
            return True
        except Exception as e:
            print(f"작업 실행 오류: {e}")
            return False
            
    except Exception as e:
        print(f"작업 생성 오류: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Celery 직접 테스트")
    print("=" * 40)
    
    if test_celery_connection():
        print("\n✅ Celery 연결 성공")
        print("\n🚀 직접 작업 테스트 시작...")
        test_direct_task()
    else:
        print("\n❌ Celery 연결 실패")