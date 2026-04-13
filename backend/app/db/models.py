"""
SQLAlchemy ORM models for the database schema.
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, ForeignKey, ARRAY, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.db.session import Base


class SourceType(str, enum.Enum):
    """Enum for data source types."""
    MARKDOWN_DIR = "markdown_dir"
    PAGERDUTY = "pagerduty"
    SLACK = "slack"
    GITHUB_ISSUES = "github_issues"
    OPSGENIE = "opsgenie"


class SourceStatus(str, enum.Enum):
    """Enum for data source status."""
    ACTIVE = "active"
    SYNCING = "syncing"
    ERROR = "error"
    DISABLED = "disabled"


class MessageRole(str, enum.Enum):
    """Enum for message roles."""
    USER = "user"
    ASSISTANT = "assistant"


class Feedback(str, enum.Enum):
    """Enum for message feedback."""
    POSITIVE = "positive"
    NEGATIVE = "negative"


class EvalRunType(str, enum.Enum):
    """Enum for evaluation run types."""
    NIGHTLY = "nightly"
    MANUAL = "manual"
    CI = "ci"


class Workspace(Base):
    """Workspace model."""
    __tablename__ = "workspaces"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    users = relationship("User", back_populates="workspace")
    data_sources = relationship("DataSource", back_populates="workspace")
    documents = relationship("Document", back_populates="workspace")
    chunks = relationship("Chunk", back_populates="workspace")
    conversations = relationship("Conversation", back_populates="workspace")
    eval_runs = relationship("EvalRun", back_populates="workspace")


class User(Base):
    """User model."""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255))
    avatar_url = Column(String(512))
    oauth_provider = Column(String(50))
    oauth_id = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    workspace = relationship("Workspace", back_populates="users")
    conversations = relationship("Conversation", back_populates="user")


class DataSource(Base):
    """Data source model."""
    __tablename__ = "data_sources"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    source_type = Column(SQLEnum(SourceType), nullable=False)
    config = Column(JSONB, nullable=False)  # Store encrypted credentials
    status = Column(SQLEnum(SourceStatus), default=SourceStatus.ACTIVE)
    last_synced_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    workspace = relationship("Workspace", back_populates="data_sources")
    documents = relationship("Document", back_populates="data_source")


class Document(Base):
    """Document model."""
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    data_source_id = Column(UUID(as_uuid=True), ForeignKey("data_sources.id"), nullable=False)
    title = Column(String(512), nullable=False)
    source_url = Column(String(1024))
    source_type = Column(String(50), nullable=False)
    incident_date = Column(DateTime)
    severity = Column(String(20))
    services = Column(ARRAY(Text))
    teams = Column(ARRAY(Text))
    raw_content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    workspace = relationship("Workspace", back_populates="documents")
    data_source = relationship("DataSource", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document")


class Chunk(Base):
    """Chunk model."""
    __tablename__ = "chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    content = Column(Text, nullable=False)
    chunk_type = Column(String(50))
    start_char = Column(Integer)
    end_char = Column(Integer)
    chunk_metadata = Column("metadata", JSONB)  # Rename column attribute to avoid conflict
    qdrant_point_id = Column(UUID(as_uuid=True), unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    document = relationship("Document", back_populates="chunks")
    workspace = relationship("Workspace", back_populates="chunks")


class Conversation(Base):
    """Conversation model."""
    __tablename__ = "conversations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(String(512))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    workspace = relationship("Workspace", back_populates="conversations")
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation")


class Message(Base):
    """Message model."""
    __tablename__ = "messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    role = Column(SQLEnum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    retrieved_chunk_ids = Column(ARRAY(UUID(as_uuid=True)))
    retrieval_scores = Column(ARRAY(Float))
    latency_ms = Column(Integer)
    model_used = Column(String(100))
    feedback = Column(SQLEnum(Feedback))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")


class EvalRun(Base):
    """Evaluation run model."""
    __tablename__ = "eval_runs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    run_type = Column(SQLEnum(EvalRunType), nullable=False)
    faithfulness = Column(Float)
    answer_relevancy = Column(Float)
    context_precision = Column(Float)
    context_recall = Column(Float)
    total_questions = Column(Integer)
    avg_latency_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    workspace = relationship("Workspace", back_populates="eval_runs")
    results = relationship("EvalResult", back_populates="eval_run")


class EvalResult(Base):
    """Evaluation result model."""
    __tablename__ = "eval_results"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    eval_run_id = Column(UUID(as_uuid=True), ForeignKey("eval_runs.id"), nullable=False)
    question = Column(Text, nullable=False)
    expected_answer = Column(Text, nullable=False)
    generated_answer = Column(Text, nullable=False)
    retrieved_chunks = Column(ARRAY(UUID(as_uuid=True)))
    faithfulness = Column(Float)
    answer_relevancy = Column(Float)
    context_precision = Column(Float)
    context_recall = Column(Float)
    latency_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    eval_run = relationship("EvalRun", back_populates="results")
