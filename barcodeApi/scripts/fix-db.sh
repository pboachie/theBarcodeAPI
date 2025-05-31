#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Stopping all containers...${NC}"
docker compose down -v

echo -e "${YELLOW}Starting fresh database container...${NC}"
docker compose up -d db

echo -e "${YELLOW}Waiting for database to start (10 seconds)...${NC}"
sleep 10

echo -e "${YELLOW}Setting up database...${NC}"
docker compose exec db bash -c "psql -U postgres <<-EOSQL
    DROP DATABASE IF EXISTS barcode_api;
    DROP DATABASE IF EXISTS barcodeapi;
    DROP USER IF EXISTS barcodeboachiefamily;

    CREATE USER barcodeboachiefamily WITH PASSWORD '$DB_PASSWORD' LOGIN;
    CREATE DATABASE barcode_api WITH OWNER = barcodeboachiefamily;

    \c barcode_api

    CREATE SCHEMA IF NOT EXISTS public AUTHORIZATION barcodeboachiefamily;
    GRANT ALL ON SCHEMA public TO barcodeboachiefamily;
    ALTER DEFAULT PRIVILEGES FOR ROLE barcodeboachiefamily IN SCHEMA public
    GRANT ALL ON TABLES TO barcodeboachiefamily;
EOSQL"

# Clear and rewrite pg_hba.conf
echo -e "${YELLOW}Configuring pg_hba.conf...${NC}"
docker compose exec db bash -c "cat > /var/lib/postgresql/data/pg_hba.conf << 'EOL'
# TYPE  DATABASE        USER            ADDRESS                 METHOD

# Database administrative login by Unix domain socket
local   all             postgres                                trust

# Allow anyone on the local system to connect to any database with
# any database user name using Unix-domain sockets
local   all             all                                     trust

# Same using local TCP/IP connections
host    all             all             127.0.0.1/32            trust

# Allow IPv6 local connections
host    all             all             ::1/128                 trust

# Allow all IPv4 connections with password
host    all             barcodeboachiefamily     0.0.0.0/0               md5
host    all             barcodeboachiefamily     172.0.0.0/8             md5
host    all             postgres                 0.0.0.0/0               md5
EOL"

# Restart PostgreSQL to apply changes
echo -e "${YELLOW}Restarting PostgreSQL...${NC}"
docker compose restart db

echo -e "${YELLOW}Waiting for database to restart (5 seconds)...${NC}"
sleep 5

# Test connection
echo -e "${YELLOW}Testing connection...${NC}"
docker compose exec db psql -U barcodeboachiefamily -d barcode_api -c "\conninfo"

# Add test table
echo -e "${YELLOW}Testing permissions with a test table...${NC}"
docker compose exec db psql -U barcodeboachiefamily -d barcode_api <<-EOSQL
    CREATE TABLE IF NOT EXISTS test_table (id SERIAL PRIMARY KEY, name TEXT);
    INSERT INTO test_table (name) VALUES ('test');
    SELECT * FROM test_table;
EOSQL

echo -e "${GREEN}Database has been reset and permissions fixed!${NC}"
echo -e "${YELLOW}Now update your connection string to:${NC}"
echo -e "${GREEN}postgresql+asyncpg://barcodeboachiefamily:$DB_PASSWORD@db:5432/barcode_api${NC}"