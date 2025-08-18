"""
Unit tests for notification system
Tests Slack notifications, budget tracking, and daily reports
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from app.monitoring.notifications import (
    SlackNotifier, AlertSeverity, AlertService, AlertManager
)
from app.monitoring.budget_tracker import BudgetTracker
from app.monitoring.daily_report import DailyReportGenerator


class TestSlackNotifier:
    """Test Slack notification functionality"""
    
    def test_send_alert_success(self):
        """Test successful alert sending"""
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            
            notifier = SlackNotifier("https://hooks.slack.com/test")
            
            result = notifier.send_alert(
                severity=AlertSeverity.HIGH,
                service=AlertService.SYSTEM,
                message="Test alert",
                metrics={"test_metric": 100}
            )
            
            assert result is True
            mock_post.assert_called_once()
            
            # Check payload structure
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            
            assert "🚨 [HIGH] System Alert" in payload['text']
            assert len(payload['attachments']) == 1
            
            attachment = payload['attachments'][0]
            assert attachment['color'] == 'danger'
            
            # Check required fields
            field_titles = [field['title'] for field in attachment['fields']]
            assert 'Severity' in field_titles
            assert 'Service' in field_titles
            assert 'Message' in field_titles
            assert 'Test Metric' in field_titles
    
    def test_send_alert_no_webhook(self):
        """Test alert sending without webhook URL"""
        notifier = SlackNotifier(None)
        
        result = notifier.send_alert(
            severity=AlertSeverity.LOW,
            service=AlertService.COLLECTOR,
            message="Test alert"
        )
        
        assert result is False
    
    def test_send_daily_report_success(self):
        """Test successful daily report sending"""
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            
            notifier = SlackNotifier("https://hooks.slack.com/test")
            
            result = notifier.send_daily_report(
                collected_posts=50,
                published_posts=45,
                token_usage=10000,
                cost_estimate=2.50,
                failure_count=5
            )
            
            assert result is True
            mock_post.assert_called_once()
            
            # Check payload structure
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            
            assert "📊" in payload['text']
            assert "Daily Reddit Publisher Report" in payload['text']
            
            attachment = payload['attachments'][0]
            field_values = {field['title']: field['value'] for field in attachment['fields']}
            
            assert field_values['Posts Collected'] == "50"
            assert field_values['Posts Published'] == "45"
            assert field_values['Token Usage'] == "10,000"
            assert field_values['Estimated Cost'] == "$2.50"
            assert field_values['Failures'] == "5"
    
    def test_alert_severity_colors(self):
        """Test different severity levels produce correct colors"""
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            
            notifier = SlackNotifier("https://hooks.slack.com/test")
            
            # Test different severities
            test_cases = [
                (AlertSeverity.LOW, "good"),
                (AlertSeverity.MEDIUM, "warning"),
                (AlertSeverity.HIGH, "danger"),
                (AlertSeverity.CRITICAL, "#ff0000")
            ]
            
            for severity, expected_color in test_cases:
                notifier.send_alert(
                    severity=severity,
                    service=AlertService.SYSTEM,
                    message="Test"
                )
                
                call_args = mock_post.call_args
                payload = call_args[1]['json']
                attachment = payload['attachments'][0]
                
                assert attachment['color'] == expected_color


class TestBudgetTracker:
    """Test budget tracking functionality"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        session = Mock()
        return session
    
    @pytest.fixture
    def budget_tracker(self, mock_db_session):
        """Create budget tracker with mocked session"""
        return BudgetTracker(mock_db_session)
    
    def test_get_reddit_daily_usage(self, budget_tracker, mock_db_session):
        """Test Reddit API usage calculation"""
        # Mock query result
        mock_db_session.query.return_value.filter.return_value.scalar.return_value = 100
        
        # Mock the settings on the budget tracker instance
        budget_tracker.settings.reddit_daily_calls_limit = 1000
        
        calls_made, usage_percentage = budget_tracker.get_reddit_daily_usage()
        
        assert calls_made == 100
        assert usage_percentage == 0.1  # 100/1000
    
    def test_get_openai_daily_usage(self, budget_tracker, mock_db_session):
        """Test OpenAI token usage calculation"""
        # Mock query result
        mock_result = Mock()
        mock_result.total_tokens = 5000
        mock_result.total_cost = 2.50
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_result
        
        # Mock the settings on the budget tracker instance
        budget_tracker.settings.openai_daily_tokens_limit = 10000
        
        tokens_used, usage_percentage, cost_usd = budget_tracker.get_openai_daily_usage()
        
        assert tokens_used == 5000
        assert usage_percentage == 0.5  # 5000/10000
        assert cost_usd == 2.50
    
    def test_budget_alert_threshold(self, budget_tracker):
        """Test budget alert triggering at 80% threshold"""
        with patch.object(budget_tracker, 'get_reddit_daily_usage') as mock_usage:
            mock_usage.return_value = (800, 0.8)  # Exactly at threshold
            
            with patch('app.monitoring.budget_tracker.send_api_budget_alert') as mock_alert:
                mock_alert.return_value = True
                
                result = budget_tracker.check_reddit_budget_alert()
                
                assert result is True
                mock_alert.assert_called_once_with(
                    budget_tracker.db_session,
                    "reddit",
                    0.8
                )
    
    def test_budget_exhaustion_check(self, budget_tracker):
        """Test budget exhaustion detection"""
        with patch.object(budget_tracker, 'get_reddit_daily_usage') as mock_usage:
            mock_usage.return_value = (1000, 1.0)  # 100% used
            
            result = budget_tracker.is_reddit_budget_exhausted()
            
            assert result is True


