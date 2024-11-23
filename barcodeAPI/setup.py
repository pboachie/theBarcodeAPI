# setup.py
from setuptools import setup, find_packages

setup(
    name='theBarcodeAPI',
    version='0.1.8',
    packages=find_packages(),
    install_requires=[
        'fastapi==0.115.4',
        'uvicorn==0.32.0',
        'starlette==0.41.2',
        'pydantic==2.9.2',
        'pydantic-settings==2.6.1',
        'SQLAlchemy[asyncio]==2.0.36',
        'psycopg2-binary==2.9.10',
        'asyncpg==0.30.0',
        'alembic==1.14.0',
        'python-jose[cryptography]==3.3.0',
        'passlib[bcrypt]==1.7.4',
        'fastapi-limiter==0.1.6',
        'redis[hiredis]==5.2.0',
        'python-barcode==0.15.1',
        'Pillow-SIMD>=9.0.0.post0',
        'python-multipart==0.0.17',
        'pytz==2024.2',
        'aiohttp==3.10.10',
        'fastnanoid==0.4.1',
        'httpx==0.27.2',
    ],
)