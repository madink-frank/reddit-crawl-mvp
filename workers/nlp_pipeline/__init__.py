"""
NLP Pipeline service for Reddit Ghost Publisher

This module provides AI-powered content processing including:
- Korean summarization using OpenAI GPT-4o
- Topic modeling and keyword extraction using BERTopic
- Pain point and product idea analysis
- Celery task orchestration for scalable processing
"""

from .openai_client import OpenAIClient, get_openai_client
# BERTopic removed for MVP - using LLM prompts only
from .analysis_engine import (
    AnalysisEngine, 
    AnalysisResult, 
    PainPoint, 
    ProductIdea,
    get_analysis_engine
)
from .tasks import (
    process_content_with_ai,
    batch_process_posts,
    train_bertopic_model,
    health_check_nlp_services,
    trigger_post_processing,
    trigger_batch_processing,
    trigger_model_training,
    get_nlp_task_status
)

__all__ = [
    # Clients
    'OpenAIClient',
    'AnalysisEngine',
    
    # Data classes
    'AnalysisResult',
    'PainPoint',
    'ProductIdea',
    
    # Client getters
    'get_openai_client',
    'get_analysis_engine',
    
    # Initialization functions (OpenAI initializes on first use)
    
    # Celery tasks
    'process_content_with_ai',
    'batch_process_posts',
    'train_bertopic_model',
    'health_check_nlp_services',
    
    # Task utilities
    'trigger_post_processing',
    'trigger_batch_processing', 
    'trigger_model_training',
    'get_nlp_task_status'
]


async def init_nlp_pipeline():
    """Initialize all NLP pipeline components"""
    # OpenAI client initializes on first use (synchronous for MVP)
    # BERTopic removed for MVP - using LLM prompts only
    pass


def get_nlp_pipeline_info():
    """Get information about the NLP pipeline"""
    return {
        "name": "Reddit Ghost Publisher NLP Pipeline",
        "version": "1.0.0",
        "components": [
            "OpenAI GPT-4o Client",
            "BERTopic Topic Modeling",
            "Analysis Engine",
            "Celery Task Processing"
        ],
        "capabilities": [
            "Korean text summarization",
            "Topic modeling and keyword extraction", 
            "Pain point identification",
            "Product idea extraction",
            "Batch processing",
            "Scalable task orchestration"
        ]
    }