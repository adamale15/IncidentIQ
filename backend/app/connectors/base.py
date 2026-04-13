"""
Base connector interface for data source ingestion.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from enum import Enum


class SourceType(str, Enum):
    """Supported data source types."""
    MARKDOWN_DIR = "markdown_dir"
    PAGERDUTY = "pagerduty"
    SLACK = "slack"
    GITHUB_ISSUES = "github_issues"
    OPSGENIE = "opsgenie"


class BaseConnector(ABC):
    """Abstract base class for data source connectors."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize connector with configuration.
        
        Args:
            config: Configuration dictionary specific to the connector type
        """
        self.config = config
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Validate configuration and establish connection if needed.
        
        Returns:
            True if connection is successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def fetch_documents(self) -> List[Dict[str, Any]]:
        """
        Fetch documents from the data source.
        
        Returns:
            List of document dictionaries with the following structure:
            {
                'title': str,
                'content': str,
                'source_url': str (optional),
                'metadata': {
                    'date': datetime (optional),
                    'severity': str (optional),
                    'services': List[str] (optional),
                    'team': str (optional),
                    'tags': List[str] (optional)
                }
            }
        """
        pass
    
    @abstractmethod
    def get_source_type(self) -> SourceType:
        """
        Get the source type for this connector.
        
        Returns:
            SourceType enum value
        """
        pass
    
    async def validate_config(self) -> bool:
        """
        Validate that the configuration has all required fields.
        
        Returns:
            True if config is valid, False otherwise
        """
        return True
