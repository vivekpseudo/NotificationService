# Decoupled Notification System

A Django-based notification system designed with a modular architecture, separating event intake, notification processing, and delivery. Supports multiple channels (Email, Slack, In-App, Teams) and includes user preference management and rate limiting.

## Project Structure

*   **`traffic_control`**: Main Django project configuration.
*   **`event_intake`**: API to receive event payloads and publish them to the Message Queue.
*   **`notification_processor`**: Consumes events, formatting them and routing based on rules.
*   **`delivery_gateway`**: Handles actual delivery to external providers (stubbed).
*   **`user_preferences`**: Manages user channel settings.

## Getting Started

### Prerequisites

*   **Docker** and **Docker Compose** installed.
*   (Optional) Python 3.11+ for local development without Docker.

### Running with Docker (Recommended)

This sets up the full stack: Django (Web + Worker), PostgreSQL, Redis, and RabbitMQ.

1.  **Build and Start Services:**
    ```bash
    docker-compose up --build
    ```

2.  **Access the API:**
    The Event Intake API will be available at `http://localhost:8000/api/events/`.

3.  **Check Logs:**
    To see the processing flow (Intake -> Celery Worker -> Delivery), verify the logs:
    ```bash
    docker-compose logs -f worker
    ```

### Connecting to PostgreSQL

The PostgreSQL database is running in a Docker container named `db`.

**Credentials:**
*   **Host**: `localhost` (mapped port 5432) or `db` (internal Docker network)
*   **Port**: `5432`
*   **Username**: `postgres`
*   **Password**: `postgres`
*   **Database**: `notification_db`

**Connection URL:**
```
postgres://postgres:postgres@localhost:5432/notification_db
```

To connect via CLI:
```bash
docker-compose exec db psql -U postgres -d notification_db
```

### Running Locally (Without Docker)

For development or verification without the full container stack, the system is configured to fallback to **SQLite** and **Celery Eager Mode** (synchronous task execution).

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Apply Migrations:**
    ```bash
    # Set this to force eager mode
    export CELERY_TASK_ALWAYS_EAGER=True
    python manage.py migrate
    ```

3.  **Run Server:**
    ```bash
    export CELERY_TASK_ALWAYS_EAGER=True
    python manage.py runserver
    ```

4.  **Verify Flow:**
    Run the included verification script to simulate traffic:
    ```bash
    python verify_flow.py
    ```

## deployment

To deploy this system to a production environment (e.g., AWS, GCP, DigitalOcean):

1.  **Database**:
    *   Provision a managed PostgreSQL instance (e.g., AWS RDS).
    *   Update `DATABASE_URL` environment variable to point to the production DB.

2.  **Broker & Cache**:
    *   Provision a managed Redis or RabbitMQ instance (e.g., AWS ElastiCache, Amazon MQ).
    *   Update `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`.

3.  **Application (Web & Worker)**:
    *   Build the Docker image: `docker build -t notification-service .`
    *   Run containers (likely via Kubernetes/ECS) using the image.
    *   Ensure to set `DEBUG=0` and provide a proper `SECRET_KEY`.

4.  **Migrations**:
    *   Run migrations as part of the deployment pipeline or in an init container:
        ```bash
        python manage.py migrate
        ```

5.  **Run Server:**
    ```bash
    python manage.py runserver
    ```
## Documentation

The API documentation is available at `http://localhost:8000/swagger/`. 

The admin dashboard is available at `http://localhost:8000/admin/`. 

create superuser:
```bash
python manage.py createsuperuser
```

## OKR API integration and secure delivery

Set `OKR_NOTIFICATION_SHARED_SECRET` to the same random secret configured as `NOTIFICATION_SERVICE_SHARED_SECRET` in the OKR backend. The event intake endpoint validates `X-OKR-Timestamp` and `X-OKR-Signature` (HMAC-SHA256 over `timestamp + "." + raw request body`) and rejects requests older than five minutes. In production, a missing secret causes the intake endpoint to reject events. Do not expose this service publicly; use private networking and HTTPS.

For Slack delivery, set `SLACK_BOT_TOKEN` in the worker environment and configure each user's Slack destination as a channel ID (for example, `C012ABCDEF`). Grant the bot only the `chat:write` scope and invite it to the destination channel. For Microsoft Teams, configure the user preference destination as an HTTPS Teams Workflow/webhook URL on an approved Microsoft webhook host. Redirects are disabled to reduce SSRF risk. Credentials and webhook URLs must be treated as secrets; do not log them or commit them to Git.

Email and in-app adapters intentionally return failure until a real provider and persistence layer are configured. Do not advertise those channels as production-ready yet. For production deployment, replace Django's development server with a production WSGI/ASGI server, remove default database credentials, set `DEBUG=0`, and provision durable broker, monitoring, TLS, and retry/dead-letter policies.
