"""
Direct database connection test - bypasses .env loading issues.
"""
import asyncio
import asyncpg


async def test_connection():
    """Test direct connection to PostgreSQL."""
    
    print("Testing direct PostgreSQL connection...")
    print("Host: localhost")
    print("Port: 5433")
    print("User: iip_user")
    print("Database: incidentiq")
    
    try:
        conn = await asyncpg.connect(
            host='localhost',
            port=5433,
            user='iip_user',
            password='iip_password',
            database='incidentiq'
        )
        
        # Test query
        version = await conn.fetchval('SELECT version()')
        print(f"\nOK Connection successful!")
        print(f"PostgreSQL version: {version}")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"\nFAIL Connection failed: {e}")
        return False


if __name__ == "__main__":
    result = asyncio.run(test_connection())
    
    if result:
        print("\n" + "="*60)
        print("DATABASE CONNECTION WORKS!")
        print("The issue is with .env file loading in the app")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("DATABASE CONNECTION ISSUE")
        print("Check Docker PostgreSQL is running: docker compose ps")
        print("="*60)
