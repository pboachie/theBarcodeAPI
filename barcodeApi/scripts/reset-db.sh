#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Stopping all containers...${NC}"
docker compose down

echo -e "${YELLOW}Removing database volume...${NC}"
docker volume rm barcodeapi_postgres_data || true

echo -e "${YELLOW}Removing all stopped containers...${NC}"
docker container prune -f

echo -e "${YELLOW}Removing unused volumes...${NC}"
docker volume prune -f

echo -e "${GREEN}Starting services again...${NC}"
docker compose up -d

echo -e "${YELLOW}Waiting for database to initialize (30 seconds)...${NC}"
sleep 30

echo -e "${GREEN}Database has been reset!${NC}"
echo -e "${YELLOW}You can check logs with: docker compose logs -f${NC}"