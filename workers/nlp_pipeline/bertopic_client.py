"""
BERTopic client for topic modeling and keyword extraction
"""
import asyncio
import logging
from typing import Dict, Any, List, Tuple, Optional
import pickle
import os
from datetime import datetime, timedelta

import numpy as np
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import CountVectorizer
from umap import UMAP
from hdbscan import HDBSCAN

from app.config import get_settings
from app.redis_client import redis_client

logger = logging.getLogger(__name__)
settings = get_settings()


class BERTopicClient:
    """BERTopic client for topic modeling and keyword extraction"""
    
    def __init__(self):
        self._model: Optional[BERTopic] = None
        self._embedding_model: Optional[SentenceTransformer] = None
        self._is_trained = False
        self._model_path = "models/bertopic_model.pkl"
        self._min_topic_size = 5
        self._n_gram_range = (1, 3)
        self._top_k_words = 10
        
        # Cache settings
        self._cache_ttl = 3600  # 1 hour
        self._topic_cache_prefix = "bertopic_topics"
        self._keyword_cache_prefix = "bertopic_keywords"
    
    async def initialize(self) -> None:
        """Initialize BERTopic model and components"""
        try:
            # Initialize sentence transformer for embeddings
            self._embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            
            # Try to load existing model
            if os.path.exists(self._model_path):
                await self._load_model()
                logger.info("Loaded existing BERTopic model")
            else:
                await self._create_new_model()
                logger.info("Created new BERTopic model")
            
            logger.info("BERTopic client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize BERTopic client: {e}")
            raise
    
    async def _create_new_model(self) -> None:
        """Create a new BERTopic model with optimized settings"""
        try:
            # UMAP for dimensionality reduction
            umap_model = UMAP(
                n_neighbors=15,
                n_components=5,
                min_dist=0.0,
                metric='cosine',
                random_state=42
            )
            
            # HDBSCAN for clustering
            hdbscan_model = HDBSCAN(
                min_cluster_size=self._min_topic_size,
                metric='euclidean',
                cluster_selection_method='eom',
                prediction_data=True
            )
            
            # CountVectorizer for keyword extraction
            vectorizer_model = CountVectorizer(
                ngram_range=self._n_gram_range,
                stop_words="english",
                min_df=2,
                max_features=5000
            )
            
            # Create BERTopic model
            self._model = BERTopic(
                embedding_model=self._embedding_model,
                umap_model=umap_model,
                hdbscan_model=hdbscan_model,
                vectorizer_model=vectorizer_model,
                top_k_words=self._top_k_words,
                language="english",
                calculate_probabilities=True,
                verbose=True
            )
            
            self._is_trained = False
            
        except Exception as e:
            logger.error(f"Failed to create BERTopic model: {e}")
            raise
    
    async def _load_model(self) -> None:
        """Load existing BERTopic model from disk"""
        try:
            with open(self._model_path, 'rb') as f:
                model_data = pickle.load(f)
            
            self._model = model_data['model']
            self._is_trained = model_data.get('is_trained', False)
            
            # Update embedding model reference
            if self._embedding_model:
                self._model.embedding_model = self._embedding_model
            
        except Exception as e:
            logger.error(f"Failed to load BERTopic model: {e}")
            raise
    
    async def _save_model(self) -> None:
        """Save BERTopic model to disk"""
        try:
            # Create models directory if it doesn't exist
            os.makedirs(os.path.dirname(self._model_path), exist_ok=True)
            
            model_data = {
                'model': self._model,
                'is_trained': self._is_trained,
                'saved_at': datetime.utcnow().isoformat()
            }
            
            with open(self._model_path, 'wb') as f:
                pickle.dump(model_data, f)
            
            logger.info(f"BERTopic model saved to {self._model_path}")
            
        except Exception as e:
            logger.error(f"Failed to save BERTopic model: {e}")
    
    async def train_model(self, documents: List[str]) -> Dict[str, Any]:
        """
        Train BERTopic model on a collection of documents
        
        Args:
            documents: List of text documents for training
        
        Returns:
            Dictionary with training results
        """
        try:
            if not self._model:
                await self.initialize()
            
            if len(documents) < self._min_topic_size * 2:
                raise ValueError(f"Need at least {self._min_topic_size * 2} documents for training")
            
            logger.info(f"Training BERTopic model on {len(documents)} documents")
            
            # Fit the model
            topics, probabilities = self._model.fit_transform(documents)
            
            # Get topic information
            topic_info = self._model.get_topic_info()
            
            # Mark as trained and save
            self._is_trained = True
            await self._save_model()
            
            # Clear cache since model has changed
            await self._clear_cache()
            
            training_results = {
                "num_documents": len(documents),
                "num_topics": len(topic_info) - 1,  # Exclude outlier topic (-1)
                "topics_found": topics,
                "topic_info": topic_info.to_dict('records'),
                "training_completed_at": datetime.utcnow().isoformat()
            }
            
            logger.info(
                f"BERTopic training completed: {training_results['num_topics']} topics found",
                extra=training_results
            )
            
            return training_results
            
        except Exception as e:
            logger.error(f"Failed to train BERTopic model: {e}")
            raise
    
    async def extract_topics(
        self, 
        text: str, 
        post_id: str,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Extract topics from a single text document
        
        Args:
            text: Text content to analyze
            post_id: Post ID for caching
            use_cache: Whether to use Redis cache
        
        Returns:
            Dictionary with topic analysis results
        """
        try:
            if not self._model:
                await self.initialize()
            
            # Check cache first
            if use_cache:
                cache_key = f"{self._topic_cache_prefix}:{post_id}"
                cached_result = await redis_client.cache_get(cache_key)
                if cached_result:
                    logger.debug(f"Retrieved topics from cache for post {post_id}")
                    return cached_result
            
            # If model is not trained, we can still get topics but with lower quality
            if not self._is_trained:
                logger.warning("BERTopic model not trained, results may be suboptimal")
            
            # Transform the text
            topics, probabilities = self._model.transform([text])
            topic_id = topics[0]
            topic_prob = probabilities[0] if probabilities is not None else None
            
            # Get topic keywords
            if topic_id != -1:  # Not an outlier
                topic_words = self._model.get_topic(topic_id)
                topic_label = self._model.topic_labels_.get(topic_id, f"Topic {topic_id}")
            else:
                topic_words = []
                topic_label = "Outlier"
            
            # Extract top keywords
            keywords = [word for word, score in topic_words[:5]] if topic_words else []
            
            # Get topic representation
            topic_representation = {
                "topic_id": int(topic_id),
                "topic_label": topic_label,
                "keywords": keywords,
                "probability": float(topic_prob) if topic_prob is not None else None,
                "is_outlier": topic_id == -1
            }
            
            result = {
                "post_id": post_id,
                "topic_representation": topic_representation,
                "extracted_keywords": keywords,
                "confidence_score": float(topic_prob) if topic_prob is not None else 0.0,
                "model_trained": self._is_trained,
                "extracted_at": datetime.utcnow().isoformat()
            }
            
            # Cache the result
            if use_cache:
                cache_key = f"{self._topic_cache_prefix}:{post_id}"
                await redis_client.cache_set(cache_key, result, ttl=self._cache_ttl)
            
            logger.info(
                f"Extracted topics for post {post_id}",
                extra={
                    "post_id": post_id,
                    "topic_id": topic_id,
                    "keywords_count": len(keywords),
                    "confidence": topic_prob
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to extract topics for post {post_id}: {e}")
            raise
    
    async def extract_keywords(
        self, 
        text: str, 
        post_id: str,
        max_keywords: int = 10,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Extract keywords from text using BERTopic's keyword extraction
        
        Args:
            text: Text content to analyze
            post_id: Post ID for caching
            max_keywords: Maximum number of keywords to return
            use_cache: Whether to use Redis cache
        
        Returns:
            Dictionary with keyword extraction results
        """
        try:
            if not self._model:
                await self.initialize()
            
            # Check cache first
            if use_cache:
                cache_key = f"{self._keyword_cache_prefix}:{post_id}"
                cached_result = await redis_client.cache_get(cache_key)
                if cached_result:
                    logger.debug(f"Retrieved keywords from cache for post {post_id}")
                    return cached_result
            
            # Use KeyBERT-style extraction if available
            try:
                # Extract keywords using the model's vectorizer
                if hasattr(self._model, 'vectorizer_model') and self._model.vectorizer_model:
                    # Transform text using the vectorizer
                    vectorizer = self._model.vectorizer_model
                    doc_term_matrix = vectorizer.transform([text])
                    
                    # Get feature names (words)
                    feature_names = vectorizer.get_feature_names_out()
                    
                    # Get word scores
                    word_scores = doc_term_matrix.toarray()[0]
                    
                    # Create word-score pairs and sort
                    word_score_pairs = list(zip(feature_names, word_scores))
                    word_score_pairs = [(word, score) for word, score in word_score_pairs if score > 0]
                    word_score_pairs.sort(key=lambda x: x[1], reverse=True)
                    
                    # Take top keywords
                    top_keywords = word_score_pairs[:max_keywords]
                    
                else:
                    # Fallback: use topic extraction
                    topic_result = await self.extract_topics(text, post_id, use_cache=False)
                    keywords = topic_result.get("extracted_keywords", [])
                    top_keywords = [(kw, 1.0) for kw in keywords[:max_keywords]]
                
            except Exception as e:
                logger.warning(f"Keyword extraction failed, using fallback method: {e}")
                # Simple fallback: split and filter
                words = text.lower().split()
                word_freq = {}
                for word in words:
                    if len(word) > 3 and word.isalpha():
                        word_freq[word] = word_freq.get(word, 0) + 1
                
                top_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:max_keywords]
            
            # Format results
            keywords_list = [{"keyword": word, "score": float(score)} for word, score in top_keywords]
            
            result = {
                "post_id": post_id,
                "keywords": keywords_list,
                "total_keywords": len(keywords_list),
                "extraction_method": "bertopic_vectorizer" if hasattr(self._model, 'vectorizer_model') else "fallback",
                "model_trained": self._is_trained,
                "extracted_at": datetime.utcnow().isoformat()
            }
            
            # Cache the result
            if use_cache:
                cache_key = f"{self._keyword_cache_prefix}:{post_id}"
                await redis_client.cache_set(cache_key, result, ttl=self._cache_ttl)
            
            logger.info(
                f"Extracted keywords for post {post_id}",
                extra={
                    "post_id": post_id,
                    "keywords_count": len(keywords_list),
                    "extraction_method": result["extraction_method"]
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to extract keywords for post {post_id}: {e}")
            raise
    
    async def map_topics_to_tags(
        self, 
        keywords: List[str], 
        max_tags: int = 5
    ) -> List[str]:
        """
        Map BERTopic keywords to Ghost CMS tags
        
        Args:
            keywords: List of keywords from topic extraction
            max_tags: Maximum number of tags to return
        
        Returns:
            List of formatted tags for Ghost CMS
        """
        try:
            if not keywords:
                return []
            
            # Tag mapping rules
            tag_mappings = {
                # Technology
                "ai": "Artificial Intelligence",
                "ml": "Machine Learning", 
                "python": "Python",
                "javascript": "JavaScript",
                "react": "React",
                "api": "API",
                "database": "Database",
                "cloud": "Cloud Computing",
                "aws": "AWS",
                "docker": "Docker",
                
                # Business
                "startup": "Startup",
                "business": "Business",
                "marketing": "Marketing",
                "product": "Product Management",
                "saas": "SaaS",
                "revenue": "Revenue",
                "growth": "Growth",
                
                # Development
                "code": "Programming",
                "development": "Software Development",
                "programming": "Programming",
                "software": "Software",
                "web": "Web Development",
                "mobile": "Mobile Development",
                
                # General
                "problem": "Problem Solving",
                "solution": "Solutions",
                "tool": "Tools",
                "productivity": "Productivity",
                "automation": "Automation"
            }
            
            # Convert keywords to tags
            tags = []
            for keyword in keywords[:max_tags * 2]:  # Get more keywords to filter from
                keyword_lower = keyword.lower().strip()
                
                # Direct mapping
                if keyword_lower in tag_mappings:
                    tag = tag_mappings[keyword_lower]
                    if tag not in tags:
                        tags.append(tag)
                
                # Partial matching
                elif len(keyword_lower) > 3:
                    for key, value in tag_mappings.items():
                        if key in keyword_lower or keyword_lower in key:
                            if value not in tags:
                                tags.append(value)
                            break
                    else:
                        # Use keyword as-is if no mapping found
                        formatted_keyword = keyword.title().replace('_', ' ').replace('-', ' ')
                        if formatted_keyword not in tags and len(formatted_keyword) > 2:
                            tags.append(formatted_keyword)
                
                if len(tags) >= max_tags:
                    break
            
            # Ensure we have at least some tags
            if not tags and keywords:
                tags = [kw.title().replace('_', ' ').replace('-', ' ') for kw in keywords[:max_tags]]
            
            return tags[:max_tags]
            
        except Exception as e:
            logger.error(f"Failed to map topics to tags: {e}")
            return []
    
    async def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current BERTopic model
        
        Returns:
            Dictionary with model information
        """
        try:
            if not self._model:
                return {"status": "not_initialized"}
            
            info = {
                "status": "initialized",
                "is_trained": self._is_trained,
                "model_path": self._model_path,
                "model_exists": os.path.exists(self._model_path),
                "min_topic_size": self._min_topic_size,
                "n_gram_range": self._n_gram_range,
                "top_k_words": self._top_k_words
            }
            
            if self._is_trained:
                try:
                    topic_info = self._model.get_topic_info()
                    info.update({
                        "num_topics": len(topic_info) - 1,  # Exclude outlier topic
                        "total_documents": topic_info['Count'].sum(),
                        "topics_overview": topic_info.head(10).to_dict('records')
                    })
                except Exception as e:
                    logger.warning(f"Could not get detailed model info: {e}")
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to get model info: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _clear_cache(self) -> None:
        """Clear all BERTopic-related cache entries"""
        try:
            # Get all cache keys for topics and keywords
            topic_keys = await redis_client.keys(f"{self._topic_cache_prefix}:*")
            keyword_keys = await redis_client.keys(f"{self._keyword_cache_prefix}:*")
            
            all_keys = topic_keys + keyword_keys
            
            if all_keys:
                await redis_client.delete(*all_keys)
                logger.info(f"Cleared {len(all_keys)} BERTopic cache entries")
            
        except Exception as e:
            logger.error(f"Failed to clear BERTopic cache: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check BERTopic client health status
        
        Returns:
            Dictionary with health information
        """
        try:
            health_info = {
                "status": "healthy",
                "model_initialized": self._model is not None,
                "embedding_model_loaded": self._embedding_model is not None,
                "is_trained": self._is_trained,
                "model_file_exists": os.path.exists(self._model_path)
            }
            
            # Test basic functionality
            if self._model and self._embedding_model:
                try:
                    # Test with a simple document
                    test_result = await self.extract_topics("test document", "health_check", use_cache=False)
                    health_info["basic_functionality"] = True
                    health_info["test_topic_id"] = test_result.get("topic_representation", {}).get("topic_id")
                except Exception as e:
                    health_info["status"] = "degraded"
                    health_info["basic_functionality"] = False
                    health_info["functionality_error"] = str(e)
            else:
                health_info["status"] = "unhealthy"
                health_info["basic_functionality"] = False
            
            return health_info
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "model_initialized": False,
                "basic_functionality": False
            }


# Global BERTopic client instance
bertopic_client = BERTopicClient()


async def init_bertopic_client() -> None:
    """Initialize the global BERTopic client"""
    await bertopic_client.initialize()


def get_bertopic_client() -> BERTopicClient:
    """Get the global BERTopic client instance"""
    return bertopic_client