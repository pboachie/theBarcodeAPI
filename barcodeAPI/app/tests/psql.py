import asyncio
import asyncpg
from urllib.parse import quote_plus
from app.config import settings

async def test_connection():
    password = quote_plus(settings.DB_PASSWORD)
    connection_params = {
        'user': 'barcodeboachiefamily',
        'password': password,
        'database': 'barcode_api',
        'host': 'localhost',
        'port': 5432
    }

    try:
        print(f"Attempting connection with params: {connection_params}")
        conn = await asyncpg.connect(**connection_params)

        version = await conn.fetchval('SELECT version()')
        print(f"Connected successfully! PostgreSQL version: {version}")

        # Test permissions
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS connection_test (
                id SERIAL PRIMARY KEY,
                test_data TEXT
            )
        ''')

        await conn.execute('''
            INSERT INTO connection_test (test_data) VALUES ($1)
        ''', 'Test successful')

        result = await conn.fetchval('SELECT test_data FROM connection_test LIMIT 1')
        print(f"Test query result: {result}")

        await conn.close()
    except Exception as e:
        print(f"Connection failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_connection())