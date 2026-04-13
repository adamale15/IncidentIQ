"""
Markdown file connector for postmortem documents.
"""
import os
import re
import yaml
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import google.generativeai as genai

from app.connectors.base import BaseConnector, SourceType
from app.config import settings

logger = logging.getLogger(__name__)


class MarkdownConnector(BaseConnector):
    """Connector for ingesting Markdown postmortem files."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize MarkdownConnector.
        
        Args:
            config: Configuration dictionary with 'path' key pointing to directory
        """
        super().__init__(config)
        self.path = config.get('path')
        
        # Initialize Gemini for metadata extraction fallback
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_FLASH_MODEL)
    
    async def connect(self) -> bool:
        """Validate that the directory path exists."""
        if not self.path:
            logger.error("No path specified in configuration")
            return False
        
        if not os.path.exists(self.path):
            logger.error(f"Path does not exist: {self.path}")
            return False
        
        if not os.path.isdir(self.path):
            logger.error(f"Path is not a directory: {self.path}")
            return False
        
        logger.info(f"Connected to Markdown directory: {self.path}")
        return True
    
    async def fetch_documents(self) -> List[Dict[str, Any]]:
        """
        Scan directory for Markdown files and parse them.
        
        Returns:
            List of document dictionaries
        """
        documents = []
        markdown_files = list(Path(self.path).rglob("*.md"))
        
        logger.info(f"Found {len(markdown_files)} Markdown files in {self.path}")
        
        for file_path in markdown_files:
            try:
                doc = await self._parse_markdown_file(file_path)
                if doc:
                    documents.append(doc)
            except Exception as e:
                logger.error(f"Error parsing {file_path}: {e}", exc_info=True)
        
        logger.info(f"Successfully parsed {len(documents)} documents")
        return documents
    
    async def _parse_markdown_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Parse a single Markdown file.
        
        Args:
            file_path: Path to the Markdown file
            
        Returns:
            Document dictionary or None if parsing fails
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract frontmatter if present
        frontmatter, body = self._extract_frontmatter(content)
        
        # If no frontmatter, extract metadata using LLM
        if not frontmatter or not frontmatter.get('title'):
            logger.info(f"No frontmatter found in {file_path.name}, using LLM extraction")
            metadata = await self._extract_metadata_with_llm(body)
        else:
            metadata = self._parse_frontmatter_metadata(frontmatter)
        
        # Use filename as title fallback
        if not metadata.get('title'):
            metadata['title'] = file_path.stem.replace('-', ' ').replace('_', ' ').title()
        
        # Generate content hash for incremental ingestion
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        return {
            'title': metadata.get('title', file_path.stem),
            'content': body,
            'source_url': str(file_path.absolute()),
            'content_hash': content_hash,
            'metadata': {
                'date': metadata.get('date'),
                'severity': metadata.get('severity'),
                'services': metadata.get('services', []),
                'team': metadata.get('team'),
                'tags': metadata.get('tags', [])
            }
        }
    
    def _extract_frontmatter(self, content: str) -> tuple[Dict[str, Any], str]:
        """
        Extract YAML frontmatter from Markdown content.
        
        Args:
            content: Raw Markdown content
            
        Returns:
            Tuple of (frontmatter_dict, body_content)
        """
        # Check for YAML frontmatter (--- at start)
        frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
        match = re.match(frontmatter_pattern, content, re.DOTALL)
        
        if match:
            try:
                frontmatter = yaml.safe_load(match.group(1))
                body = match.group(2)
                return frontmatter or {}, body
            except yaml.YAMLError as e:
                logger.warning(f"Error parsing YAML frontmatter: {e}")
                return {}, content
        
        return {}, content
    
    def _parse_frontmatter_metadata(self, frontmatter: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse metadata from frontmatter.
        
        Args:
            frontmatter: Parsed YAML frontmatter dictionary
            
        Returns:
            Normalized metadata dictionary
        """
        metadata = {}
        
        # Extract title
        metadata['title'] = frontmatter.get('title', '')
        
        # Extract date
        date_value = frontmatter.get('date')
        if date_value:
            if isinstance(date_value, datetime):
                metadata['date'] = date_value
            elif isinstance(date_value, str):
                try:
                    # Try parsing common date formats
                    for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d']:
                        try:
                            metadata['date'] = datetime.strptime(date_value, fmt)
                            break
                        except ValueError:
                            continue
                except Exception as e:
                    logger.warning(f"Could not parse date: {date_value}")
        
        # Extract severity
        severity = frontmatter.get('severity', '').upper()
        if severity:
            metadata['severity'] = severity
        
        # Extract services (can be list or comma-separated string)
        services = frontmatter.get('services', [])
        if isinstance(services, str):
            services = [s.strip() for s in services.split(',')]
        metadata['services'] = services
        
        # Extract team
        metadata['team'] = frontmatter.get('team', '')
        
        # Extract tags
        tags = frontmatter.get('tags', [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(',')]
        metadata['tags'] = tags
        
        return metadata
    
    async def _extract_metadata_with_llm(self, content: str) -> Dict[str, Any]:
        """
        Extract metadata from content using LLM when frontmatter is missing.
        
        Args:
            content: Document content
            
        Returns:
            Extracted metadata dictionary
        """
        # Truncate content to first 3000 chars to save tokens
        truncated_content = content[:3000]
        
        prompt = f"""Analyze this incident postmortem and extract structured metadata.

Document content:
{truncated_content}

Extract the following information in JSON format:
{{
  "title": "Brief title of the incident",
  "date": "YYYY-MM-DD format if mentioned, or null",
  "severity": "P0, P1, P2, P3, or null",
  "services": ["list", "of", "affected", "services"],
  "team": "Owning team name or null"
}}

Only return the JSON, nothing else."""

        try:
            response = self.model.generate_content(prompt)
            
            # Extract JSON from response
            response_text = response.text.strip()
            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                response_text = re.sub(r'^```(?:json)?\s*|\s*```$', '', response_text, flags=re.MULTILINE)
            
            import json
            metadata = json.loads(response_text)
            
            # Parse date if present
            if metadata.get('date'):
                try:
                    metadata['date'] = datetime.strptime(metadata['date'], '%Y-%m-%d')
                except ValueError:
                    metadata['date'] = None
            
            logger.info(f"LLM extracted metadata: {metadata}")
            return metadata
            
        except Exception as e:
            logger.error(f"Error extracting metadata with LLM: {e}", exc_info=True)
            return {
                'title': '',
                'date': None,
                'severity': None,
                'services': [],
                'team': None
            }
    
    def get_source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.MARKDOWN_DIR
    
    async def validate_config(self) -> bool:
        """Validate configuration has required 'path' field."""
        if not self.config.get('path'):
            logger.error("Configuration missing required 'path' field")
            return False
        return True
