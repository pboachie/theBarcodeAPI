#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Checking PostgreSQL configuration...${NC}"

# Check user and database existence
docker compose exec db psql -U postgres -c "\du barcodeboachiefamily"
docker compose exec db psql -U postgres -c "\l barcode_api"

# Check schema permissions
docker compose exec db psql -U postgres -d barcode_api -c "\dn+"

# Check specific permissions
docker compose exec db psql -U postgres -d barcode_api <<-EOSQL
    SELECT
        grantee, privilege_type, table_schema, table_name
    FROM
        information_schema.table_privileges
    WHERE
        grantee = 'barcodeboachiefamily';

    SELECT
        grantee, privilege_type, table_schema, table_name
    FROM
        information_schema.role_table_grants
    WHERE
        grantee = 'barcodeboachiefamily';
EOSQL

# Check pg_hba.conf
echo -e "\n${YELLOW}Checking pg_hba.conf entries:${NC}"
docker compose exec db bash -c "cat /var/lib/postgresql/data/pg_hba.conf | grep -v '^#' | grep -v '^$'"

# Test connection as barcodeboachiefamily
echo -e "\n${YELLOW}Testing connection as barcodeboachiefamily:${NC}"
docker compose exec db psql -U barcodeboachiefamily -d barcode_api -c "SELECT current_user, current_database(), session_user, inet_server_addr();"

# Show current database size
echo -e "\n${YELLOW}Database size:${NC}"
docker compose exec db psql -U postgres -d barcode_api -c "SELECT pg_size_pretty(pg_database_size('barcode_api'));"