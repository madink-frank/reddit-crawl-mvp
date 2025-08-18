"""
Velocity calculation and trend analysis for Reddit posts
"""
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from app.config import get_settings
from app.redis_client import redis_client
from workers.collector.reddit_client import RedditPost

logger = logging.getLogger(__name__)
settings = get_settings()


class TrendDirection(Enum):
    """Trend direction indicators"""
    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"
    EXPLOSIVE = "explosive"
    DECLINING = "declining"


@dataclass
class VelocityMetrics:
    """Velocity and trend metrics for a post"""
    post_id: str
    current_score: int
    current_comments: int
    velocity_score: float  # score/time ratio
    comment_velocity: float  # comments/time ratio
    trend_direction: TrendDirection
    trend_strength: float  # 0-1 scale
    momentum_score: float  # Combined momentum indicator
    predicted_peak_score: Optional[int] = None
    time_to_peak_hours: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'post_id': self.post_id,
            'current_score': self.current_score,
            'current_comments': self.current_comments,
            'velocity_score': self.velocity_score,
            'comment_velocity': self.comment_velocity,
            'trend_direction': self.trend_direction.value,
            'trend_strength': self.trend_strength,
            'momentum_score': self.momentum_score,
            'predicted_peak_score': self.predicted_peak_score,
            'time_to_peak_hours': self.time_to_peak_hours,
            'calculated_at': datetime.utcnow().isoformat()
        }


@dataclass
class HistoricalDataPoint:
    """Historical data point for trend analysis"""
    timestamp: datetime
    score: int
    comments: int
    upvote_ratio: float
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HistoricalDataPoint':
        """Create from dictionary"""
        return cls(
            timestamp=datetime.fromisoformat(data['timestamp']),
            score=data['score'],
            comments=data['comments'],
            upvote_ratio=data['upvote_ratio']
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'score': self.score,
            'comments': self.comments,
            'upvote_ratio': self.upvote_ratio
        }