class TestDailyReportGenerator:
    """Test daily report generation"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        session = Mock()
        return session
    
    @pytest.fixture
    def report_generator(self, mock_db_session):
        """Create report generator with mocked session"""
        return DailyReportGenerator(mock_db_session)
    
    def test_generate_daily_report_structure(self, report_generator, mock_db_session):
        """Test daily report has correct structure"""
        # Mock all database queries to return empty results
        mock_db_session.query.return_value.filter.return_value.scalar.return_value = 0
        mock_db_session.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
        mock_db_session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        report = report_generator.generate_daily_report()
        
        # Check required top-level keys
        required_keys = [
            'report_date', 'generated_at', 'overall_status',
            'collection', 'processing', 'publishing', 'token_usage',
            'errors', 'performance', 'costs', 'summary'
        ]
        
        for key in required_keys:
            assert key in report
        
        # Check summary structure
        summary = report['summary']
        summary_keys = [
            'total_posts_collected', 'total_posts_processed', 'total_posts_published',
            'total_failures', 'success_rate', 'total_cost_usd', 'avg_processing_time_minutes'
        ]
        
        for key in summary_keys:
            assert key in summary
    
    def test_cost_analysis_calculation(self, report_generator):
        """Test cost analysis calculations"""
        token_metrics = {
            "total_cost_usd": 5.0,
            "total_tokens": 10000,
            "total_api_calls": 20
        }
        
        cost_analysis = report_generator._calculate_cost_analysis(token_metrics)
        
        assert cost_analysis['total_cost_usd'] == 5.0
        assert cost_analysis['cost_per_post'] == 0.25  # 5.0 / 20
        assert cost_analysis['estimated_monthly_cost'] == 150.0  # 5.0 * 30
        assert cost_analysis['cost_per_1k_tokens'] == 0.5  # 5.0 / 10 * 1000
    
    def test_overall_status_determination(self, report_generator):
        """Test overall status determination logic"""
        # Test excellent status
        collection_metrics = {"collection_success_rate": 0.98}
        processing_metrics = {"processing_success_rate": 0.97}
        publishing_metrics = {"publishing_success_rate": 0.96}
        error_metrics = {"total_failures": 0}
        
        status = report_generator._determine_overall_status(
            collection_metrics, processing_metrics, publishing_metrics, error_metrics
        )
        
        assert status == "excellent"
        
        # Test poor status
        collection_metrics = {"collection_success_rate": 0.5}
        processing_metrics = {"processing_success_rate": 0.6}
        publishing_metrics = {"publishing_success_rate": 0.4}
        error_metrics = {"total_failures": 50}
        
        status = report_generator._determine_overall_status(
            collection_metrics, processing_metrics, publishing_metrics, error_metrics
        )
        
        assert status == "poor"
    
    def test_send_daily_report_slack_integration(self, report_generator):
        """Test daily report Slack integration"""
        with patch.object(report_generator, 'generate_daily_report') as mock_generate:
            mock_generate.return_value = {
                'report_date': '2024-01-01',
                'overall_status': 'good',
                'summary': {
                    'total_posts_collected': 100,
                    'total_posts_published': 95,
                    'success_rate': 0.95,
                    'total_failures': 5,
                    'total_cost_usd': 3.50,
                    'avg_processing_time_minutes': 2.5
                },
                'costs': {'total_cost_usd': 3.50, 'cost_breakdown': {}},
                'errors': {'total_failures': 5, 'common_errors': []},
                'token_usage': {'total_tokens': 7000}
            }
            
            with patch.object(report_generator, '_send_slack_report') as mock_slack:
                mock_slack.return_value = True
                
                result = report_generator.send_daily_report()
                
                assert result is True
                mock_generate.assert_called_once()
                mock_slack.assert_called_once()


class TestAlertManager:
    """Test alert management functionality"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return Mock()
    
    @pytest.fixture
    def alert_manager(self, mock_db_session):
        """Create alert manager with mocked dependencies"""
        with patch('app.monitoring.alert_service.MetricsCollector'):
            with patch('app.monitoring.alert_service.BudgetTracker'):
                return AlertManager(mock_db_session)
    
    def test_check_failure_rate_alert(self, alert_manager):
        """Test failure rate alert checking"""
        with patch.object(alert_manager.metrics_collector, 'get_recent_failure_rate') as mock_rate:
            mock_rate.return_value = 0.06  # 6% failure rate
            
            with patch.object(alert_manager.notifier, 'send_alert') as mock_send:
                mock_send.return_value = True
                
                with patch('app.monitoring.alert_service.get_settings') as mock_settings:
                    mock_settings.return_value.failure_rate_threshold = 0.05
                    
                    result = alert_manager.check_failure_rate_alert()
                    
                    assert result is True
                    mock_send.assert_called_once()
                    
                    # Check alert parameters
                    call_args = mock_send.call_args
                    assert call_args[1]['severity'] == AlertSeverity.HIGH
                    assert call_args[1]['service'] == AlertService.SYSTEM
    
    def test_check_queue_backlog_alert(self, alert_manager):
        """Test queue backlog alert checking"""
        with patch.object(alert_manager.metrics_collector, 'get_queue_metrics') as mock_queue:
            mock_queue.return_value = {
                "queue_total_pending": 600,
                "queue_collect_pending": 200,
                "queue_process_pending": 200,
                "queue_publish_pending": 200
            }
            
            with patch.object(alert_manager.notifier, 'send_alert') as mock_send:
                mock_send.return_value = True
                
                with patch('app.monitoring.alert_service.get_settings') as mock_settings:
                    mock_settings.return_value.queue_alert_threshold = 500
                    
                    result = alert_manager.check_queue_backlog_alert()
                    
                    assert result is True
                    mock_send.assert_called_once()
                    
                    # Check alert parameters
                    call_args = mock_send.call_args
                    assert call_args[1]['severity'] == AlertSeverity.MEDIUM
                    assert call_args[1]['service'] == AlertService.QUEUE


if __name__ == "__main__":
    pytest.main([__file__])