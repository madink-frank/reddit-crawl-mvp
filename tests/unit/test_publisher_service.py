"""
Unit tests for Publisher service
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from workers.publisher.tasks import publish_to_ghost
from workers.publisher.template_engine import TemplateEngine, ArticleTemplate


class TestTemplateEngine:
    """Test template engine functionality"""
    
    @pytest.fixture
    def template_engine(self):
        """Create template engine"""
        return TemplateEngine()
    
    def test_render_article_template_basic(self, template_engine):
        """Test basic article template rendering"""
        post_data = {
            'title': 'Test Article Title',
            'summary_ko': '이것은 테스트 기사의 한국어 요약입니다.',
            'content': 'This is the original Reddit content.',
            'url': 'https://reddit.com/r/test/comments/abc123/',
            'subreddit': 'test',
            'tags': ['기술', '테스트', '프로그래밍'],
            'pain_points': {
                'main_issues': ['성능 문제', '사용성 문제'],
                'severity': 'medium'
            },
            'product_ideas': {
                'suggestions': ['모바일 앱 개발', 'API 개선'],
                'priority': 'high'
            }
        }
        
        html_content = template_engine.render_article(post_data)
        
        # Check basic structure
        assert '<h1>Test Article Title</h1>' in html_content
        assert '이것은 테스트 기사의 한국어 요약입니다.' in html_content
        assert 'This is the original Reddit content.' in html_content
        
        # Check source attribution
        assert 'Source:' in html_content
        assert 'https://reddit.com/r/test/comments/abc123/' in html_content
        assert 'Media and usernames belong to their respective owners' in html_content
        assert 'Takedown requests will be honored' in html_content
        
        # Check pain points section
        assert '성능 문제' in html_content
        assert '사용성 문제' in html_content
        
        # Check product ideas section
        assert '모바일 앱 개발' in html_content
        assert 'API 개선' in html_content
    
    def test_render_article_template_with_images(self, template_engine):
        """Test article template with processed images"""
        post_data = {
            'title': 'Test Article with Images',
            'summary_ko': '이미지가 포함된 테스트 기사입니다.',
            'content': 'Check out this image: ![Test Image](https://reddit.com/image.jpg)',
            'url': 'https://reddit.com/r/test/comments/abc123/',
            'subreddit': 'test',
            'processed_images': [
                {
                    'original_url': 'https://reddit.com/image.jpg',
                    'ghost_url': 'https://cdn.ghost.io/processed-image.jpg',
                    'alt_text': 'Test Image'
                }
            ]
        }
        
        html_content = template_engine.render_article(post_data)
        
        # Check that Reddit URLs are replaced with Ghost URLs
        assert 'https://cdn.ghost.io/processed-image.jpg' in html_content
        assert 'https://reddit.com/image.jpg' not in html_content
    
    def test_render_article_template_minimal(self, template_engine):
        """Test article template with minimal data"""
        post_data = {
            'title': 'Minimal Article',
            'summary_ko': '최소한의 데이터로 생성된 기사입니다.',
            'content': 'Minimal content.',
            'url': 'https://reddit.com/r/test/comments/minimal/',
            'subreddit': 'test'
        }
        
        html_content = template_engine.render_article(post_data)
        
        # Should still render basic structure
        assert '<h1>Minimal Article</h1>' in html_content
        assert '최소한의 데이터로 생성된 기사입니다.' in html_content
        assert 'Source:' in html_content
    
    def test_process_markdown_to_html(self, template_engine):
        """Test Markdown to HTML conversion"""
        markdown_content = """
# Header 1
## Header 2

This is **bold** text and *italic* text.

- List item 1
- List item 2