class VelocityCalculator:
    """Calculate velocity metrics for Reddit posts"""
    
    def __init__(self):
        self.historical_data_ttl = 86400 * 7  # Keep data for 7 days
        self.min_data_points = 3  # Minimum points for trend analysis
    
    async def calculate_velocity(self, post: RedditPost) -> VelocityMetrics:
        """
        Calculate comprehensive velocity metrics for a post
        
        Args:
            post: RedditPost to analyze
        
        Returns:
            VelocityMetrics with calculated values
        """
        try:
            # Store current data point
            await self._store_data_point(post)
            
            # Get historical data
            historical_data = await self._get_historical_data(post.id)
            
            # Calculate basic velocity
            velocity_score = self._calculate_basic_velocity(post)
            comment_velocity = self._calculate_comment_velocity(post)
            
            # Calculate trend if we have enough data
            if len(historical_data) >= self.min_data_points:
                trend_direction, trend_strength = self._calculate_trend(historical_data)
                momentum_score = self._calculate_momentum(historical_data)
                predicted_peak, time_to_peak = self._predict_peak(historical_data, post)
            else:
                trend_direction = TrendDirection.STABLE
                trend_strength = 0.5
                momentum_score = velocity_score / 100  # Normalize to 0-1
                predicted_peak = None
                time_to_peak = None
            
            return VelocityMetrics(
                post_id=post.id,
                current_score=post.score,
                current_comments=post.num_comments,
                velocity_score=velocity_score,
                comment_velocity=comment_velocity,
                trend_direction=trend_direction,
                trend_strength=trend_strength,
                momentum_score=momentum_score,
                predicted_peak_score=predicted_peak,
                time_to_peak_hours=time_to_peak
            )
            
        except Exception as e:
            logger.error(f"Error calculating velocity for post {post.id}: {e}")
            # Return basic metrics on error
            return VelocityMetrics(
                post_id=post.id,
                current_score=post.score,
                current_comments=post.num_comments,
                velocity_score=self._calculate_basic_velocity(post),
                comment_velocity=self._calculate_comment_velocity(post),
                trend_direction=TrendDirection.STABLE,
                trend_strength=0.5,
                momentum_score=0.5
            )
    
    def _calculate_basic_velocity(self, post: RedditPost) -> float:
        """Calculate basic score/time velocity"""
        if post.age_hours <= 0:
            return 0.0
        
        # Use logarithmic scaling to handle very high scores
        normalized_score = math.log(max(post.score, 1))
        velocity = normalized_score / post.age_hours
        
        return round(velocity, 4)
    
    def _calculate_comment_velocity(self, post: RedditPost) -> float:
        """Calculate comment velocity"""
        if post.age_hours <= 0:
            return 0.0
        
        return round(post.num_comments / post.age_hours, 4)
    
    async def _store_data_point(self, post: RedditPost) -> None:
        """Store current data point for historical analysis"""
        try:
            data_point = HistoricalDataPoint(
                timestamp=datetime.utcnow(),
                score=post.score,
                comments=post.num_comments,
                upvote_ratio=post.upvote_ratio
            )
            
            # Store in Redis sorted set with timestamp as score
            key = f"post_history:{post.id}"
            timestamp_score = data_point.timestamp.timestamp()
            
            await redis_client._client.zadd(
                key,
                {data_point.to_dict(): timestamp_score}
            )
            
            # Set expiration
            await redis_client.expire(key, self.historical_data_ttl)
            
            # Keep only recent data points (last 100)
            await redis_client._client.zremrangebyrank(key, 0, -101)
            
        except Exception as e:
            logger.error(f"Error storing data point for post {post.id}: {e}")
    
    async def _get_historical_data(self, post_id: str) -> List[HistoricalDataPoint]:
        """Get historical data points for a post"""
        try:
            key = f"post_history:{post_id}"
            
            # Get all data points sorted by timestamp
            raw_data = await redis_client._client.zrange(key, 0, -1, withscores=True)
            
            historical_data = []
            for data_str, timestamp_score in raw_data:
                try:
                    import json
                    data_dict = json.loads(data_str)
                    historical_data.append(HistoricalDataPoint.from_dict(data_dict))
                except Exception as e:
                    logger.warning(f"Error parsing historical data: {e}")
                    continue
            
            return sorted(historical_data, key=lambda x: x.timestamp)
            
        except Exception as e:
            logger.error(f"Error getting historical data for post {post_id}: {e}")
            return []
    
    def _calculate_trend(self, historical_data: List[HistoricalDataPoint]) -> Tuple[TrendDirection, float]:
        """Calculate trend direction and strength"""
        if len(historical_data) < 2:
            return TrendDirection.STABLE, 0.5
        
        # Calculate score changes over time
        score_changes = []
        comment_changes = []
        
        for i in range(1, len(historical_data)):
            prev_point = historical_data[i-1]
            curr_point = historical_data[i]
            
            time_diff = (curr_point.timestamp - prev_point.timestamp).total_seconds() / 3600
            if time_diff > 0:
                score_change = (curr_point.score - prev_point.score) / time_diff
                comment_change = (curr_point.comments - prev_point.comments) / time_diff
                
                score_changes.append(score_change)
                comment_changes.append(comment_change)
        
        if not score_changes:
            return TrendDirection.STABLE, 0.5
        
        # Calculate average change rates
        avg_score_change = sum(score_changes) / len(score_changes)
        avg_comment_change = sum(comment_changes) / len(comment_changes)
        
        # Determine trend direction
        combined_change = avg_score_change + (avg_comment_change * 2)  # Weight comments more
        
        if combined_change > 50:
            direction = TrendDirection.EXPLOSIVE
            strength = min(combined_change / 100, 1.0)
        elif combined_change > 10:
            direction = TrendDirection.RISING
            strength = min(combined_change / 50, 1.0)
        elif combined_change < -10:
            direction = TrendDirection.DECLINING
            strength = min(abs(combined_change) / 50, 1.0)
        elif combined_change < -2:
            direction = TrendDirection.FALLING
            strength = min(abs(combined_change) / 20, 1.0)
        else:
            direction = TrendDirection.STABLE
            strength = 0.5
        
        return direction, round(strength, 3)
    
    def _calculate_momentum(self, historical_data: List[HistoricalDataPoint]) -> float:
        """Calculate momentum score based on acceleration"""
        if len(historical_data) < 3:
            return 0.5
        
        # Calculate acceleration (change in velocity)
        velocities = []
        
        for i in range(1, len(historical_data)):
            prev_point = historical_data[i-1]
            curr_point = historical_data[i]
            
            time_diff = (curr_point.timestamp - prev_point.timestamp).total_seconds() / 3600
            if time_diff > 0:
                velocity = (curr_point.score - prev_point.score) / time_diff
                velocities.append(velocity)
        
        if len(velocities) < 2:
            return 0.5
        
        # Calculate acceleration
        accelerations = []
        for i in range(1, len(velocities)):
            acceleration = velocities[i] - velocities[i-1]
            accelerations.append(acceleration)
        
        if not accelerations:
            return 0.5
        
        avg_acceleration = sum(accelerations) / len(accelerations)
        
        # Normalize momentum score to 0-1 range
        momentum = 0.5 + (avg_acceleration / 100)  # Adjust scaling as needed
        return max(0.0, min(1.0, momentum))
    
    def _predict_peak(
        self, 
        historical_data: List[HistoricalDataPoint], 
        current_post: RedditPost
    ) -> Tuple[Optional[int], Optional[float]]:
        """Predict peak score and time to reach it"""
        if len(historical_data) < 3:
            return None, None
        
        try:
            # Simple linear regression to predict peak
            # This is a basic implementation - in production you'd want more sophisticated modeling
            
            # Get recent trend
            recent_data = historical_data[-5:]  # Last 5 data points
            
            if len(recent_data) < 2:
                return None, None
            
            # Calculate average growth rate
            total_score_change = recent_data[-1].score - recent_data[0].score
            total_time_hours = (recent_data[-1].timestamp - recent_data[0].timestamp).total_seconds() / 3600
            
            if total_time_hours <= 0:
                return None, None
            
            growth_rate = total_score_change / total_time_hours
            
            # Predict when growth will slow down (simple heuristic)
            # Assume growth slows down after 24-48 hours for most posts
            remaining_peak_time = max(0, 36 - current_post.age_hours)
            
            if growth_rate > 0 and remaining_peak_time > 0:
                predicted_additional_score = growth_rate * remaining_peak_time * 0.5  # Decay factor
                predicted_peak = int(current_post.score + predicted_additional_score)
                
                return predicted_peak, remaining_peak_time
            
            return None, None
            
        except Exception as e:
            logger.error(f"Error predicting peak: {e}")
            return None, None


