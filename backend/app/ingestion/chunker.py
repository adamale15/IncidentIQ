"""
Section-aware chunking engine for different document types.
"""
import re
import logging
from typing import List, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ChunkType(str, Enum):
    """Types of chunks."""
    SUMMARY = "summary"
    ROOT_CAUSE = "root_cause"
    TIMELINE = "timeline"
    RESOLUTION = "resolution"
    ACTION_ITEMS = "action_items"
    ALERT = "alert"
    ALERT_BURST = "alert_burst"
    DISCUSSION = "discussion"
    RUNBOOK_STEP = "runbook_step"
    GENERIC = "generic"


class BaseChunker:
    """Base class for chunking strategies."""
    
    def __init__(self, max_chunk_tokens: int = 1000):
        """
        Initialize chunker.
        
        Args:
            max_chunk_tokens: Maximum tokens per chunk (approximate)
        """
        self.max_chunk_tokens = max_chunk_tokens
        self.max_chunk_chars = max_chunk_tokens * 4  # Rough estimate: 1 token ≈ 4 chars
    
    def chunk(self, content: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk document content.
        
        Args:
            content: Document content
            metadata: Document metadata
            
        Returns:
            List of chunk dictionaries
        """
        raise NotImplementedError


class PostmortemChunker(BaseChunker):
    """Chunker for postmortem documents - section-aware."""
    
    SECTION_PATTERNS = {
        ChunkType.SUMMARY: [
            r'##?\s*Summary',
            r'##?\s*Overview',
            r'##?\s*Executive Summary'
        ],
        ChunkType.ROOT_CAUSE: [
            r'##?\s*Root Cause',
            r'##?\s*Cause',
            r'##?\s*Why did this happen'
        ],
        ChunkType.TIMELINE: [
            r'##?\s*Timeline',
            r'##?\s*Incident Timeline',
            r'##?\s*Event Timeline'
        ],
        ChunkType.RESOLUTION: [
            r'##?\s*Resolution',
            r'##?\s*Fix',
            r'##?\s*How it was fixed',
            r'##?\s*Remediation'
        ],
        ChunkType.ACTION_ITEMS: [
            r'##?\s*Action Items',
            r'##?\s*Follow[- ]?up',
            r'##?\s*Next Steps',
            r'##?\s*TODO'
        ]
    }
    
    def chunk(self, content: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk postmortem by sections.
        
        Args:
            content: Postmortem content
            metadata: Document metadata
            
        Returns:
            List of chunks with metadata
        """
        chunks = []
        
        # Split by h2/h3 headers
        sections = self._split_by_headers(content)
        
        for section_title, section_content, start_pos, end_pos in sections:
            if not section_content.strip():
                continue
            
            # Determine chunk type from section title
            chunk_type = self._classify_section(section_title)
            
            # If section is too long, split by paragraphs
            if len(section_content) > self.max_chunk_chars:
                sub_chunks = self._split_long_section(section_content, start_pos)
                for sub_content, sub_start, sub_end in sub_chunks:
                    chunks.append({
                        'content': sub_content,
                        'chunk_type': chunk_type,
                        'start_char': sub_start,
                        'end_char': sub_end,
                        'metadata': {
                            **metadata,
                            'section_title': section_title
                        }
                    })
            else:
                chunks.append({
                    'content': section_content,
                    'chunk_type': chunk_type,
                    'start_char': start_pos,
                    'end_char': end_pos,
                    'metadata': {
                        **metadata,
                        'section_title': section_title
                    }
                })
        
        logger.info(f"Postmortem chunked into {len(chunks)} sections")
        return chunks
    
    def _split_by_headers(self, content: str) -> List[tuple]:
        """
        Split content by markdown headers.
        
        Returns:
            List of (title, content, start_pos, end_pos) tuples
        """
        # Match h2 (##) or h3 (###) headers
        header_pattern = r'^(#{2,3})\s+(.+)$'
        
        sections = []
        lines = content.split('\n')
        current_section = []
        current_title = "Introduction"
        section_start = 0
        char_pos = 0
        
        for i, line in enumerate(lines):
            match = re.match(header_pattern, line)
            
            if match:
                # Save previous section
                if current_section:
                    section_content = '\n'.join(current_section)
                    sections.append((
                        current_title,
                        section_content,
                        section_start,
                        char_pos
                    ))
                
                # Start new section
                current_title = match.group(2).strip()
                current_section = []
                section_start = char_pos + len(line) + 1
            else:
                current_section.append(line)
            
            char_pos += len(line) + 1  # +1 for newline
        
        # Add final section
        if current_section:
            section_content = '\n'.join(current_section)
            sections.append((
                current_title,
                section_content,
                section_start,
                char_pos
            ))
        
        return sections
    
    def _classify_section(self, section_title: str) -> ChunkType:
        """Classify section type from title."""
        section_lower = section_title.lower()
        
        for chunk_type, patterns in self.SECTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, section_title, re.IGNORECASE):
                    return chunk_type
        
        return ChunkType.GENERIC
    
    def _split_long_section(self, content: str, start_pos: int) -> List[tuple]:
        """
        Split long section by paragraphs.
        
        Returns:
            List of (content, start_pos, end_pos) tuples
        """
        paragraphs = content.split('\n\n')
        chunks = []
        current_chunk = []
        current_length = 0
        chunk_start = start_pos
        
        for para in paragraphs:
            para_len = len(para)
            
            if current_length + para_len > self.max_chunk_chars and current_chunk:
                # Save current chunk
                chunk_content = '\n\n'.join(current_chunk)
                chunk_end = chunk_start + len(chunk_content)
                chunks.append((chunk_content, chunk_start, chunk_end))
                
                # Start new chunk
                current_chunk = [para]
                current_length = para_len
                chunk_start = chunk_end + 2  # +2 for \n\n
            else:
                current_chunk.append(para)
                current_length += para_len + 2  # +2 for \n\n
        
        # Add final chunk
        if current_chunk:
            chunk_content = '\n\n'.join(current_chunk)
            chunk_end = chunk_start + len(chunk_content)
            chunks.append((chunk_content, chunk_start, chunk_end))
        
        return chunks