[Link](https://example.com)

```python
def hello():
    print("Hello, World!")
```
        """
        
        html_content = template_engine._process_markdown(markdown_content)
        
        assert '<h1>Header 1</h1>' in html_content
        assert '<h2>Header 2</h2>' in html_content
        assert '<strong>bold</strong>' in html_content
        assert '<em>italic</em>' in html_content
        assert '<ul>' in html_content
        assert '<li>List item 1</li>' in html_content
        assert '<a href="https://example.com">Link</a>' in html_content
        assert '<code>' in html_content
    
    def test_add_source_attribution(self, template_engine):
        """Test source attribution addition"""
        reddit_url = 'https://reddit.com/r/test/comments/abc123/'
        
        attribution = template_engine._add_source_attribution(reddit_url)
        
        assert '<hr>' in attribution
        assert 'Source:' in attribution
        assert reddit_url in attribution
        assert 'Media and usernames belong to their respective owners' in attribution
        assert 'Takedown requests will be honored' in attribution
    
    def test_format_pain_points(self, template_engine):
        """Test pain points formatting"""
        pain_points = {
            'main_issues': ['성능이 느림', '사용자 인터페이스가 복잡함', '문서가 부족함'],
            'severity': 'high',
            'categories': ['performance', 'usability', 'documentation']
        }
        
        formatted = template_engine._format_pain_points(pain_points)
        
        assert '<h3>주요 문제점</h3>' in formatted
        assert '성능이 느림' in formatted
        assert '사용자 인터페이스가 복잡함' in formatted
        assert '문서가 부족함' in formatted
        assert '<ul>' in formatted
        assert '<li>' in formatted
    
    def test_format_product_ideas(self, template_engine):
        """Test product ideas formatting"""
        product_ideas = {
            'suggestions': ['모바일 앱 개발', 'API 성능 개선', '사용자 가이드 작성'],
            'priority': 'medium',
            'feasibility': 'high'
        }
        
        formatted = template_engine._format_product_ideas(product_ideas)
        
        assert '<h3>제품 아이디어</h3>' in formatted
        assert '모바일 앱 개발' in formatted
        assert 'API 성능 개선' in formatted
        assert '사용자 가이드 작성' in formatted
        assert '<ul>' in formatted
        assert '<li>' in formatted


class TestArticleTemplate:
    """Test Article template class"""
    
    def test_article_template_creation(self):
        """Test creating an article template"""
        template = ArticleTemplate()
        
        assert template.name == 'article'
        assert template.description == 'Standard article template for Reddit content'
        assert hasattr(template, 'render')
    
    def test_article_template_render(self):
        """Test article template rendering"""
        template = ArticleTemplate()
        
        post_data = {
            'title': 'Template Test',
            'summary_ko': '템플릿 테스트입니다.',
            'content': 'Template test content.',
            'url': 'https://reddit.com/test',
            'subreddit': 'test'
        }
        
        result = template.render(post_data)
        
        assert isinstance(result, str)
        assert 'Template Test' in result
        assert '템플릿 테스트입니다.' in result


class TestPublisherTasks:
    """Test publisher Celery tasks"""
    
    @pytest.mark.asyncio
    async def test_publish_to_ghost_success(self):
        """Test successful Ghost publishing"""
        with patch('workers.publisher.tasks.get_db_session') as mock_db:
            with patch('workers.publisher.tasks.get_ghost_client') as mock_ghost:
                with patch('workers.publisher.tasks.TemplateEngine') as mock_template:
                    # Mock database
                    mock_session = Mock()
                    mock_db.return_value.__enter__.return_value = mock_session
                    
                    mock_post = Mock()
                    mock_post.id = 'test-uuid'
                    mock_post.title = 'Test Post'
                    mock_post.summary_ko = '테스트 포스트'
                    mock_post.tags = ['테스트', '기술']
                    mock_post.reddit_post_id = 'test123'
                    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_post
                    
                    # Mock Ghost client
                    mock_ghost_client = AsyncMock()
                    mock_ghost.return_value = mock_ghost_client
                    mock_ghost_client.create_post.return_value = {
                        'id': 'ghost-post-123',
                        'url': 'https://blog.example.com/test-post/',
                        'slug': 'test-post'
                    }
                    
                    # Mock template engine
                    mock_template_instance = Mock()
                    mock_template.return_value = mock_template_instance
                    mock_template_instance.render_article.return_value = '<h1>Test Post</h1><p>Content</p>'
                    
                    # Execute task
                    result = await publish_to_ghost('test123')
                    
                    # Verify results
                    assert result['status'] == 'success'
                    assert result['ghost_url'] == 'https://blog.example.com/test-post/'
                    
                    # Verify database updates
                    assert mock_post.ghost_post_id == 'ghost-post-123'
                    assert mock_post.ghost_url == 'https://blog.example.com/test-post/'
                    assert mock_post.ghost_slug == 'test-post'
                    mock_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_publish_to_ghost_post_not_found(self):
        """Test publishing with non-existent post"""
        with patch('workers.publisher.tasks.get_db_session') as mock_db:
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session
            mock_session.query.return_value.filter_by.return_value.first.return_value = None
            
            result = await publish_to_ghost('non-existent-id')
            
            assert result['status'] == 'error'
            assert 'not found' in result['error'].lower()
    
    @pytest.mark.asyncio
    async def test_publish_to_ghost_already_published(self):
        """Test publishing already published post (idempotency)"""
        with patch('workers.publisher.tasks.get_db_session') as mock_db:
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session
            
            mock_post = Mock()
            mock_post.ghost_post_id = 'existing-ghost-id'
            mock_post.ghost_url = 'https://blog.example.com/existing-post/'
            mock_post.content_hash = 'existing-hash'
            mock_session.query.return_value.filter_by.return_value.first.return_value = mock_post
            
            # Mock content hash calculation to return same hash (no changes)
            with patch('workers.publisher.tasks.calculate_content_hash') as mock_hash:
                mock_hash.return_value = 'existing-hash'
                
                result = await publish_to_ghost('test123')
                
                assert result['status'] == 'skipped'
                assert 'already published' in result['message'].lower()
    
    @pytest.mark.asyncio
    async def test_publish_to_ghost_content_updated(self):
        """Test publishing post with updated content"""
        with patch('workers.publisher.tasks.get_db_session') as mock_db:
            with patch('workers.publisher.tasks.get_ghost_client') as mock_ghost:
                with patch('workers.publisher.tasks.TemplateEngine') as mock_template:
                    # Mock database
                    mock_session = Mock()
                    mock_db.return_value.__enter__.return_value = mock_session
                    
                    mock_post = Mock()
                    mock_post.ghost_post_id = 'existing-ghost-id'
                    mock_post.content_hash = 'old-hash'
                    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_post
                    
                    # Mock Ghost client
                    mock_ghost_client = AsyncMock()
                    mock_ghost.return_value = mock_ghost_client
                    mock_ghost_client.update_post.return_value = {
                        'id': 'existing-ghost-id',
                        'url': 'https://blog.example.com/updated-post/',
                        'slug': 'updated-post'
                    }
                    
                    # Mock template engine
                    mock_template_instance = Mock()
                    mock_template.return_value = mock_template_instance
                    mock_template_instance.render_article.return_value = '<h1>Updated Post</h1>'
                    
                    # Mock content hash to show change
                    with patch('workers.publisher.tasks.calculate_content_hash') as mock_hash:
                        mock_hash.return_value = 'new-hash'
                        
                        result = await publish_to_ghost('test123')
                        
                        assert result['status'] == 'updated'
                        mock_ghost_client.update_post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_publish_to_ghost_with_images(self):
        """Test publishing post with image processing"""
        with patch('workers.publisher.tasks.get_db_session') as mock_db:
            with patch('workers.publisher.tasks.get_ghost_client') as mock_ghost:
                with patch('workers.publisher.tasks.get_image_handler') as mock_image:
                    with patch('workers.publisher.tasks.TemplateEngine') as mock_template:
                        # Mock database
                        mock_session = Mock()
                        mock_db.return_value.__enter__.return_value = mock_session
                        
                        mock_post = Mock()
                        mock_post.content = 'Check out this image: ![Test](https://reddit.com/img.jpg)'
                        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_post
                        
                        # Mock image handler
                        mock_image_handler = AsyncMock()
                        mock_image.return_value = mock_image_handler
                        mock_image_handler.process_content_images.return_value = (
                            'Check out this image: ![Test](https://cdn.ghost.io/processed-img.jpg)',
                            [{'original_url': 'https://reddit.com/img.jpg', 'ghost_url': 'https://cdn.ghost.io/processed-img.jpg'}]
                        )
                        mock_image_handler.get_feature_image.return_value = 'https://cdn.ghost.io/feature.jpg'
                        
                        # Mock Ghost client
                        mock_ghost_client = AsyncMock()
                        mock_ghost.return_value = mock_ghost_client
                        mock_ghost_client.create_post.return_value = {
                            'id': 'ghost-post-123',
                            'url': 'https://blog.example.com/test-post/',
                            'slug': 'test-post'
                        }
                        
                        # Mock template engine
                        mock_template_instance = Mock()
                        mock_template.return_value = mock_template_instance
                        mock_template_instance.render_article.return_value = '<h1>Test</h1>'
                        
                        result = await publish_to_ghost('test123')
                        
                        assert result['status'] == 'success'
                        mock_image_handler.process_content_images.assert_called_once()
                        mock_image_handler.get_feature_image.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_publish_to_ghost_ghost_api_error(self):
        """Test publishing with Ghost API error"""
        with patch('workers.publisher.tasks.get_db_session') as mock_db:
            with patch('workers.publisher.tasks.get_ghost_client') as mock_ghost:
                with patch('workers.publisher.tasks.TemplateEngine') as mock_template:
                    # Mock database
                    mock_session = Mock()
                    mock_db.return_value.__enter__.return_value = mock_session
                    
                    mock_post = Mock()
                    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_post
                    
                    # Mock Ghost client to raise error
                    mock_ghost_client = AsyncMock()
                    mock_ghost.return_value = mock_ghost_client
                    from workers.publisher.ghost_client import GhostAPIError
                    mock_ghost_client.create_post.side_effect = GhostAPIError("API Error")
                    
                    # Mock template engine
                    mock_template_instance = Mock()
                    mock_template.return_value = mock_template_instance
                    mock_template_instance.render_article.return_value = '<h1>Test</h1>'
                    
                    result = await publish_to_ghost('test123')
                    
                    assert result['status'] == 'error'
                    assert 'API Error' in result['error']
    
    @pytest.mark.asyncio
    async def test_publish_to_ghost_with_default_og_image(self):
        """Test publishing with default OG image when no media present"""
        with patch('workers.publisher.tasks.get_db_session') as mock_db:
            with patch('workers.publisher.tasks.get_ghost_client') as mock_ghost:
                with patch('workers.publisher.tasks.get_image_handler') as mock_image:
                    with patch('workers.publisher.tasks.TemplateEngine') as mock_template:
                        with patch('workers.publisher.tasks.get_settings') as mock_settings:
                            # Mock settings
                            mock_settings.return_value.default_og_image_url = 'https://cdn.ghost.io/default-og.jpg'
                            
                            # Mock database
                            mock_session = Mock()
                            mock_db.return_value.__enter__.return_value = mock_session
                            
                            mock_post = Mock()
                            mock_post.content = 'Text only content, no images'
                            mock_session.query.return_value.filter_by.return_value.first.return_value = mock_post
                            
                            # Mock image handler - no images found
                            mock_image_handler = AsyncMock()
                            mock_image.return_value = mock_image_handler
                            mock_image_handler.process_content_images.return_value = ('Text only content, no images', [])
                            mock_image_handler.get_feature_image.return_value = 'https://cdn.ghost.io/default-og.jpg'
                            
                            # Mock Ghost client
                            mock_ghost_client = AsyncMock()
                            mock_ghost.return_value = mock_ghost_client
                            mock_ghost_client.create_post.return_value = {
                                'id': 'ghost-post-123',
                                'url': 'https://blog.example.com/test-post/',
                                'slug': 'test-post'
                            }
                            
                            # Mock template engine
                            mock_template_instance = Mock()
                            mock_template.return_value = mock_template_instance
                            mock_template_instance.render_article.return_value = '<h1>Test</h1>'
                            
                            result = await publish_to_ghost('test123')
                            
                            assert result['status'] == 'success'
                            # Verify that create_post was called with feature_image
                            call_args = mock_ghost_client.create_post.call_args[0][0]
                            assert call_args.feature_image == 'https://cdn.ghost.io/default-og.jpg'


if __name__ == "__main__":
    pytest.main([__file__])