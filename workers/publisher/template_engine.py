"""
Content Template System for Ghost CMS Publishing (MVP Version)

Handles Article template rendering, Markdown to HTML conversion,
and automatic source attribution for Reddit content.
"""

import re
from typing import Dict, Any
from pathlib import Path
import logging

import markdown
from pybars import Compiler

from app.config import settings

logger = logging.getLogger(__name__)


class TemplateEngine:
    """Simplified template engine for Ghost CMS content (MVP - Article template only)"""
    
    def __init__(self, templates_dir: str = "templates"):
        self.templates_dir = Path(templates_dir)
        self.compiler = Compiler()
        self._article_template = None
        self._markdown = markdown.Markdown(
            extensions=[
                'markdown.extensions.extra',
                'markdown.extensions.codehilite',
                'markdown.extensions.nl2br'
            ],
            extension_configs={
                'codehilite': {
                    'css_class': 'highlight',
                    'use_pygments': True
                }
            }
        )
        
        # Load article template on initialization
        self._load_article_template()
    
    def _load_article_template(self):
        """Load the Article template (MVP - single template only)"""
        try:
            template_file = self.templates_dir / "article.hbs"
            
            if template_file.exists():
                with open(template_file, 'r', encoding='utf-8') as f:
                    template_content = f.read()
                
                # Compile the template
                self._article_template = self.compiler.compile(template_content)
                
                logger.info(f"Article template loaded successfully: {template_file}")
            else:
                logger.warning(f"Article template file not found: {template_file}")
                # Create a default template if file doesn't exist
                self._create_default_template()
                
        except Exception as e:
            logger.error(f"Failed to load article template: {e}")
            # Create a fallback template
            self._create_default_template()
    
    def _create_default_template(self):
        """Create a default article template if none exists"""
        default_template = '''
<article class="reddit-article">
    <header>
        <h1>{{title}}</h1>
        <div class="meta">
            <span class="subreddit">r/{{subreddit}}</span>
            <span class="score">{{score}} points</span>
            <span class="comments">{{comments}} comments</span>
        </div>
    </header>

    <div class="content">
        {{#if summary_ko}}
        <section class="summary">
            <h2>요약</h2>
            <p>{{summary_ko}}</p>
        </section>
        {{/if}}

        {{#if pain_points}}
        <section class="insights">
            <h2>핵심 인사이트</h2>
            <ul>
                {{#each pain_points}}
                <li>{{this}}</li>
                {{/each}}
            </ul>
        </section>
        {{/if}}

        {{#if product_ideas}}
        <section class="product-ideas">
            <h2>제품 아이디어</h2>
            <ul>
                {{#each product_ideas}}
                <li>{{this}}</li>
                {{/each}}
            </ul>
        </section>
        {{/if}}

        {{#if content}}
        <section class="original-content">
            <h2>원문</h2>
            <div class="reddit-content">
                {{{content}}}
            </div>
        </section>
        {{/if}}
    </div>
</article>
        '''
        
        self._article_template = self.compiler.compile(default_template.strip())
        logger.info("Default article template created")
    
    def markdown_to_html(self, markdown_text: str) -> str:
        """Convert Markdown text to HTML"""
        if not markdown_text:
            return ""
        
        try:
            # Reset the markdown instance to clear any previous state
            self._markdown.reset()
            
            # Convert markdown to HTML
            html = self._markdown.convert(markdown_text)
            
            # Clean up the HTML
            html = self._clean_html(html)
            
            logger.debug(
                "Markdown converted to HTML",
                input_length=len(markdown_text),
                output_length=len(html)
            )
            
            return html
            
        except Exception as e:
            logger.error("Failed to convert markdown to HTML", error=str(e))
            # Return the original text wrapped in a paragraph as fallback
            return f"<p>{markdown_text}</p>"
    
    def _clean_html(self, html: str) -> str:
        """Clean and sanitize HTML content"""
        # Remove any script tags for security
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove any style tags
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove any onclick or other event handlers
        html = re.sub(r'\s*on\w+\s*=\s*["\'][^"\']*["\']', '', html, flags=re.IGNORECASE)
        
        # Clean up extra whitespace
        html = re.sub(r'\s+', ' ', html)
        html = html.strip()
        
        return html
    
    def _add_source_attribution(self, content: str, reddit_url: str) -> str:
        """Add fixed source attribution as required by MVP
        
        Fixed format: Source/Media/Takedown notice
        """
        source_html = f'''
<hr>
<p><strong>Source:</strong> <a href="{reddit_url}" target="_blank" rel="noopener">Reddit</a></p>
<p><em>Media and usernames belong to their respective owners.</em></p>
<p><em>Requests for takedown will be honored.</em></p>
        '''
        
        # Always append at the end
        return content + source_html
    
    def _prepare_template_data(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare data for Article template rendering (MVP - single template)"""
        # Base data for article template
        template_data = {
            'title': post_data.get('title', ''),
            'subreddit': post_data.get('subreddit', ''),
            'score': post_data.get('score', 0),
            'comments': post_data.get('num_comments', 0),  # Use num_comments from DB schema
            'url': post_data.get('reddit_url', ''),  # Reddit URL for source attribution
            'summary_ko': post_data.get('summary_ko', ''),
        }
        
        # Convert content from markdown to HTML if needed
        raw_content = post_data.get('content', '')
        if raw_content:
            template_data['content'] = self.markdown_to_html(raw_content)
        
        # Process pain points and product ideas (JSON fields from DB)
        pain_points = post_data.get('pain_points')
        if pain_points:
            if isinstance(pain_points, str):
                # If it's a JSON string, try to parse it
                try:
                    import json
                    pain_points = json.loads(pain_points)
                except:
                    pain_points = []
            elif isinstance(pain_points, dict):
                # If it's a dict, extract values or convert to list
                pain_points = list(pain_points.values()) if pain_points else []
            template_data['pain_points'] = pain_points
        
        product_ideas = post_data.get('product_ideas')
        if product_ideas:
            if isinstance(product_ideas, str):
                try:
                    import json
                    product_ideas = json.loads(product_ideas)
                except:
                    product_ideas = []
            elif isinstance(product_ideas, dict):
                product_ideas = list(product_ideas.values()) if product_ideas else []
            template_data['product_ideas'] = product_ideas
        
        return template_data
    
    def render_article(self, post_data: Dict[str, Any]) -> str:
        """Render content using the Article template (MVP - single template only)"""
        try:
            if not self._article_template:
                raise ValueError("Article template not available")
            
            # Prepare template data
            template_data = self._prepare_template_data(post_data)
            
            # Render the template
            rendered_content = self._article_template(template_data)
            
            # Add fixed source attribution
            reddit_url = post_data.get('reddit_url', post_data.get('url', ''))
            final_content = self._add_source_attribution(rendered_content, reddit_url)
            
            logger.info(f"Article template rendered successfully: {post_data.get('title', '')[:50]}")
            
            return final_content
            
        except Exception as e:
            logger.error(f"Failed to render article template: {e}")
            
            # Fallback to simple HTML
            return self._create_fallback_content(post_data)
    
    def _create_fallback_content(self, post_data: Dict[str, Any]) -> str:
        """Create simple fallback content when template rendering fails"""
        title = post_data.get('title', 'Untitled')
        content = post_data.get('content', '')
        summary = post_data.get('summary_ko', '')
        reddit_url = post_data.get('reddit_url', post_data.get('url', ''))
        
        html_content = self.markdown_to_html(content) if content else ""
        
        fallback_html = f"""
<article class="reddit-fallback">
    <h1>{title}</h1>
    {f'<div class="summary"><h2>요약</h2><p>{summary}</p></div>' if summary else ''}
    {f'<div class="content">{html_content}</div>' if html_content else ''}
</article>
        """
        
        # Add source attribution
        return self._add_source_attribution(fallback_html, reddit_url)


# Singleton instance for MVP
_template_engine = None

def get_template_engine() -> TemplateEngine:
    """Get singleton template engine instance"""
    global _template_engine
    if _template_engine is None:
        _template_engine = TemplateEngine()
    return _template_engine