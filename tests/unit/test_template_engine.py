"""
Unit tests for Template Engine
"""

import pytest
import json
from unittest.mock import patch, mock_open
from pathlib import Path

from workers.publisher.template_engine import (
    TemplateEngine,
    TemplateType,
    get_template_engine
)


class TestTemplateEngine:
    """Test TemplateEngine functionality"""
    
    @pytest.fixture
    def sample_post_data(self):
        """Sample post data for testing"""
        return {
            'title': 'Test Reddit Post',
            'subreddit': 'technology',
            'score': 150,
            'comments': 25,
            'url': 'https://reddit.com/r/technology/test',
            'author': 'test_user',
            'content': '# Test Content\n\nThis is a **test** post with *markdown*.',
            'summary_ko': '이것은 테스트 게시글입니다.',
            'topic_tag': 'tech',
            'pain_points': ['Problem 1', 'Problem 2'],
            'product_ideas': ['Idea 1', 'Idea 2']
        }
    
    @pytest.fixture
    def mock_templates(self):
        """Mock template files"""
        return {
            'article.hbs': '''
            <article>
                <h1>{{title}}</h1>
                <div>{{summary_ko}}</div>
                <div>{{{content}}}</div>
                {{#if pain_points}}
                <ul>{{#each pain_points}}<li>{{this}}</li>{{/each}}</ul>
                {{/if}}
            </article>
            ''',
            'list.hbs': '''
            <article>
                <h1>{{title}}</h1>
                <div>{{summary_ko}}</div>
                {{#if items}}
                <ol>{{#each items}}<li>{{this}}</li>{{/each}}</ol>
                {{/if}}
            </article>
            ''',
            'qa.hbs': '''
            <article>
                <h1>{{title}}</h1>
                <div class="question">{{{content}}}</div>
                <div class="answer">{{summary_ko}}</div>
                {{#if top_answers}}
                {{#each top_answers}}
                <div class="answer">{{{content}}}</div>
                {{/each}}
                {{/if}}
            </article>
            '''
        }
    
    def test_markdown_to_html(self):
        """Test markdown to HTML conversion"""
        engine = TemplateEngine()
        
        markdown_text = "# Header\n\nThis is **bold** and *italic* text."
        html = engine.markdown_to_html(markdown_text)
        
        assert '<h1' in html and 'Header</h1>' in html
        assert '<strong>bold</strong>' in html
        assert '<em>italic</em>' in html
    
    def test_markdown_to_html_empty(self):
        """Test markdown conversion with empty input"""
        engine = TemplateEngine()
        
        assert engine.markdown_to_html("") == ""
        assert engine.markdown_to_html(None) == ""
    
    def test_clean_html(self):
        """Test HTML cleaning functionality"""
        engine = TemplateEngine()
        
        dirty_html = '<p onclick="alert()">Test</p><script>alert("xss")</script>'
        clean_html = engine._clean_html(dirty_html)
        
        assert 'onclick' not in clean_html
        assert '<script>' not in clean_html
        assert '<p>Test</p>' in clean_html
    
    def test_add_copyright_notice(self):
        """Test copyright notice addition"""
        engine = TemplateEngine()
        
        content = '<p>Test content</p>'
        url = 'https://reddit.com/test'
        
        result = engine._add_copyright_notice(content, url)
        
        assert 'Reddit TOS §5' in result
        assert url in result
        assert 'reddit-copyright' in result
    
    def test_detect_template_type_qa(self):
        """Test Q&A template type detection"""
        engine = TemplateEngine()
        
        qa_post = {
            'title': 'How to learn Python?',
            'content': 'I want to learn Python programming'
        }
        
        template_type = engine._detect_template_type(qa_post)
        assert template_type == TemplateType.QA
    
    def test_detect_template_type_list(self):
        """Test list template type detection"""
        engine = TemplateEngine()
        
        list_post = {
            'title': 'Top 10 Programming Languages',
            'content': '1. Python\n2. JavaScript\n3. Java'
        }
        
        template_type = engine._detect_template_type(list_post)
        assert template_type == TemplateType.LIST
    
    def test_detect_template_type_article(self):
        """Test article template type detection (default)"""
        engine = TemplateEngine()
        
        article_post = {
            'title': 'Technology News',
            'content': 'This is a regular article about technology.'
        }
        
        template_type = engine._detect_template_type(article_post)
        assert template_type == TemplateType.ARTICLE
    
    def test_extract_list_items_numbered(self):
        """Test extracting numbered list items"""
        engine = TemplateEngine()
        
        content = "1. First item\n2. Second item\n3. Third item"
        items = engine._extract_list_items(content)
        
        assert len(items) == 3
        assert "First item" in items
        assert "Second item" in items
        assert "Third item" in items
    
    def test_extract_list_items_bullets(self):
        """Test extracting bullet list items"""
        engine = TemplateEngine()
        
        content = "- First item\n* Second item\n+ Third item"
        items = engine._extract_list_items(content)
        
        assert len(items) == 3
        assert "First item" in items
        assert "Second item" in items
        assert "Third item" in items
    
    def test_extract_list_items_paragraphs(self):
        """Test extracting items from paragraphs"""
        engine = TemplateEngine()
        
        content = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        items = engine._extract_list_items(content)
        
        assert len(items) == 3
        assert "First paragraph." in items
    
    def test_prepare_template_data_basic(self, sample_post_data):
        """Test basic template data preparation"""
        engine = TemplateEngine()
        
        template_data = engine._prepare_template_data(sample_post_data, TemplateType.ARTICLE)
        
        assert template_data['title'] == 'Test Reddit Post'
        assert template_data['subreddit'] == 'technology'
        assert template_data['score'] == 150
        assert template_data['summary_ko'] == '이것은 테스트 게시글입니다.'
        assert '<h1' in template_data['content'] and 'Test Content</h1>' in template_data['content']
        assert template_data['pain_points'] == ['Problem 1', 'Problem 2']
    
    def test_prepare_template_data_list(self, sample_post_data):
        """Test template data preparation for list type"""
        engine = TemplateEngine()
        
        sample_post_data['content'] = "1. First\n2. Second\n3. Third"
        template_data = engine._prepare_template_data(sample_post_data, TemplateType.LIST)
        
        assert 'items' in template_data
        assert len(template_data['items']) == 3
        assert 'First' in template_data['items']
    
    def test_prepare_template_data_qa(self, sample_post_data):
        """Test template data preparation for Q&A type"""
        engine = TemplateEngine()
        
        sample_post_data['top_answers'] = [
            {'content': 'Answer 1', 'score': 10},
            {'content': 'Answer 2', 'score': 5}
        ]
        
        template_data = engine._prepare_template_data(sample_post_data, TemplateType.QA)
        
        assert 'top_answers' in template_data
        assert len(template_data['top_answers']) == 2
        assert '<p>Answer 1</p>' in template_data['top_answers'][0]['content']
    
    def test_prepare_template_data_json_fields(self, sample_post_data):
        """Test handling of JSON string fields"""
        engine = TemplateEngine()
        
        # Test with JSON strings
        sample_post_data['pain_points'] = '["JSON Problem 1", "JSON Problem 2"]'
        sample_post_data['product_ideas'] = '["JSON Idea 1", "JSON Idea 2"]'
        
        template_data = engine._prepare_template_data(sample_post_data, TemplateType.ARTICLE)
        
        assert template_data['pain_points'] == ["JSON Problem 1", "JSON Problem 2"]
        assert template_data['product_ideas'] == ["JSON Idea 1", "JSON Idea 2"]
    
    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_load_templates_success(self, mock_file, mock_exists, mock_templates):
        """Test successful template loading"""
        mock_exists.return_value = True
        
        def mock_open_side_effect(file_path, *args, **kwargs):
            filename = Path(file_path).name
            if filename in mock_templates:
                return mock_open(read_data=mock_templates[filename]).return_value
            return mock_open().return_value
        
        mock_file.side_effect = mock_open_side_effect
        
        engine = TemplateEngine()
        
        assert len(engine._templates) == 3
        assert TemplateType.ARTICLE in engine._templates
        assert TemplateType.LIST in engine._templates
        assert TemplateType.QA in engine._templates
    
    @patch('pathlib.Path.exists')
    def test_load_templates_missing_files(self, mock_exists):
        """Test template loading with missing files"""
        mock_exists.return_value = False
        
        engine = TemplateEngine()
        
        # Should not crash, but templates dict should be empty
        assert len(engine._templates) == 0
    
    @patch.object(TemplateEngine, '_load_templates')
    def test_render_template_fallback(self, mock_load, sample_post_data):
        """Test template rendering with fallback"""
        # Mock empty templates to trigger fallback
        mock_load.return_value = None
        
        engine = TemplateEngine()
        engine._templates = {}  # Empty templates
        
        result = engine.render_template(sample_post_data)
        
        assert 'reddit-fallback' in result
        assert sample_post_data['title'] in result
        assert 'Reddit TOS §5' in result
    
    def test_create_fallback_content(self, sample_post_data):
        """Test fallback content creation"""
        engine = TemplateEngine()
        
        result = engine._create_fallback_content(sample_post_data)
        
        assert sample_post_data['title'] in result
        assert sample_post_data['summary_ko'] in result
        assert 'reddit-fallback' in result
        assert 'Reddit TOS §5' in result
    
    def test_get_available_templates(self):
        """Test getting available templates"""
        engine = TemplateEngine()
        engine._templates = {
            TemplateType.ARTICLE: None,
            TemplateType.LIST: None
        }
        
        available = engine.get_available_templates()
        
        assert 'article' in available
        assert 'list' in available
        assert len(available) == 2
    
    def test_validate_template_data_valid(self, sample_post_data):
        """Test validation with valid data"""
        engine = TemplateEngine()
        
        result = engine.validate_template_data(sample_post_data)
        
        assert len(result['errors']) == 0
        assert len(result['warnings']) == 0
    
    def test_validate_template_data_missing_required(self):
        """Test validation with missing required fields"""
        engine = TemplateEngine()
        
        invalid_data = {'subreddit': 'test'}  # Missing title and url
        result = engine.validate_template_data(invalid_data)
        
        assert len(result['errors']) == 2
        assert any('title' in error for error in result['errors'])
        assert any('url' in error for error in result['errors'])
    
    def test_validate_template_data_missing_recommended(self):
        """Test validation with missing recommended fields"""
        engine = TemplateEngine()
        
        minimal_data = {
            'title': 'Test',
            'url': 'https://reddit.com/test'
        }
        result = engine.validate_template_data(minimal_data)
        
        assert len(result['errors']) == 0
        assert len(result['warnings']) > 0
        assert any('content' in warning for warning in result['warnings'])
    
    def test_validate_template_data_invalid_url(self):
        """Test validation with invalid URL"""
        engine = TemplateEngine()
        
        data = {
            'title': 'Test',
            'url': 'invalid-url'
        }
        result = engine.validate_template_data(data)
        
        assert len(result['warnings']) > 0
        assert any('URL should start with' in warning for warning in result['warnings'])
    
    def test_reload_templates(self):
        """Test template reloading"""
        engine = TemplateEngine()
        original_count = len(engine._templates)
        
        # Mock the reload
        with patch.object(engine, '_load_templates') as mock_load:
            engine.reload_templates()
            mock_load.assert_called_once()


def test_get_template_engine_singleton():
    """Test singleton pattern for template engine"""
    engine1 = get_template_engine()
    engine2 = get_template_engine()
    
    assert engine1 is engine2


class TestTemplateType:
    """Test TemplateType enum"""
    
    def test_template_type_values(self):
        """Test template type enum values"""
        assert TemplateType.ARTICLE.value == "article"
        assert TemplateType.LIST.value == "list"
        assert TemplateType.QA.value == "qa"
    
    def test_template_type_iteration(self):
        """Test iterating over template types"""
        types = list(TemplateType)
        assert len(types) == 3
        assert TemplateType.ARTICLE in types
        assert TemplateType.LIST in types
        assert TemplateType.QA in types