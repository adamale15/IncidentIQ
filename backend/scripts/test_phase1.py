"""
Test script for Phase 1 - Ingest corpus and test retrieval.
"""
import asyncio
import uuid
from pathlib import Path

from app.db.session import AsyncSessionLocal
from app.db.models import Workspace, DataSource, SourceType, SourceStatus
from app.connectors.markdown import MarkdownConnector
from app.ingestion.pipeline import IngestionPipeline
from app.retrieval.hybrid import HybridRetriever


async def test_phase1():
    """Test ingestion and retrieval."""
    
    print("=" * 60)
    print("PHASE 1 TEST - Ingestion & Retrieval")
    print("=" * 60)
    
    # Step 0: Initialize database tables
    print("\n[0/4] Initializing database...")
    from app.db.session import init_db
    try:
        await init_db()
        print("OK Database tables created")
    except Exception as e:
        print(f"WARN Database init warning: {e}")
        print("  Continuing anyway (tables may already exist)")
    
    # Create database session
    async with AsyncSessionLocal() as session:
        
        # Step 1: Create a test workspace
        print("\n[1/4] Creating test workspace...")
        workspace = Workspace(
            name="Test SRE Team",
            slug=f"test-sre-team-{uuid.uuid4().hex[:8]}"
        )
        session.add(workspace)
        await session.flush()
        print(f"OK Workspace created: {workspace.id}")
        
        # Step 2: Create data source
        print("\n[2/4] Creating data source...")
        data_source = DataSource(
            workspace_id=workspace.id,
            source_type=SourceType.MARKDOWN_DIR,
            config={"path": str(Path("../data/synthetic/postmortems").absolute())},
            status=SourceStatus.ACTIVE
        )
        session.add(data_source)
        await session.flush()
        print(f"OK Data source created: {data_source.id}")
        
        # Step 3: Ingest postmortems
        print("\n[3/4] Ingesting postmortems...")
        connector = MarkdownConnector(data_source.config)
        pipeline = IngestionPipeline()
        
        stats = await pipeline.ingest_from_connector(
            connector=connector,
            workspace_id=workspace.id,
            data_source_id=data_source.id,
            db_session=session
        )
        
        print(f"OK Ingestion complete!")
        print(f"  Documents: {stats['documents']}")
        print(f"  Chunks: {stats['chunks']}")
        
        # Step 4: Test retrieval
        print("\n[4/4] Testing hybrid retrieval...")
        retriever = HybridRetriever()
        
        test_queries = [
            "What causes connection pool issues?",
            "How to fix memory leaks?",
            "Payment service failures"
        ]
        
        for query in test_queries:
            print(f"\n  Query: '{query}'")
            results = await retriever.retrieve(
                query=query,
                workspace_id=workspace.id,
                top_k=3
            )
            
            print(f"  Retrieved {len(results)} chunks:")
            for i, result in enumerate(results[:2], 1):
                print(f"    {i}. Score: {result['score']:.3f} | {result['metadata']['document_title']}")
        
        await session.commit()
    
    print("\n" + "=" * 60)
    print("OK PHASE 1 TEST COMPLETE!")
    print(f"OK Workspace ID: {workspace.id}")
    print(f"OK Use this workspace_id for API queries")
    print("=" * 60)
    
    # Save workspace ID for later use
    with open("test_workspace_id.txt", "w") as f:
        f.write(str(workspace.id))
    print(f"\nWorkspace ID saved to: test_workspace_id.txt")


if __name__ == "__main__":
    asyncio.run(test_phase1())