class TrendAnalyzer:
    """Analyze trends across multiple posts and subreddits"""
    
    def __init__(self):
        self.velocity_calculator = VelocityCalculator()
    
    async def analyze_subreddit_trends(self, subreddit: str, posts: List[RedditPost]) -> Dict[str, Any]:
        """Analyze trends for a subreddit"""
        try:
            if not posts:
                return {"error": "No posts provided"}
            
            # Calculate velocity for all posts
            velocity_metrics = []
            for post in posts:
                metrics = await self.velocity_calculator.calculate_velocity(post)
                velocity_metrics.append(metrics)
            
            # Aggregate statistics
            total_posts = len(velocity_metrics)
            avg_velocity = sum(m.velocity_score for m in velocity_metrics) / total_posts
            avg_momentum = sum(m.momentum_score for m in velocity_metrics) / total_posts
            
            # Count trend directions
            trend_counts = {}
            for direction in TrendDirection:
                count = sum(1 for m in velocity_metrics if m.trend_direction == direction)
                trend_counts[direction.value] = count
            
            # Find top performers
            top_velocity = sorted(velocity_metrics, key=lambda x: x.velocity_score, reverse=True)[:5]
            top_momentum = sorted(velocity_metrics, key=lambda x: x.momentum_score, reverse=True)[:5]
            
            # Calculate subreddit health score
            health_score = self._calculate_subreddit_health(velocity_metrics)
            
            return {
                "subreddit": subreddit,
                "total_posts": total_posts,
                "avg_velocity_score": round(avg_velocity, 4),
                "avg_momentum_score": round(avg_momentum, 4),
                "trend_distribution": trend_counts,
                "health_score": health_score,
                "top_velocity_posts": [
                    {"post_id": m.post_id, "velocity": m.velocity_score} 
                    for m in top_velocity
                ],
                "top_momentum_posts": [
                    {"post_id": m.post_id, "momentum": m.momentum_score} 
                    for m in top_momentum
                ],
                "analyzed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing subreddit trends for {subreddit}: {e}")
            return {"error": str(e)}
    
    def _calculate_subreddit_health(self, velocity_metrics: List[VelocityMetrics]) -> float:
        """Calculate overall health score for a subreddit"""
        if not velocity_metrics:
            return 0.0
        
        # Factors for health score
        avg_velocity = sum(m.velocity_score for m in velocity_metrics) / len(velocity_metrics)
        avg_momentum = sum(m.momentum_score for m in velocity_metrics) / len(velocity_metrics)
        
        # Count positive trends
        positive_trends = sum(
            1 for m in velocity_metrics 
            if m.trend_direction in [TrendDirection.RISING, TrendDirection.EXPLOSIVE]
        )
        positive_ratio = positive_trends / len(velocity_metrics)
        
        # Calculate health score (0-100)
        health_score = (
            (avg_velocity * 10) +  # Velocity component
            (avg_momentum * 30) +  # Momentum component (weighted more)
            (positive_ratio * 60)  # Positive trend ratio (weighted most)
        )
        
        return round(min(100, max(0, health_score)), 2)
    
    async def get_trending_posts(
        self, 
        posts: List[RedditPost], 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get trending posts based on velocity and momentum"""
        try:
            # Calculate metrics for all posts
            post_metrics = []
            for post in posts:
                metrics = await self.velocity_calculator.calculate_velocity(post)
                
                # Calculate trending score
                trending_score = self._calculate_trending_score(metrics, post)
                
                post_metrics.append({
                    "post": post,
                    "metrics": metrics,
                    "trending_score": trending_score
                })
            
            # Sort by trending score
            trending_posts = sorted(
                post_metrics, 
                key=lambda x: x["trending_score"], 
                reverse=True
            )[:limit]
            
            # Format results
            results = []
            for item in trending_posts:
                post = item["post"]
                metrics = item["metrics"]
                
                results.append({
                    "post_id": post.id,
                    "title": post.title,
                    "subreddit": post.subreddit,
                    "score": post.score,
                    "comments": post.num_comments,
                    "age_hours": post.age_hours,
                    "velocity_score": metrics.velocity_score,
                    "momentum_score": metrics.momentum_score,
                    "trend_direction": metrics.trend_direction.value,
                    "trending_score": item["trending_score"],
                    "permalink": post.permalink
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error getting trending posts: {e}")
            return []
    
    def _calculate_trending_score(self, metrics: VelocityMetrics, post: RedditPost) -> float:
        """Calculate overall trending score for ranking"""
        score = 0.0
        
        # Velocity component (30%)
        score += metrics.velocity_score * 0.3
        
        # Momentum component (40%)
        score += metrics.momentum_score * 40
        
        # Trend direction bonus (20%)
        trend_multipliers = {
            TrendDirection.EXPLOSIVE: 2.0,
            TrendDirection.RISING: 1.5,
            TrendDirection.STABLE: 1.0,
            TrendDirection.FALLING: 0.7,
            TrendDirection.DECLINING: 0.3
        }
        score += trend_multipliers.get(metrics.trend_direction, 1.0) * 20
        
        # Recency bonus (10%) - newer posts get slight bonus
        if post.age_hours < 6:
            score += (6 - post.age_hours) * 1.67  # Max 10 points
        
        # Quality indicators
        if post.upvote_ratio > 0.8:
            score += 5
        
        if post.num_comments > post.score * 0.1:  # Good engagement ratio
            score += 3
        
        return round(score, 2)


# Global instances
velocity_calculator = VelocityCalculator()
trend_analyzer = TrendAnalyzer()


def get_velocity_calculator() -> VelocityCalculator:
    """Get velocity calculator instance"""
    return velocity_calculator


def get_trend_analyzer() -> TrendAnalyzer:
    """Get trend analyzer instance"""
    return trend_analyzer