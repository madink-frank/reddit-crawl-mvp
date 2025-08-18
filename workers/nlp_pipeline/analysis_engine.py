"""
Analysis engine for pain points and product ideas extraction
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
import json
from datetime import datetime
from dataclasses import dataclass, asdict

from app.config import get_settings
from app.redis_client import redis_client
from .openai_client import get_openai_client

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class PainPoint:
    """Data class for pain point representation"""
    description: str
    category: str  # 기술적/사용성/비용/시간/기타
    severity: str  # 높음/보통/낮음
    frequency: str  # 자주/가끔/드물게
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PainPoint":
        return cls(**data)


@dataclass
class ProductIdea:
    """Data class for product idea representation"""
    title: str
    description: str
    target_pain_point: str
    feasibility: str  # 높음/보통/낮음
    market_potential: str  # 높음/보통/낮음
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProductIdea":
        return cls(**data)


@dataclass
class AnalysisResult:
    """Data class for complete analysis result"""
    post_id: str
    pain_points: List[PainPoint]
    product_ideas: List[ProductIdea]
    confidence_score: float
    analysis_notes: str
    analyzed_at: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "post_id": self.post_id,
            "pain_points": [pp.to_dict() for pp in self.pain_points],
            "product_ideas": [pi.to_dict() for pi in self.product_ideas],
            "confidence_score": self.confidence_score,
            "analysis_notes": self.analysis_notes,
            "analyzed_at": self.analyzed_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalysisResult":
        pain_points = [PainPoint.from_dict(pp) for pp in data.get("pain_points", [])]
        product_ideas = [ProductIdea.from_dict(pi) for pi in data.get("product_ideas", [])]
        
        return cls(
            post_id=data["post_id"],
            pain_points=pain_points,
            product_ideas=product_ideas,
            confidence_score=data.get("confidence_score", 0.0),
            analysis_notes=data.get("analysis_notes", ""),
            analyzed_at=data.get("analyzed_at", datetime.utcnow().isoformat())
        )


class AnalysisEngine:
    """Engine for extracting pain points and product ideas from Reddit posts"""
    
    def __init__(self):
        self._cache_ttl = 3600  # 1 hour
        self._cache_prefix = "analysis_result"
        
        # Analysis quality thresholds
        self._min_confidence_score = 0.3
        self._max_pain_points = 10
        self._max_product_ideas = 8
        
        # Validation patterns
        self._valid_categories = ["기술적", "사용성", "비용", "시간", "기타"]
        self._valid_severities = ["높음", "보통", "낮음"]
        self._valid_frequencies = ["자주", "가끔", "드물게"]
        self._valid_feasibilities = ["높음", "보통", "낮음"]
        self._valid_market_potentials = ["높음", "보통", "낮음"]
    
    async def analyze_post(
        self, 
        post_title: str, 
        post_content: str, 
        post_id: str,
        use_cache: bool = True
    ) -> AnalysisResult:
        """
        Analyze Reddit post for pain points and product ideas
        
        Args:
            post_title: Reddit post title
            post_content: Reddit post content
            post_id: Post ID for tracking and caching
            use_cache: Whether to use Redis cache
        
        Returns:
            AnalysisResult with extracted pain points and product ideas
        """
        try:
            # Check cache first
            if use_cache:
                cache_key = f"{self._cache_prefix}:{post_id}"
                cached_result = await redis_client.cache_get(cache_key)
                if cached_result:
                    logger.debug(f"Retrieved analysis from cache for post {post_id}")
                    return AnalysisResult.from_dict(cached_result)
            
            # Get OpenAI client
            openai_client = get_openai_client()
            
            # Perform analysis using OpenAI
            analysis_response = await openai_client.analyze_pain_points_and_ideas(
                post_title=post_title,
                post_content=post_content,
                post_id=post_id,
                max_tokens=800
            )
            
            # Extract and validate analysis data
            raw_analysis = analysis_response.get("analysis", {})
            validated_result = await self._validate_and_clean_analysis(raw_analysis, post_id)
            
            # Create analysis result
            result = AnalysisResult(
                post_id=post_id,
                pain_points=validated_result["pain_points"],
                product_ideas=validated_result["product_ideas"],
                confidence_score=validated_result["confidence_score"],
                analysis_notes=validated_result["analysis_notes"],
                analyzed_at=datetime.utcnow().isoformat()
            )
            
            # Cache the result
            if use_cache:
                cache_key = f"{self._cache_prefix}:{post_id}"
                await redis_client.cache_set(cache_key, result.to_dict(), ttl=self._cache_ttl)
            
            logger.info(
                f"Analyzed post {post_id}",
                extra={
                    "post_id": post_id,
                    "pain_points_count": len(result.pain_points),
                    "product_ideas_count": len(result.product_ideas),
                    "confidence_score": result.confidence_score,
                    "token_usage": analysis_response.get("total_tokens", 0)
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to analyze post {post_id}: {e}")
            raise
    
    async def _validate_and_clean_analysis(
        self, 
        raw_analysis: Dict[str, Any], 
        post_id: str
    ) -> Dict[str, Any]:
        """
        Validate and clean raw analysis data from OpenAI
        
        Args:
            raw_analysis: Raw analysis data from OpenAI
            post_id: Post ID for logging
        
        Returns:
            Cleaned and validated analysis data
        """
        try:
            validated_data = {
                "pain_points": [],
                "product_ideas": [],
                "confidence_score": 0.0,
                "analysis_notes": ""
            }
            
            # Validate pain points
            raw_pain_points = raw_analysis.get("pain_points", [])
            if isinstance(raw_pain_points, list):
                for pp_data in raw_pain_points[:self._max_pain_points]:
                    if isinstance(pp_data, dict):
                        pain_point = self._validate_pain_point(pp_data)
                        if pain_point:
                            validated_data["pain_points"].append(pain_point)
            
            # Validate product ideas
            raw_product_ideas = raw_analysis.get("product_ideas", [])
            if isinstance(raw_product_ideas, list):
                for pi_data in raw_product_ideas[:self._max_product_ideas]:
                    if isinstance(pi_data, dict):
                        product_idea = self._validate_product_idea(pi_data)
                        if product_idea:
                            validated_data["product_ideas"].append(product_idea)
            
            # Validate confidence score
            confidence = raw_analysis.get("confidence_score", 0.0)
            if isinstance(confidence, (int, float)) and 0.0 <= confidence <= 1.0:
                validated_data["confidence_score"] = float(confidence)
            else:
                # Calculate confidence based on number of valid items found
                total_items = len(validated_data["pain_points"]) + len(validated_data["product_ideas"])
                validated_data["confidence_score"] = min(total_items * 0.1, 1.0)
            
            # Validate analysis notes
            notes = raw_analysis.get("analysis_notes", "")
            if isinstance(notes, str) and len(notes.strip()) > 0:
                validated_data["analysis_notes"] = notes.strip()[:500]  # Limit length
            else:
                validated_data["analysis_notes"] = f"Analysis completed for post {post_id}"
            
            # Quality check
            if validated_data["confidence_score"] < self._min_confidence_score:
                logger.warning(
                    f"Low confidence analysis for post {post_id}: {validated_data['confidence_score']}"
                )
            
            return validated_data
            
        except Exception as e:
            logger.error(f"Failed to validate analysis for post {post_id}: {e}")
            # Return minimal valid structure
            return {
                "pain_points": [],
                "product_ideas": [],
                "confidence_score": 0.0,
                "analysis_notes": f"Analysis validation failed: {str(e)}"
            }
    
    def _validate_pain_point(self, pp_data: Dict[str, Any]) -> Optional[PainPoint]:
        """Validate and create PainPoint from raw data"""
        try:
            # Required fields
            description = pp_data.get("description", "").strip()
            if not description or len(description) < 10:
                return None
            
            # Validate category
            category = pp_data.get("category", "기타").strip()
            if category not in self._valid_categories:
                category = "기타"
            
            # Validate severity
            severity = pp_data.get("severity", "보통").strip()
            if severity not in self._valid_severities:
                severity = "보통"
            
            # Validate frequency
            frequency = pp_data.get("frequency", "가끔").strip()
            if frequency not in self._valid_frequencies:
                frequency = "가끔"
            
            # Calculate confidence based on data quality
            confidence = 0.8  # Base confidence
            if len(description) > 50:
                confidence += 0.1
            if category != "기타":
                confidence += 0.1
            
            return PainPoint(
                description=description[:200],  # Limit length
                category=category,
                severity=severity,
                frequency=frequency,
                confidence=min(confidence, 1.0)
            )
            
        except Exception as e:
            logger.warning(f"Failed to validate pain point: {e}")
            return None
    
    def _validate_product_idea(self, pi_data: Dict[str, Any]) -> Optional[ProductIdea]:
        """Validate and create ProductIdea from raw data"""
        try:
            # Required fields
            title = pi_data.get("title", "").strip()
            description = pi_data.get("description", "").strip()
            target_pain_point = pi_data.get("target_pain_point", "").strip()
            
            if not title or len(title) < 5:
                return None
            if not description or len(description) < 10:
                return None
            
            # Validate feasibility
            feasibility = pi_data.get("feasibility", "보통").strip()
            if feasibility not in self._valid_feasibilities:
                feasibility = "보통"
            
            # Validate market potential
            market_potential = pi_data.get("market_potential", "보통").strip()
            if market_potential not in self._valid_market_potentials:
                market_potential = "보통"
            
            # Calculate confidence based on data quality
            confidence = 0.7  # Base confidence
            if len(description) > 50:
                confidence += 0.1
            if len(target_pain_point) > 10:
                confidence += 0.1
            if feasibility == "높음" or market_potential == "높음":
                confidence += 0.1
            
            return ProductIdea(
                title=title[:100],  # Limit length
                description=description[:300],  # Limit length
                target_pain_point=target_pain_point[:200],  # Limit length
                feasibility=feasibility,
                market_potential=market_potential,
                confidence=min(confidence, 1.0)
            )
            
        except Exception as e:
            logger.warning(f"Failed to validate product idea: {e}")
            return None
    
    async def batch_analyze_posts(
        self, 
        posts: List[Dict[str, str]], 
        max_concurrent: int = 3
    ) -> List[AnalysisResult]:
        """
        Analyze multiple posts concurrently
        
        Args:
            posts: List of post dictionaries with 'id', 'title', 'content'
            max_concurrent: Maximum concurrent analyses
        
        Returns:
            List of AnalysisResult objects
        """
        try:
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def analyze_single_post(post_data: Dict[str, str]) -> Optional[AnalysisResult]:
                async with semaphore:
                    try:
                        return await self.analyze_post(
                            post_title=post_data["title"],
                            post_content=post_data["content"],
                            post_id=post_data["id"]
                        )
                    except Exception as e:
                        logger.error(f"Failed to analyze post {post_data['id']}: {e}")
                        return None
            
            # Create tasks for all posts
            tasks = [analyze_single_post(post) for post in posts]
            
            # Execute all tasks
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out None results and exceptions
            valid_results = []
            for result in results:
                if isinstance(result, AnalysisResult):
                    valid_results.append(result)
                elif isinstance(result, Exception):
                    logger.error(f"Batch analysis exception: {result}")
            
            logger.info(
                f"Batch analysis completed: {len(valid_results)}/{len(posts)} successful",
                extra={
                    "total_posts": len(posts),
                    "successful_analyses": len(valid_results),
                    "failed_analyses": len(posts) - len(valid_results)
                }
            )
            
            return valid_results
            
        except Exception as e:
            logger.error(f"Failed to perform batch analysis: {e}")
            return []
    
    async def get_analysis_statistics(self, days: int = 7) -> Dict[str, Any]:
        """
        Get analysis statistics for the last N days
        
        Args:
            days: Number of days to look back
        
        Returns:
            Dictionary with analysis statistics
        """
        try:
            # This would typically query the database for actual statistics
            # For now, we'll return a placeholder structure
            stats = {
                "total_analyses": 0,
                "avg_pain_points_per_post": 0.0,
                "avg_product_ideas_per_post": 0.0,
                "avg_confidence_score": 0.0,
                "category_distribution": {},
                "severity_distribution": {},
                "feasibility_distribution": {},
                "period_days": days
            }
            
            # In a real implementation, this would query the database
            # and calculate actual statistics from stored AnalysisResult data
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get analysis statistics: {e}")
            return {}
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check analysis engine health status
        
        Returns:
            Dictionary with health information
        """
        try:
            # Test basic functionality
            test_result = await self.analyze_post(
                post_title="Test Post",
                post_content="This is a test post to check if the analysis engine is working properly.",
                post_id="health_check_test",
                use_cache=False
            )
            
            return {
                "status": "healthy",
                "basic_functionality": True,
                "test_analysis_completed": True,
                "test_pain_points_count": len(test_result.pain_points),
                "test_product_ideas_count": len(test_result.product_ideas),
                "test_confidence_score": test_result.confidence_score,
                "cache_enabled": True,
                "validation_rules_loaded": True
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "basic_functionality": False,
                "test_analysis_completed": False
            }


# Global analysis engine instance
analysis_engine = AnalysisEngine()


def get_analysis_engine() -> AnalysisEngine:
    """Get the global analysis engine instance"""
    return analysis_engine