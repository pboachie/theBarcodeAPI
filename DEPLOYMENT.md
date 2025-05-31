# Deployment Process Documentation

## 1. CI/CD Overview

This project utilizes GitHub Actions for its CI/CD (Continuous Integration/Continuous Deployment) pipelines. Two main workflows manage the deployment and infrastructure setup:

*   **`application-cd.yml` (Application Deployment):**
    *   **Purpose:** This workflow is responsible for deploying updates to the frontend and backend applications. It handles code changes, builds, and deploys new versions to the server.
    *   **Triggers:**
        *   Automatically on push to the `main` branch.
        *   Manually via `workflow_dispatch` (allowing deployment from a specific branch if needed).

*   **`infra-ci.yml` (Infrastructure Setup):**
    *   **Purpose:** This workflow handles the initial setup and configuration of the server infrastructure. This includes installing dependencies (Nginx, Node.js, Docker, PM2), configuring system services, setting up directories, and preparing the environment for application deployment.
    *   **Triggers:**
        *   Manually via `workflow_dispatch`. This is typically run once for a new server or when significant infrastructure changes are required.

## 2. Workflows and Scripts

### 2.1. `application-cd.yml` - Application Deployment Workflow

This workflow orchestrates the deployment of both frontend and backend applications.

**Jobs:**

*   **`frontend-deployment`:**
    *   Determines the branch to deploy.
    *   Checks for changes in frontend-specific files.
    *   Validates necessary environment variables.
    *   Sets up Node.js and caches Next.js build artifacts.
    *   Installs dependencies and builds the frontend application.
    *   Deploys the frontend, manages PM2, and performs health checks with rollback capability.
*   **`backend-deployment`:**
    *   Runs after `frontend-deployment`.
    *   Determines the branch for backend code.
    *   Checks for changes in backend-specific files.
    *   Cleans and copies backend files to the deployment directory.
    *   Creates the `.env` file for backend services.
    *   Manages Docker Buildx cache for faster image builds.
    *   Builds (or uses cached) Docker images for backend services.
    *   Stores the Git commit hash for the current deployment.
    *   Sets up initial directories required by the backend.
    *   Deploys backend services using Docker Compose, including data backups and health checks.
    *   Runs database migrations.
    *   Verifies the backend deployment and performs cleanup.
*   **`final-verification`:**
    *   Runs after both frontend and backend deployments.
    *   Cleans up build artifacts from the runner workspace.
    *   Collects diagnostics and sends notifications if any part of the deployment failed.

**Key Scripts Used (from `scripts/` directory):**

*   **`check-frontend-changes.sh`:** Detects changes in frontend code to decide if a deployment is needed.
*   **`deploy-frontend.sh`:** Manages the frontend deployment lifecycle (new release, symlinks, PM2, health checks, rollback).
*   **`check-backend-changes.sh`:** Detects changes in backend code to decide if a deployment is needed.
*   **`create-backend-env-file.sh`:** Generates the `.env` file with necessary secrets and configurations for the backend services.
*   **`deploy-backend-docker.sh`:** Manages the backend Docker deployment (Docker Compose, data backups, health checks).
*   **`run-migrations.sh`:** Executes database migrations (Alembic) within the API container.

### 2.2. `infra-ci.yml` - Infrastructure Setup Workflow

This workflow prepares the server environment for the applications.

**Job:**

*   **`infra-ci-job`:**
    *   Checks out repository code.
    *   Sets up initial application directories on the server.
    *   (Optionally, a commented-out section for `sudoers` configuration exists but is disabled due to security risks).
    *   Sets up PM2 home directory and permissions for the runner user.
    *   Updates system packages.
    *   Installs essential system dependencies (Nginx, Node.js, PM2, Docker, Docker Compose).
    *   Creates a global `/tmp/env_vars` file to be sourced by subsequent scripts, centralizing environment variable access for this workflow run.
    *   Configures Nginx as a reverse proxy.
    *   Configures PM2 for managing the frontend application (including templating `ecosystem.config.js`).
    *   Configures the backend Docker environment:
        *   Copies backend application code to the deployment directory.
        *   Templates and creates `docker-compose.yml` and the backend `.env` file.
        *   Sets up `backup.sh` and `wait-for-it.sh` utility scripts.
    *   Fixes file and directory permissions across the application deployment paths.
    *   Configures backup coordination (creates `pre-backup-check.sh` and related cron job).
    *   Adds a cleanup routine (creates `cleanup.sh` and related cron job for old releases/backups and Docker prune).
    *   Verifies the overall setup, including critical file integrity and basic cron job installation checks.
    *   Verifies the basic repository structure for the backend.
    *   Starts/restarts Nginx and Docker services.
    *   Cleans up the temporary `/tmp/env_vars` file.

**Key Scripts Used (from `scripts/infra/` directory):**

*   **`update-system.sh`:** Updates system packages (`apt-get update && apt-get upgrade`).
*   **`install-dependencies.sh`:** Installs Nginx, Node.js, PM2, Docker, and Docker Compose.
*   **`configure-nginx.sh`:** Sets up Nginx site configuration as a reverse proxy.
*   **`configure-pm2.sh`:** Configures PM2 and templates the `ecosystem.config.js` for the frontend.
*   **`setup-docker-env.sh`:** Prepares the backend Docker environment, templates `docker-compose.yml`, backend `.env`, `backup.sh`, and `wait-for-it.sh`.
*   **`fix-permissions.sh`:** Standardizes file and directory permissions.
*   **`configure-backup-coordination.sh`:** Creates `pre-backup-check.sh` and its cron job.
*   **`add-cleanup-routine.sh`:** Creates `cleanup.sh` (for old releases/backups, Docker prune) and its cron job.
*   **`verify-setup.sh`:** Checks critical files, directories, permissions, and basic cron job setup.

