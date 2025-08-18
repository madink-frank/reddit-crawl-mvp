"""
Unit tests for Metadata Processor
"""

import pytest
import json
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta

from workers.publisher.metadata_processor import (
    MetadataProcessor,
    get_metadata_processor
)


class TestMetadataProcessor:
    """Test MetadataProcessor functionality"""
    
    @pytest.fixture
    def mock_ghost_client(self):
        """Mock Ghost client"""
        client = AsyncMock()
        client.get_tags.return_value = [
            {'id': '1', 'name': 'technology'},
            {'id': '2', 'name': 'programming'},
            {'id': '3', 'name': 'ai'}
        ]
        client.create_tag.return_value = {'id': '4', 'name': 'new-tag'}
        return client
    
    @pytest.fixture
    def metadata_processor(self, mock_ghost_client):
        """Create MetadataProcessor with mocked dependencies"""
        return MetadataProcessor(ghost_client=mock_ghost_client)
    
    @pytest.fixture
    def sample_post_data(self):
        """Sample post data for testing"""
        return {
            'title': 'Amazing AI Breakthrough in Machine Learning',
            'content': 'This is about #AI and #MachineLearning with Python programming.',
            'summary_ko': '인공지능과 머신러닝의 놀라운 발전에 대한 내용입니다.',
            'subreddit': 'MachineLearning',
            'topic_tag': 'artificial intelligence, neural networks, deep learning',
            'url': 'https://reddit.com/r/MachineLearning/test',
            'feature_image': 'https://cdn.ghost.io/feature.jpg'
        }
    
    def test_normalize_tag_basic(self, metadata_processor):
        """Test basic tag normalization"""
        assert metadata_processor.normalize_tag('machine learning') == 'ml'
        assert metadata_processor.normalize_tag('artificial intelligence') == 'ai'
        assert metadata_processor.normalize_tag('user experience') == 'ux'
        assert metadata_processor.normalize_tag('API Development') == 'api-development'
    
    def test_normalize_tag_special_chars(self, metadata_processor):
        """Test tag normalization with special characters"""
        assert metadata_processor.normalize_tag('C++') == 'c'
        assert metadata_processor.normalize_tag('Node.js') == 'nodejs'
        assert metadata_processor.normalize_tag('React/Redux') == 'reactredux'
        assert metadata_processor.normalize_tag('  Web   Development  ') == 'web-development'
    
    def test_normalize_tag_korean(self, metadata_processor):
        """Test Korean tag normalization"""
        assert metadata_processor.normalize_tag('기술') == 'technology'
        assert metadata_processor.normalize_tag('인공지능') == 'ai'
        assert metadata_processor.normalize_tag('프로그래밍') == 'programming'
    
    def test_normalize_tag_empty(self, metadata_processor):
        """Test normalization with empty/invalid input"""
        assert metadata_processor.normalize_tag('') == ''
        assert metadata_processor.normalize_tag('   ') == ''
        assert metadata_processor.normalize_tag('!@#$%') == ''
    
    def test_extract_tags_from_bertopic_list(self, metadata_processor):
        """Test extracting tags from BERTopic list format"""
        keywords = ['machine learning', 'artificial intelligence', 'neural networks']
        tags = metadata_processor.extract_tags_from_bertopic(keywords)
        
        assert 'ml' in tags
        assert 'ai' in tags
        assert 'neural-networks' in tags
    
    def test_extract_tags_from_bertopic_dict_format(self, metadata_processor):
        """Test extracting tags from BERTopic dictionary format"""
        keywords = [
            {'word': 'machine learning', 'score': 0.8},
            {'word': 'python', 'score': 0.6},
            {'word': 'data science', 'score': 0.4}
        ]
        tags = metadata_processor.extract_tags_from_bertopic(keywords)
        
        assert 'ml' in tags
        assert 'python' in tags
        assert 'data-science' in tags
    
    def test_extract_tags_from_bertopic_json_string(self, metadata_processor):
        """Test extracting tags from JSON string"""
        keywords = '["artificial intelligence", "deep learning", "tensorflow"]'
        tags = metadata_processor.extract_tags_from_bertopic(keywords)
        
        assert 'ai' in tags
        assert 'deep-learning' in tags
        assert 'tensorflow' in tags
    
    def test_extract_tags_from_bertopic_comma_string(self, metadata_processor):
        """Test extracting tags from comma-separated string"""
        keywords = 'machine learning, python, data analysis'
        tags = metadata_processor.extract_tags_from_bertopic(keywords)
        
        assert 'ml' in tags
        assert 'python' in tags
        assert 'data-analysis' in tags
    
    def test_extract_tags_from_bertopic_empty(self, metadata_processor):
        """Test extracting tags from empty input"""
        assert metadata_processor.extract_tags_from_bertopic(None) == []
        assert metadata_processor.extract_tags_from_bertopic('') == []
        assert metadata_processor.extract_tags_from_bertopic([]) == []
    
    def test_extract_tags_from_subreddit(self, metadata_processor):
        """Test extracting tags from subreddit"""
        tags = metadata_processor.extract_tags_from_subreddit('MachineLearning')
        
        assert 'machinelearning' in tags
        assert 'ml' in tags
        assert 'ai' in tags
    
    def test_extract_tags_from_subreddit_with_prefix(self, metadata_processor):
        """Test extracting tags from subreddit with r/ prefix"""
        tags = metadata_processor.extract_tags_from_subreddit('r/programming')
        
        assert 'programming' in tags
        assert 'coding' in tags
        assert 'dev' in tags
    
    def test_extract_tags_from_subreddit_common_mappings(self, metadata_processor):
        """Test subreddit to tag mappings"""
        test_cases = [
            ('technology', ['technology', 'tech']),
            ('webdev', ['webdev', 'web', 'development']),
            ('javascript', ['javascript', 'js', 'programming']),
            ('startups', ['startups', 'startup', 'business'])
        ]
        
        for subreddit, expected_tags in test_cases:
            tags = metadata_processor.extract_tags_from_subreddit(subreddit)
            for expected_tag in expected_tags:
                assert expected_tag in tags
    
    def test_extract_tags_from_content(self, metadata_processor):
        """Test extracting tags from content"""
        title = "Learning Python for Machine Learning"
        content = "This post discusses #AI and #MachineLearning using Python and TensorFlow."
        
        tags = metadata_processor.extract_tags_from_content(title, content)
        
        assert 'ai' in tags
        assert 'machinelearning' in tags
        assert 'python' in tags
    
    def test_extract_tags_from_content_tech_terms(self, metadata_processor):
        """Test extracting tech terms from content"""
        title = "Building APIs with Node.js"
        content = "Using React, MongoDB, and Docker for development."
        
        tags = metadata_processor.extract_tags_from_content(title, content)
        
        assert 'nodejs' in tags or 'node-js' in tags
        assert 'react' in tags
        assert 'mongodb' in tags
        assert 'docker' in tags
    
    @pytest.mark.asyncio
    async def test_get_existing_ghost_tags(self, metadata_processor):
        """Test fetching existing Ghost tags"""
        tags = await metadata_processor.get_existing_ghost_tags()
        
        assert 'technology' in tags
        assert 'programming' in tags
        assert 'ai' in tags
        assert tags['technology'] == '1'
    
    @pytest.mark.asyncio
    async def test_get_existing_ghost_tags_caching(self, metadata_processor):
        """Test Ghost tags caching"""
        # First call
        tags1 = await metadata_processor.get_existing_ghost_tags()
        
        # Second call should use cache
        tags2 = await metadata_processor.get_existing_ghost_tags()
        
        assert tags1 == tags2
        # Ghost client should only be called once
        metadata_processor.ghost_client.get_tags.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_existing_ghost_tags_no_client(self):
        """Test fetching tags without Ghost client"""
        processor = MetadataProcessor(ghost_client=None)
        tags = await processor.get_existing_ghost_tags()
        
        assert tags == {}
    
    @pytest.mark.asyncio
    async def test_create_missing_tags(self, metadata_processor):
        """Test creating missing tags in Ghost"""
        tag_names = ['new-tag', 'technology', 'another-new-tag']
        
        created_tags = await metadata_processor.create_missing_tags(tag_names)
        
        # Should create tags that don't exist
        assert 'new-tag' in created_tags
        assert 'another-new-tag' in created_tags
        # Should not create existing tags
        assert 'technology' not in created_tags
    
    @pytest.mark.asyncio
    async def test_create_missing_tags_api_error(self, metadata_processor):
        """Test handling API errors when creating tags"""
        from workers.publisher.ghost_client import GhostAPIError
        
        metadata_processor.ghost_client.create_tag.side_effect = GhostAPIError("API Error")
        
        created_tags = await metadata_processor.create_missing_tags(['failing-tag'])
        
        assert created_tags == {}
    
    @pytest.mark.asyncio
    async def test_map_tags_to_ghost(self, metadata_processor, sample_post_data):
        """Test mapping various tag sources to Ghost tags"""
        tag_sources = {
            'bertopic_keywords': 'machine learning, python',
            'subreddit': 'MachineLearning',
            'title': sample_post_data['title'],
            'content': sample_post_data['content']
        }
        
        tags = await metadata_processor.map_tags_to_ghost(tag_sources)
        
        assert len(tags) > 0
        assert any('ml' in tag or 'machinelearning' in tag for tag in tags)
        assert 'python' in tags
    
    def test_generate_seo_metadata(self, metadata_processor, sample_post_data):
        """Test SEO metadata generation"""
        seo_metadata = metadata_processor.generate_seo_metadata(sample_post_data)
        
        assert 'meta_title' in seo_metadata
        assert 'meta_description' in seo_metadata
        
        # Check length constraints
        assert len(seo_metadata['meta_title']) <= 60
        assert len(seo_metadata['meta_description']) <= 160
        
        # Should include subreddit in title if space allows
        title_with_subreddit = f"{sample_post_data['title']} | r/MachineLearning"
        if len(title_with_subreddit) <= 60:
            assert 'MachineLearning' in seo_metadata['meta_title']
    
    def test_generate_seo_metadata_long_title(self, metadata_processor):
        """Test SEO metadata with very long title"""
        long_post = {
            'title': 'This is a very long title that exceeds the recommended length for SEO meta titles and should be truncated',
            'summary_ko': 'Short summary',
            'subreddit': 'test'
        }
        
        seo_metadata = metadata_processor.generate_seo_metadata(long_post)
        
        assert len(seo_metadata['meta_title']) <= 60
        assert seo_metadata['meta_title'].endswith('...')
    
    def test_generate_social_metadata(self, metadata_processor, sample_post_data):
        """Test social media metadata generation"""
        feature_image = 'https://cdn.ghost.io/feature.jpg'
        social_metadata = metadata_processor.generate_social_metadata(sample_post_data, feature_image)
        
        required_fields = ['og_title', 'og_description', 'twitter_title', 'twitter_description']
        for field in required_fields:
            assert field in social_metadata
        
        # Check length constraints
        assert len(social_metadata['og_title']) <= 95
        assert len(social_metadata['twitter_title']) <= 70
        assert len(social_metadata['twitter_description']) <= 200
        
        # Should include image
        assert social_metadata['og_image'] == feature_image
        assert social_metadata['twitter_image'] == feature_image
    
    def test_generate_social_metadata_no_image(self, metadata_processor, sample_post_data):
        """Test social metadata without feature image"""
        social_metadata = metadata_processor.generate_social_metadata(sample_post_data)
        
        assert 'og_image' not in social_metadata
        assert 'twitter_image' not in social_metadata
    
    def test_generate_activitypub_metadata(self, metadata_processor, sample_post_data):
        """Test ActivityPub metadata generation"""
        activitypub_metadata = metadata_processor.generate_activitypub_metadata(sample_post_data)
        
        assert 'activitypub_content' in activitypub_metadata
        assert 'hashtags' in activitypub_metadata
        assert 'visibility' in activitypub_metadata
        assert 'language' in activitypub_metadata
        
        # Check content includes key elements
        content = activitypub_metadata['activitypub_content']
        assert sample_post_data['title'] in content
        assert 'r/MachineLearning' in content
        
        # Check hashtags
        hashtags = activitypub_metadata['hashtags']
        assert '#MachineLearning' in hashtags
        assert '#Reddit' in hashtags
        
        # Check length constraint
        assert len(content) <= 500
    
    def test_generate_activitypub_metadata_long_content(self, metadata_processor):
        """Test ActivityPub metadata with very long content"""
        long_post = {
            'title': 'Very Long Title ' * 20,  # Make it very long
            'summary_ko': 'Very long summary ' * 30,
            'subreddit': 'test',
            'url': 'https://reddit.com/test'
        }
        
        activitypub_metadata = metadata_processor.generate_activitypub_metadata(long_post)
        
        assert len(activitypub_metadata['activitypub_content']) <= 500
        assert activitypub_metadata['activitypub_content'].endswith('...')
    
    @pytest.mark.asyncio
    async def test_process_post_metadata(self, metadata_processor, sample_post_data):
        """Test complete metadata processing"""
        processed_metadata = await metadata_processor.process_post_metadata(sample_post_data)
        
        # Should contain all metadata types
        assert 'tags' in processed_metadata
        assert 'meta_title' in processed_metadata
        assert 'meta_description' in processed_metadata
        assert 'og_title' in processed_metadata
        assert 'twitter_title' in processed_metadata
        assert 'activitypub' in processed_metadata
        
        # Tags should be populated
        assert len(processed_metadata['tags']) > 0
        
        # ActivityPub should be a dict
        assert isinstance(processed_metadata['activitypub'], dict)
    
    def test_validate_metadata_valid(self, metadata_processor):
        """Test validation with valid metadata"""
        valid_metadata = {
            'tags': ['ai', 'ml', 'python'],
            'meta_title': 'Good Title',
            'meta_description': 'This is a good meta description that is not too long or too short.',
            'og_title': 'Good OG Title',
            'twitter_title': 'Good Twitter Title'
        }
        
        result = metadata_processor.validate_metadata(valid_metadata)
        
        assert len(result['errors']) == 0
        assert len(result['warnings']) == 0
    
    def test_validate_metadata_errors(self, metadata_processor):
        """Test validation with invalid metadata"""
        invalid_metadata = {
            'tags': ['tag'] * 15,  # Too many tags
            'meta_title': 'This is a very long meta title that exceeds the recommended 60 character limit',
            'meta_description': 'Short',  # Too short
            'og_title': 'This is a very long Open Graph title that exceeds the Facebook recommended limit of 95 characters',
            'twitter_title': 'This is a very long Twitter title that exceeds the recommended 70 character limit'
        }
        
        result = metadata_processor.validate_metadata(invalid_metadata)
        
        assert len(result['errors']) > 0
        assert len(result['warnings']) > 0
        
        # Check specific errors
        errors = ' '.join(result['errors'])
        assert 'Meta title too long' in errors
        assert 'Open Graph title too long' in errors
        assert 'Twitter title too long' in errors
    
    def test_validate_metadata_no_tags(self, metadata_processor):
        """Test validation with no tags"""
        metadata = {
            'tags': [],
            'meta_title': 'Good Title',
            'meta_description': 'Good description that meets length requirements.'
        }
        
        result = metadata_processor.validate_metadata(metadata)
        
        assert len(result['errors']) == 0
        assert any('No tags generated' in warning for warning in result['warnings'])


@pytest.mark.asyncio
async def test_get_metadata_processor_singleton():
    """Test singleton pattern for metadata processor"""
    processor1 = await get_metadata_processor()
    processor2 = await get_metadata_processor()
    
    assert processor1 is processor2


@pytest.mark.asyncio
async def test_get_metadata_processor_with_client():
    """Test getting metadata processor with Ghost client"""
    mock_client = AsyncMock()
    
    # Reset singleton
    import workers.publisher.metadata_processor
    workers.publisher.metadata_processor._metadata_processor = None
    
    processor = await get_metadata_processor(mock_client)
    
    assert processor.ghost_client is mock_client