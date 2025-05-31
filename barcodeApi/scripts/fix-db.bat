@echo off
setlocal EnableDelayedExpansion

REM Attempt to read DB_PASSWORD from .env file using PowerShell
echo Attempting to load DB_PASSWORD from .env file (in current directory)...
SET "DB_PASSWORD=" REM Clear any pre-existing DB_PASSWORD

REM PowerShell command to extract DB_PASSWORD. Outputs value or a placeholder if not found/empty.
FOR /F "delims=" %%v IN (
    'powershell -NoProfile -ExecutionPolicy Bypass -Command "$val = try { Get-Content .\.env -ErrorAction Stop | Where-Object { $_.Trim() -match '^DB_PASSWORD=' } | ForEach-Object { ($_.Trim() -split '=', 2)[1].Trim() } | Select-Object -First 1 } catch { $null }; if ($val -ne $null -and $val -ne '') { Write-Output $val } else { Write-Output '___EMPTY_OR_NOT_FOUND___' }"'
) DO (
    SET "DB_PASSWORD=%%v"
)

REM Check the result of loading DB_PASSWORD
IF DEFINED DB_PASSWORD (
    IF "!DB_PASSWORD!" == "___EMPTY_OR_NOT_FOUND___" (
        echo WARNING: DB_PASSWORD not found in .env or its value is empty.
        SET "DB_PASSWORD=" REM Ensure it is treated as empty for SQL if placeholder was returned
    ) ELSE (
        REM Password seems to be loaded, now remove potential surrounding quotes
        IF "!DB_PASSWORD:~0,1!" == """ SET "DB_PASSWORD=!DB_PASSWORD:~1,-1!"
        IF "!DB_PASSWORD:~0,1!" == "'" SET "DB_PASSWORD=!DB_PASSWORD:~1,-1!"
        echo DB_PASSWORD loaded successfully from .env.
    )
) ELSE (
    echo CRITICAL_ERROR: Failed to capture any output from PowerShell. DB_PASSWORD remains unset.
    echo This can happen if PowerShell is not available or the command has errors.
)

IF NOT DEFINED DB_PASSWORD (
    echo Final Check - WARNING: DB_PASSWORD is not set. The database user might be created without a password.
    echo Please ensure .env exists in the current directory and contains DB_PASSWORD, or set DB_PASSWORD manually in your environment.
)

REM Script to reset and configure the PostgreSQL database for the Barcode API

echo Stopping all containers...
docker compose down -v

echo Starting fresh database container...
docker compose up -d db

echo Waiting for database to start (10 seconds)...
timeout /t 10 /nobreak > nul

echo Setting up database...
REM Create a temporary SQL file for initial database setup
(
    echo DROP DATABASE IF EXISTS barcode_api;
    echo DROP DATABASE IF EXISTS barcodeapi;
    echo DROP USER IF EXISTS barcodeboachiefamily;
    echo CREATE USER barcodeboachiefamily WITH PASSWORD '%DB_PASSWORD%' LOGIN;
    echo CREATE DATABASE barcode_api WITH OWNER = barcodeboachiefamily;
    echo \c barcode_api
    echo CREATE SCHEMA IF NOT EXISTS public AUTHORIZATION barcodeboachiefamily;
    echo GRANT ALL ON SCHEMA public TO barcodeboachiefamily;
    echo ALTER DEFAULT PRIVILEGES FOR ROLE barcodeboachiefamily IN SCHEMA public
    echo GRANT ALL ON TABLES TO barcodeboachiefamily;
) > temp_db_setup.sql

REM Execute the SQL script inside the container by piping its content
type temp_db_setup.sql | docker compose exec -T db psql -U postgres

REM Clean up the temporary SQL file from the host
del temp_db_setup.sql

echo Configuring pg_hba.conf...
REM Create a temporary pg_hba.conf file
(
    echo # TYPE  DATABASE        USER            ADDRESS                 METHOD
    echo # Database administrative login by Unix domain socket
    echo local   all             postgres                                trust
    echo # Allow anyone on the local system to connect to any database with
    echo # any database user name using Unix-domain sockets
    echo local   all             all                                     trust
    echo # Same using local TCP/IP connections
    echo host    all             all             127.0.0.1/32            trust
    echo # Allow IPv6 local connections
    echo host    all             all             ::1/128                 trust
    echo # Allow all IPv4 connections with password
    echo host    all             barcodeboachiefamily     0.0.0.0/0               md5
    echo host    all             barcodeboachiefamily     172.0.0.0/8             md5
    echo host    all             postgres                 0.0.0.0/0               md5
) > temp_pg_hba.conf

REM Copy the temp pg_hba.conf into the container
docker cp temp_pg_hba.conf db:/var/lib/postgresql/data/pg_hba.conf

REM Clean up the temporary pg_hba.conf file from the host
del temp_pg_hba.conf

echo Restarting PostgreSQL to apply pg_hba.conf changes...
docker compose restart db

echo Waiting for database to restart (10 seconds)...
timeout /t 10 /nobreak > nul

echo Testing database connection...
echo \conninfo | docker compose exec -T db psql -U barcodeboachiefamily -d barcode_api

echo Testing permissions with a test table...
REM Create a temporary SQL file for test table operations
(
    echo CREATE TABLE IF NOT EXISTS test_table (id SERIAL PRIMARY KEY, name TEXT^);
    echo INSERT INTO test_table (name^) VALUES ('test'^);
    echo SELECT * FROM test_table;
) > temp_test_table.sql

REM Execute the SQL script for test table inside the container by piping its content
type temp_test_table.sql | docker compose exec -T db psql -U barcodeboachiefamily -d barcode_api

REM Clean up the temporary SQL file from the host
del temp_test_table.sql

echo Database has been reset and permissions fixed!
echo Now update your connection string to:
echo postgresql+asyncpg://barcodeboachiefamily:%DB_PASSWORD%@db:5432/barcode_api

endlocal