class AlertChunker(BaseChunker):
    """Chunker for alert payloads."""
    
    def chunk(self, content: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Each alert becomes one chunk.
        
        Args:
            content: Alert payload (JSON string or formatted text)
            metadata: Alert metadata
            
        Returns:
            List with single chunk
        """
        return [{
            'content': content,
            'chunk_type': ChunkType.ALERT,
            'start_char': 0,
            'end_char': len(content),
            'metadata': metadata
        }]
    
    @staticmethod
    def group_alerts(alerts: List[Dict[str, Any]], time_window_seconds: int = 300) -> List[Dict[str, Any]]:
        """
        Group alerts within time window into alert bursts.
        
        Args:
            alerts: List of alert dictionaries with 'timestamp' in metadata
            time_window_seconds: Time window for grouping (default 5 minutes)
            
        Returns:
            List of grouped alert bursts
        """
        if not alerts:
            return []
        
        # Sort by timestamp
        sorted_alerts = sorted(alerts, key=lambda a: a['metadata'].get('date', 0))
        
        bursts = []
        current_burst = [sorted_alerts[0]]
        
        for alert in sorted_alerts[1:]:
            time_diff = (alert['metadata'].get('date', 0) - 
                        current_burst[0]['metadata'].get('date', 0))
            
            if hasattr(time_diff, 'total_seconds'):
                time_diff_seconds = time_diff.total_seconds()
            else:
                time_diff_seconds = 0
            
            if time_diff_seconds <= time_window_seconds:
                current_burst.append(alert)
            else:
                # Save current burst
                if len(current_burst) > 1:
                    bursts.append({
                        'content': '\n\n'.join([a['content'] for a in current_burst]),
                        'chunk_type': ChunkType.ALERT_BURST,
                        'metadata': {
                            'alert_count': len(current_burst),
                            'services': list(set([s for a in current_burst 
                                                for s in a['metadata'].get('services', [])])),
                            'date': current_burst[0]['metadata'].get('date')
                        }
                    })
                else:
                    bursts.append(current_burst[0])
                
                # Start new burst
                current_burst = [alert]
        
        # Add final burst
        if len(current_burst) > 1:
            bursts.append({
                'content': '\n\n'.join([a['content'] for a in current_burst]),
                'chunk_type': ChunkType.ALERT_BURST,
                'metadata': {
                    'alert_count': len(current_burst),
                    'services': list(set([s for a in current_burst 
                                        for s in a['metadata'].get('services', [])])),
                    'date': current_burst[0]['metadata'].get('date')
                }
            })
        else:
            bursts.append(current_burst[0])
        
        return bursts


class SlackChunker(BaseChunker):
    """Chunker for Slack thread conversations."""
    
    def __init__(self, max_chunk_tokens: int = 1000, message_overlap: int = 2):
        """
        Initialize Slack chunker.
        
        Args:
            max_chunk_tokens: Maximum tokens per chunk
            message_overlap: Number of messages to overlap between chunks
        """
        super().__init__(max_chunk_tokens)
        self.message_overlap = message_overlap
    
    def chunk(self, content: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk Slack thread by conversation turns with overlap.
        
        Args:
            content: Formatted Slack thread content
            metadata: Thread metadata
            
        Returns:
            List of chunks
        """
        # Assume content is formatted as:
        # [timestamp] username: message\n
        
        messages = self._parse_messages(content)
        
        if not messages:
            return []
        
        chunks = []
        current_chunk = []
        current_length = 0
        chunk_start = 0
        
        for i, (msg_text, msg_len) in enumerate(messages):
            if current_length + msg_len > self.max_chunk_chars and current_chunk:
                # Save current chunk
                chunk_content = '\n'.join(current_chunk)
                chunk_end = chunk_start + len(chunk_content)
                chunks.append({
                    'content': chunk_content,
                    'chunk_type': ChunkType.DISCUSSION,
                    'start_char': chunk_start,
                    'end_char': chunk_end,
                    'metadata': metadata
                })
                
                # Start new chunk with overlap
                overlap_start = max(0, len(current_chunk) - self.message_overlap)
                current_chunk = current_chunk[overlap_start:]
                current_length = sum(len(m) for m in current_chunk)
                chunk_start = chunk_end - current_length
            
            current_chunk.append(msg_text)
            current_length += msg_len
        
        # Add final chunk
        if current_chunk:
            chunk_content = '\n'.join(current_chunk)
            chunk_end = chunk_start + len(chunk_content)
            chunks.append({
                'content': chunk_content,
                'chunk_type': ChunkType.DISCUSSION,
                'start_char': chunk_start,
                'end_char': chunk_end,
                'metadata': metadata
            })
        
        logger.info(f"Slack thread chunked into {len(chunks)} conversation turns")
        return chunks
    
    def _parse_messages(self, content: str) -> List[tuple]:
        """
        Parse messages from formatted content.
        
        Returns:
            List of (message_text, message_length) tuples
        """
        lines = content.split('\n')
        messages = []
        
        for line in lines:
            if line.strip():
                messages.append((line, len(line)))
        
        return messages


class ChunkerFactory:
    """Factory to get the appropriate chunker for a document type."""
    
    @staticmethod
    def get_chunker(source_type: str, **kwargs) -> BaseChunker:
        """
        Get chunker instance for source type.
        
        Args:
            source_type: Type of document source
            **kwargs: Additional arguments for chunker
            
        Returns:
            Chunker instance
        """
        chunker_map = {
            'postmortem': PostmortemChunker,
            'markdown': PostmortemChunker,
            'alert': AlertChunker,
            'pagerduty': AlertChunker,
            'slack': SlackChunker,
            'slack_thread': SlackChunker,
        }
        
        chunker_class = chunker_map.get(source_type.lower(), PostmortemChunker)
        return chunker_class(**kwargs)