## 3. Manual Triggers and Configuration

### 3.1. Manual Workflow Triggers (`workflow_dispatch`)

*   **`application-cd.yml`:**
    *   Can be triggered manually from the GitHub Actions UI.
    *   **Inputs:**
        *   `branch` (optional): Specify the branch to deploy. If not provided, it defaults to the branch where the workflow is initiated from (usually `main`).
*   **`infra-ci.yml`:**
    *   Can be triggered manually from the GitHub Actions UI.
    *   No specific inputs are defined for this workflow; it runs on the default branch (typically `main`).

### 3.2. Required GitHub Secrets and Variables

The following GitHub Actions secrets and variables **must** be configured in your repository/organization settings for the pipelines to function correctly:

**Secrets (Repository or Organization level):**

*   `DOMAIN_NAME`: The primary domain name for your application (e.g., `example.com`).
*   `SUDO_PASSWORD`: The sudo password for the self-hosted runner user. This is required for privileged operations during infrastructure setup and deployment.
*   `DB_PASSWORD`: The password for the main application database user (e.g., `barcodeboachiefamily`).
*   `POSTGRES_PASSWORD`: The password for the PostgreSQL superuser (`postgres`).
*   `API_SECRET_KEY`: A strong, unique secret key for JWT token generation and other security functions within your API.
*   `API_MASTER_KEY`: A master API key for administrative or high-privilege access to your API.

**Variables (Repository or Organization level):**

*   `ENVIRONMENT`: The deployment environment name (e.g., `staging`, `production`). This is used to segregate configurations, paths, and service names.
*   `API_VERSION`: The version of your API (e.g., `v1`). This is used in the backend `.env` file and can be useful for API versioning.

## 4. Further Recommendations

This CI/CD setup provides a solid foundation for automating deployments and infrastructure management. For future enhancements, consider the following:

*   **Advanced Secrets Management:**
    *   For enhanced security, especially in production environments, integrate a dedicated secrets management solution like HashiCorp Vault, AWS Secrets Manager, or Google Cloud Secret Manager instead of relying solely on GitHub Actions secrets for runtime configuration.

*   **Pipeline Testing & Validation:**
    *   **Local Testing with `act`:** Use tools like `act` to test GitHub Actions workflows locally. This can help catch syntax errors and basic logic issues before pushing to the repository.
    *   **Script Testing:** Develop a strategy for testing individual shell scripts, possibly using Docker to create consistent test environments or incorporating shell unit testing frameworks (e.g., `shunit2`, `bats`).
    *   **Integration/E2E Tests:** Add automated integration or end-to-end tests to the `application-cd.yml` workflow after deployment to ensure application health and functionality.

*   **Configuration Management (for `infra-ci.yml`):**
    *   For more complex infrastructure or managing multiple servers, consider using configuration management tools like Ansible, Chef, or Puppet. These tools can make the `infra-ci.yml` workflow more robust, declarative, and easier to maintain, especially for tasks like package installation, file templating, and service configuration. Ansible, in particular, has a lower learning curve and uses YAML like GitHub Actions.

*   **Security Hardening:**
    *   **Sudoers Review:** If the commented-out `sudoers` configuration in `infra-ci.yml` is ever considered for use, it **must** be thoroughly reviewed to grant only the absolute minimum necessary privileges (Principle of Least Privilege). Avoid broad, passwordless sudo access.
    *   **Runner Permissions:** Ensure the self-hosted runner user has the minimum necessary permissions on the server. Avoid running it as root.
    *   **Regular Audits:** Periodically audit security configurations, dependencies (using tools like `npm audit`, `safety` for Python), and access controls.
    *   **Network Security:** Implement firewall rules (e.g., `ufw`) to restrict access to necessary ports only.
    *   **HTTPS:** Ensure Nginx is configured to serve traffic over HTTPS using SSL/TLS certificates (e.g., from Let's Encrypt). The current Nginx config only sets up HTTP.

*   **Docker Image Tagging and Registry:**
    *   Instead of always using `barcodeapi:latest` (or relying on implicit latest), implement a more specific Docker image tagging strategy (e.g., using Git commit SHAs, semantic versioning).
    *   Push images to a private Docker registry (like Docker Hub private repos, GitHub Container Registry, AWS ECR, Google Artifact Registry) rather than just loading them locally on the runner. This allows for better version control, rollback to specific image versions, and sharing images across environments if needed.

*   **Monitoring, Logging, and Alerting:**
    *   Integrate comprehensive monitoring and logging solutions (e.g., Prometheus, Grafana, ELK stack, Datadog, Sentry).
    *   Set up alerts for critical errors, performance issues, or security events in both the application and infrastructure.
    *   Ensure application logs (frontend and backend) are properly managed, rotated, and accessible for debugging.

*   **Database Backup Robustness:**
    *   Verify backup integrity periodically by performing test restores.
    *   Consider off-server backups for disaster recovery (e.g., copying backups to cloud storage).

*   **Idempotency of Scripts:**
    *   Continue to ensure all scripts are as idempotent as possible, meaning they can be run multiple times with the same outcome without causing unintended side effects. This is crucial for reliable automation.
