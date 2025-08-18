"""
OpenAI GPT-4o-mini/GPT-4o client for Reddit Ghost Publisher MVP
Simplified implementation with fallback support and cost tracking
"""
import logging
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
import json
import os

import openai
from openai import OpenAI
from openai.types.chat import ChatCompletion

from app.config import get_settings
from app.redis_client import redis_client

logger = logging.getLogger(__name__)
settings = get_settings()


class OpenAIClient:
    """Simplified OpenAI client with GPT-4o-mini primary and GPT-4o fallback"""
    
    # Internal cost map (per 1K tokens)
    COST_PER_1K_TOKENS = {
        'gpt-4o-mini': Decimal('0.00015'),  # $0.15/1M input tokens
        'gpt-4o': Decimal('0.005')          # $5.00/1M input tokens  
    }
    
    def __init__(self):
        self._client: Optional[OpenAI] = None
        self._api_key = os.getenv('OPENAI_API_KEY')
        self._daily_token_limit = int(os.getenv('OPENAI_DAILY_TOKENS_LIMIT', '100000'))
        
        # Model configuration: primary + fallback
        self._primary_model = 'gpt-4o-mini'
        self._fallback_model = 'gpt-4o'
    
    def initialize(self) -> None:
        """Initialize OpenAI client (synchronous for MVP)"""
        if not self._api_key:
            raise ValueError("OpenAI API key not found in environment variables")
        
        self._client = OpenAI(api_key=self._api_key)
        logger.info("OpenAI client initialized successfully")
    
    def check_daily_token_usage(self) -> Tuple[int, bool]:
        """
        Check daily token usage against limit with 80%/100% alerts
        
        Returns:
            Tuple of (current_usage, is_over_limit)
        """
        try:
            today = datetime.utcnow().strftime("%Y%m%d")
            cache_key = f"usage:{today}"
            
            current_usage = redis_client.get(cache_key)
            current_usage = int(current_usage) if current_usage else 0
            
            # Check for alert thresholds
            usage_percentage = (current_usage / self._daily_token_limit) * 100
            
            # 80% threshold alert
            if usage_percentage >= 80 and not self._has_sent_alert(today, "80"):
                self._send_token_budget_alert(current_usage, self._daily_token_limit, "80%")
                self._mark_alert_sent(today, "80")
            
            # 100% threshold alert
            is_over_limit = current_usage >= self._daily_token_limit
            if is_over_limit and not self._has_sent_alert(today, "100"):
                self._send_token_budget_alert(current_usage, self._daily_token_limit, "100%")
                self._mark_alert_sent(today, "100")
            
            return current_usage, is_over_limit
            
        except Exception as e:
            logger.error(f"Failed to check daily token usage: {e}")
            return 0, False
    
    def _has_sent_alert(self, date: str, threshold: str) -> bool:
        """Check if alert has been sent for this date and threshold"""
        try:
            alert_key = f"alert_sent:{date}:{threshold}"
            return redis_client.exists(alert_key)
        except Exception:
            return False
    
    def _mark_alert_sent(self, date: str, threshold: str) -> None:
        """Mark alert as sent for this date and threshold"""
        try:
            alert_key = f"alert_sent:{date}:{threshold}"
            redis_client.setex(alert_key, 86400, "1")  # Expire in 24 hours
        except Exception as e:
            logger.error(f"Failed to mark alert as sent: {e}")
    
    def _send_token_budget_alert(self, current_usage: int, limit: int, threshold: str) -> None:
        """Send Slack alert for token budget threshold"""
        try:
            import requests
            
            slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')
            if not slack_webhook_url:
                logger.warning("SLACK_WEBHOOK_URL not configured, skipping alert")
                return
            
            usage_percentage = (current_usage / limit) * 100
            
            payload = {
                "text": f"🚨 [HIGH] OpenAI Token Budget Alert",
                "attachments": [
                    {
                        "color": "danger" if threshold == "100%" else "warning",
                        "fields": [
                            {"title": "Service", "value": "OpenAI API", "short": True},
                            {"title": "Threshold", "value": threshold, "short": True},
                            {"title": "Current Usage", "value": f"{current_usage:,} tokens", "short": True},
                            {"title": "Daily Limit", "value": f"{limit:,} tokens", "short": True},
                            {"title": "Usage %", "value": f"{usage_percentage:.1f}%", "short": True},
                            {"title": "Status", "value": "BLOCKED" if threshold == "100%" else "WARNING", "short": True}
                        ]
                    }
                ]
            }
            
            response = requests.post(slack_webhook_url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info(f"Token budget alert sent for {threshold} threshold")
            else:
                logger.error(f"Failed to send Slack alert: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Failed to send token budget alert: {e}")
    
    def _update_token_usage(self, tokens_used: int) -> None:
        """Update daily token usage counter with UTC 00:00 auto reset"""
        try:
            today = datetime.utcnow().strftime("%Y%m%d")
            cache_key = f"usage:{today}"
            
            # Increment counter
            redis_client.incr(cache_key, tokens_used)
            
            # Set expiry to end of day UTC if key is new
            ttl = redis_client.ttl(cache_key)
            if ttl == -1:  # Key exists but no expiry set
                tomorrow = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                seconds_until_tomorrow = int((tomorrow - datetime.utcnow()).total_seconds())
                redis_client.expire(cache_key, seconds_until_tomorrow)
            
        except Exception as e:
            logger.error(f"Failed to update token usage: {e}")
    
    def _calculate_cost(self, total_tokens: int, model: str) -> Decimal:
        """Calculate cost using internal cost map"""
        cost_per_1k = self.COST_PER_1K_TOKENS.get(model, Decimal('0.001'))
        return (Decimal(total_tokens) / 1000) * cost_per_1k
    
    def _get_korean_summary_prompt(self, title: str, content: str) -> str:
        """Generate Korean summary prompt template"""
        return f"""다음 Reddit 게시글을 한국어로 요약해주세요:

제목: {title}

내용:
{content}

요약 요구사항:
1. 핵심 내용을 3-5문장으로 간결하게 요약
2. 자연스러운 한국어로 작성
3. 원문의 맥락과 톤을 유지
4. 기술적 용어는 한국어로 번역하되 필요시 영어 병기
5. 객관적이고 중립적인 톤 유지

요약:"""

    def generate_korean_summary(
        self, 
        post_title: str, 
        post_content: str, 
        post_id: str,
        max_tokens: int = 500
    ) -> Dict[str, Any]:
        """
        Generate Korean summary with GPT-4o-mini primary + GPT-4o fallback
        
        Args:
            post_title: Reddit post title
            post_content: Reddit post content
            post_id: Post ID for tracking
            max_tokens: Maximum tokens for response
        
        Returns:
            Dictionary with summary and token usage info
        """
        if not self._client:
            self.initialize()
        
        # Check daily token limit
        current_usage, is_over_limit = self.check_daily_token_usage()
        if is_over_limit:
            raise Exception(f"Daily token limit exceeded: {current_usage}/{self._daily_token_limit}")
        
        # Prepare Korean summary prompt
        prompt = self._get_korean_summary_prompt(post_title, post_content)
        
        # Try primary model first (GPT-4o-mini) with enhanced error handling
        model_used = None
        response = None
        fallback_attempted = False
        
        for attempt in range(2):  # Primary + fallback attempt
            current_model = self._primary_model if attempt == 0 else self._fallback_model
            
            try:
                logger.debug(f"Attempting {current_model} for post {post_id} (attempt {attempt + 1})")
                
                response = self._client.chat.completions.create(
                    model=current_model,
                    messages=[
                        {
                            "role": "system",
                            "content": "당신은 Reddit 게시글을 한국어로 요약하는 전문가입니다. 정확하고 간결하며 이해하기 쉬운 요약을 제공합니다."
                        },
                        {
                            "role": "user", 
                            "content": prompt
                        }
                    ],
                    max_tokens=max_tokens,
                    temperature=0.3,
                    timeout=30  # Add timeout
                )
                
                model_used = current_model
                if attempt == 0:
                    logger.info(f"Used primary model {self._primary_model} for post {post_id}")
                else:
                    logger.info(f"Used fallback model {self._fallback_model} for post {post_id}")
                    fallback_attempted = True
                break
                
            except openai.RateLimitError as e:
                logger.warning(f"Rate limit error with {current_model} for post {post_id}: {e}")
                if attempt == 0:  # Try fallback on rate limit
                    logger.info(f"Rate limit on primary model, trying fallback {self._fallback_model}")
                    continue
                else:
                    # Both models rate limited, raise the error
                    raise Exception(f"Both models rate limited: {e}")
                    
            except openai.APIError as e:
                logger.error(f"API error with {current_model} for post {post_id}: {e}")
                if attempt == 0 and "model_not_found" not in str(e).lower():
                    logger.info(f"API error on primary model, trying fallback {self._fallback_model}")
                    continue
                else:
                    raise Exception(f"API error: {e}")
                    
            except openai.APITimeoutError as e:
                logger.warning(f"Timeout error with {current_model} for post {post_id}: {e}")
                if attempt == 0:
                    logger.info(f"Timeout on primary model, trying fallback {self._fallback_model}")
                    continue
                else:
                    raise Exception(f"Timeout on both models: {e}")
                    
            except openai.APIConnectionError as e:
                logger.warning(f"Connection error with {current_model} for post {post_id}: {e}")
                if attempt == 0:
                    logger.info(f"Connection error on primary model, trying fallback {self._fallback_model}")
                    continue
                else:
                    raise Exception(f"Connection error on both models: {e}")
                    
            except Exception as e:
                logger.error(f"Unexpected error with {current_model} for post {post_id}: {e}")
                if attempt == 0:
                    logger.info(f"Unexpected error on primary model, trying fallback {self._fallback_model}")
                    continue
                else:
                    raise Exception(f"Both models failed: {e}")
        
        if not response or not model_used:
            raise Exception("Failed to get response from both primary and fallback models")
        
        # Extract response data
        summary = response.choices[0].message.content.strip()
        total_tokens = response.usage.total_tokens
        
        # Calculate cost using internal cost map
        cost = self._calculate_cost(total_tokens, model_used)
        
        # Update token usage tracking
        self._update_token_usage(total_tokens)
        
        logger.info(
            f"Generated Korean summary for post {post_id}",
            extra={
                "post_id": post_id,
                "model": model_used,
                "total_tokens": total_tokens,
                "cost_usd": float(cost),
                "summary_length": len(summary)
            }
        )
        
        return {
            "summary": summary,
            "model": model_used,
            "total_tokens": total_tokens,
            "cost_usd": cost
        }
    
    def extract_tags_llm(
        self,
        post_title: str,
        post_content: str,
        post_id: str,
        max_tokens: int = 200
    ) -> Dict[str, Any]:
        """
        Extract 3-5 tags using LLM prompt with consistent formatting rules
        
        Args:
            post_title: Reddit post title
            post_content: Reddit post content
            post_id: Post ID for tracking
            max_tokens: Maximum tokens for response
        
        Returns:
            Dictionary with tags and token usage info
        """
        if not self._client:
            self.initialize()
        
        # Check daily token limit
        current_usage, is_over_limit = self.check_daily_token_usage()
        if is_over_limit:
            raise Exception(f"Daily token limit exceeded: {current_usage}/{self._daily_token_limit}")
        
        # Prepare tag extraction prompt
        prompt = self._get_tag_extraction_prompt(post_title, post_content)
        
        # Try primary model first (GPT-4o-mini) with enhanced error handling
        model_used = None
        response = None
        
        for attempt in range(2):  # Primary + fallback attempt
            current_model = self._primary_model if attempt == 0 else self._fallback_model
            
            try:
                logger.debug(f"Attempting {current_model} for tag extraction {post_id} (attempt {attempt + 1})")
                
                response = self._client.chat.completions.create(
                    model=current_model,
                    messages=[
                        {
                            "role": "system",
                            "content": "당신은 Reddit 게시글에서 검색 최적화된 태그를 추출하는 전문가입니다. 일관된 표기 규칙을 따라 3-5개의 태그를 제공합니다."
                        },
                        {
                            "role": "user", 
                            "content": prompt
                        }
                    ],
                    max_tokens=max_tokens,
                    temperature=0.2,
                    timeout=30
                )
                
                model_used = current_model
                if attempt == 0:
                    logger.info(f"Used primary model {self._primary_model} for tag extraction {post_id}")
                else:
                    logger.info(f"Used fallback model {self._fallback_model} for tag extraction {post_id}")
                break
                
            except openai.RateLimitError as e:
                logger.warning(f"Rate limit error with {current_model} for tag extraction {post_id}: {e}")
                if attempt == 0:
                    continue
                else:
                    raise Exception(f"Both models rate limited for tag extraction: {e}")
                    
            except openai.APIError as e:
                logger.error(f"API error with {current_model} for tag extraction {post_id}: {e}")
                if attempt == 0 and "model_not_found" not in str(e).lower():
                    continue
                else:
                    raise Exception(f"API error in tag extraction: {e}")
                    
            except openai.APITimeoutError as e:
                logger.warning(f"Timeout error with {current_model} for tag extraction {post_id}: {e}")
                if attempt == 0:
                    continue
                else:
                    raise Exception(f"Timeout on both models for tag extraction: {e}")
                    
            except openai.APIConnectionError as e:
                logger.warning(f"Connection error with {current_model} for tag extraction {post_id}: {e}")
                if attempt == 0:
                    continue
                else:
                    raise Exception(f"Connection error on both models for tag extraction: {e}")
                    
            except Exception as e:
                logger.error(f"Unexpected error with {current_model} for tag extraction {post_id}: {e}")
                if attempt == 0:
                    continue
                else:
                    raise Exception(f"Both models failed for tag extraction: {e}")
        
        if not response or not model_used:
            raise Exception("Failed to get response from both models for tag extraction")
        
        # Extract and parse tags
        tags_text = response.choices[0].message.content.strip()
        total_tokens = response.usage.total_tokens
        
        # Parse tags from response (expecting comma-separated format)
        tags = []
        for tag in tags_text.split(','):
            tag = tag.strip().lower()
            if tag and len(tags) < 5:  # Limit to 5 tags
                tags.append(tag)
        
        # Ensure we have at least 3 tags
        if len(tags) < 3:
            # Add generic tags if needed
            generic_tags = ['reddit', '게시글', '콘텐츠']
            for generic_tag in generic_tags:
                if generic_tag not in tags and len(tags) < 3:
                    tags.append(generic_tag)
        
        # Calculate cost using internal cost map
        cost = self._calculate_cost(total_tokens, model_used)
        
        # Update token usage tracking
        self._update_token_usage(total_tokens)
        
        logger.info(
            f"Extracted tags for post {post_id}",
            extra={
                "post_id": post_id,
                "model": model_used,
                "total_tokens": total_tokens,
                "cost_usd": float(cost),
                "tags_count": len(tags),
                "tags": tags
            }
        )
        
        return {
            "tags": tags,
            "model": model_used,
            "total_tokens": total_tokens,
            "cost_usd": cost
        }
    
    def _get_tag_extraction_prompt(self, title: str, content: str) -> str:
        """Generate tag extraction prompt template"""
        return f"""다음 Reddit 게시글에서 3-5개의 태그를 추출해주세요:

제목: {title}

내용:
{content}

태그 추출 요구사항:
1. 3개에서 5개의 태그 추출
2. 모든 태그는 소문자로 작성
3. 한글 태그 우선, 필요시 영어 사용
4. 검색 최적화를 위한 키워드 선택
5. 일관된 표기 규칙 적용 (띄어쓰기 없이, 하이픈 사용 가능)
6. 쉼표로 구분하여 나열

예시: 개발, 프로그래밍, 웹개발, 기술, 튜토리얼

태그:"""
    
    def analyze_pain_points_and_ideas(
        self,
        post_title: str,
        post_content: str,
        post_id: str,
        max_tokens: int = 800
    ) -> Dict[str, Any]:
        """
        Analyze pain points and product ideas with JSON schema validation
        
        Args:
            post_title: Reddit post title
            post_content: Reddit post content
            post_id: Post ID for tracking
            max_tokens: Maximum tokens for response
        
        Returns:
            Dictionary with analysis results and token usage info
        """
        if not self._client:
            self.initialize()
        
        # Check daily token limit
        current_usage, is_over_limit = self.check_daily_token_usage()
        if is_over_limit:
            raise Exception(f"Daily token limit exceeded: {current_usage}/{self._daily_token_limit}")
        
        # Prepare analysis prompt
        prompt = self._get_pain_points_analysis_prompt(post_title, post_content)
        
        # Try primary model first (GPT-4o-mini) with enhanced error handling
        model_used = None
        response = None
        
        for attempt in range(2):  # Primary + fallback attempt
            current_model = self._primary_model if attempt == 0 else self._fallback_model
            
            try:
                logger.debug(f"Attempting {current_model} for analysis {post_id} (attempt {attempt + 1})")
                
                response = self._client.chat.completions.create(
                    model=current_model,
                    messages=[
                        {
                            "role": "system",
                            "content": "당신은 Reddit 게시글에서 사용자의 페인 포인트와 제품 아이디어를 추출하는 분석 전문가입니다. 정확한 JSON 형태로 결과를 제공합니다."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    max_tokens=max_tokens,
                    temperature=0.2,
                    response_format={"type": "json_object"},
                    timeout=30
                )
                
                model_used = current_model
                if attempt == 0:
                    logger.info(f"Used primary model {self._primary_model} for analysis {post_id}")
                else:
                    logger.info(f"Used fallback model {self._fallback_model} for analysis {post_id}")
                break
                
            except openai.RateLimitError as e:
                logger.warning(f"Rate limit error with {current_model} for analysis {post_id}: {e}")
                if attempt == 0:
                    continue
                else:
                    raise Exception(f"Both models rate limited for analysis: {e}")
                    
            except openai.APIError as e:
                logger.error(f"API error with {current_model} for analysis {post_id}: {e}")
                if attempt == 0 and "model_not_found" not in str(e).lower():
                    continue
                else:
                    raise Exception(f"API error in analysis: {e}")
                    
            except openai.APITimeoutError as e:
                logger.warning(f"Timeout error with {current_model} for analysis {post_id}: {e}")
                if attempt == 0:
                    continue
                else:
                    raise Exception(f"Timeout on both models for analysis: {e}")
                    
            except openai.APIConnectionError as e:
                logger.warning(f"Connection error with {current_model} for analysis {post_id}: {e}")
                if attempt == 0:
                    continue
                else:
                    raise Exception(f"Connection error on both models for analysis: {e}")
                    
            except Exception as e:
                logger.error(f"Unexpected error with {current_model} for analysis {post_id}: {e}")
                if attempt == 0:
                    continue
                else:
                    raise Exception(f"Both models failed for analysis: {e}")
        
        if not response or not model_used:
            raise Exception("Failed to get response from both models for analysis")
        
        # Extract and parse response
        analysis_text = response.choices[0].message.content.strip()
        total_tokens = response.usage.total_tokens
        
        # Parse JSON response with schema validation
        try:
            analysis_data = json.loads(analysis_text)
            # Validate and ensure required schema fields
            analysis_data = self._validate_analysis_schema(analysis_data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse analysis JSON for post {post_id}: {e}")
            # Fallback structure with schema compliance
            analysis_data = self._get_fallback_analysis_schema()
        
        # Calculate cost using internal cost map
        cost = self._calculate_cost(total_tokens, model_used)
        
        # Update token usage tracking
        self._update_token_usage(total_tokens)
        
        logger.info(
            f"Analyzed pain points for post {post_id}",
            extra={
                "post_id": post_id,
                "model": model_used,
                "total_tokens": total_tokens,
                "cost_usd": float(cost),
                "pain_points_count": len(analysis_data.get("pain_points", [])),
                "product_ideas_count": len(analysis_data.get("product_ideas", []))
            }
        )
        
        return {
            "analysis": analysis_data,
            "model": model_used,
            "total_tokens": total_tokens,
            "cost_usd": cost
        }
    
    def _get_pain_points_analysis_prompt(self, title: str, content: str) -> str:
        """Generate pain points analysis prompt template with JSON schema"""
        return f"""다음 Reddit 게시글을 분석하여 사용자의 페인 포인트와 잠재적 제품 아이디어를 추출해주세요:

제목: {title}

내용:
{content}

다음 JSON 스키마에 맞춰 결과를 제공해주세요:

{{
  "meta": {{
    "version": "1.0",
    "analysis_date": "{datetime.utcnow().isoformat()}",
    "confidence_score": 0.85
  }},
  "pain_points": [
    {{
      "description": "페인 포인트 설명",
      "category": "카테고리 (기술적/사용성/비용/시간/기타)",
      "severity": "심각도 (높음/보통/낮음)",
      "frequency": "빈도 (자주/가끔/드물게)"
    }}
  ],
  "product_ideas": [
    {{
      "title": "제품 아이디어 제목",
      "description": "제품 아이디어 설명",
      "target_pain_point": "해결하는 페인 포인트",
      "feasibility": "실현 가능성 (높음/보통/낮음)",
      "market_potential": "시장 잠재력 (높음/보통/낮음)"
    }}
  ],
  "analysis_notes": "분석 과정에서의 추가 노트"
}}

분석 기준:
1. 명시적으로 언급된 문제점과 불만사항 식별
2. 암시적으로 드러나는 니즈와 개선점 파악
3. 실현 가능한 제품/서비스 아이디어 도출
4. 시장성과 기술적 실현 가능성 고려
5. meta.version 필드는 반드시 포함"""
    
    def _validate_analysis_schema(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and ensure JSON schema compliance"""
        # Ensure meta field exists with version
        if "meta" not in data:
            data["meta"] = {}
        
        if "version" not in data["meta"]:
            data["meta"]["version"] = "1.0"
        
        if "analysis_date" not in data["meta"]:
            data["meta"]["analysis_date"] = datetime.utcnow().isoformat()
        
        # Ensure required arrays exist
        if "pain_points" not in data:
            data["pain_points"] = []
        
        if "product_ideas" not in data:
            data["product_ideas"] = []
        
        # Validate pain_points structure
        for pain_point in data["pain_points"]:
            if not isinstance(pain_point, dict):
                continue
            pain_point.setdefault("description", "")
            pain_point.setdefault("category", "기타")
            pain_point.setdefault("severity", "보통")
            pain_point.setdefault("frequency", "가끔")
        
        # Validate product_ideas structure
        for idea in data["product_ideas"]:
            if not isinstance(idea, dict):
                continue
            idea.setdefault("title", "")
            idea.setdefault("description", "")
            idea.setdefault("target_pain_point", "")
            idea.setdefault("feasibility", "보통")
            idea.setdefault("market_potential", "보통")
        
        return data
    
    def _get_fallback_analysis_schema(self) -> Dict[str, Any]:
        """Get fallback analysis structure when JSON parsing fails"""
        return {
            "meta": {
                "version": "1.0",
                "analysis_date": datetime.utcnow().isoformat(),
                "confidence_score": 0.0,
                "parsing_error": True
            },
            "pain_points": [],
            "product_ideas": [],
            "analysis_notes": "JSON 파싱 실패로 인한 기본 구조 반환"
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Check OpenAI client health status"""
        try:
            if not self._client:
                return {
                    "status": "unhealthy",
                    "error": "Client not initialized",
                    "api_key_configured": bool(self._api_key)
                }
            
            # Check daily token usage
            current_usage, is_over_limit = self.check_daily_token_usage()
            
            return {
                "status": "healthy" if not is_over_limit else "degraded",
                "daily_token_usage": current_usage,
                "daily_token_limit": self._daily_token_limit,
                "over_limit": is_over_limit,
                "primary_model": self._primary_model,
                "fallback_model": self._fallback_model
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# Global OpenAI client instance
openai_client = OpenAIClient()


def get_openai_client() -> OpenAIClient:
    """Get the global OpenAI client instance"""
    return openai_client