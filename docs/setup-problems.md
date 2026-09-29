# Backend Architecture Review

## Setup Problems and Resolutions

During the process of cloning, configuring, running, and testing the backend project, several setup and testing issues were encountered. The following problems were identified and resolved.

---

## 1. Database Configuration — SQLite to PostgreSQL

### Problem

Initially, the project used **SQLite** as the database during development and testing.

For the final setup, the project needed to use **PostgreSQL** instead of SQLite.

### Resolution

The database configuration was changed to PostgreSQL.

The following steps were completed:

* PostgreSQL was installed and started.
* A PostgreSQL database was configured for the project.
* PostgreSQL connection details were added to the `.env` file.
* Django was configured to read the PostgreSQL settings from environment variables.
* Django's database connection was verified successfully.
* Existing migrations were checked.
* All required migrations were successfully applied/verified.

### Result

The project is now running successfully with **PostgreSQL** as the database instead of SQLite.

---

## 2. Stale `ProfileView` Import in `config/urls.py`

### Problem

During the initial setup, running a Django management command resulted in an import error:

```text
ImportError: cannot import name 'ProfileView' from 'services.views'
```

The `config/urls.py` file contained a reference to `ProfileView`, but the current version of `services/views.py` did not contain that view.

### Resolution

The latest committed version of `config/urls.py` was restored.

Only the affected file was restored rather than restoring the entire project.

After the correction, the Django system check completed successfully:

```text
System check identified no issues (0 silenced).
```

### Result

The Django project was able to start correctly and management commands worked normally.

---

## 3. Redis Docker Container Conflict

### Problem

When attempting to start Redis using Docker Compose, Docker reported that the container name was already being used:

```text
Conflict. The container name "/notification-redis" is already in use
```

### Cause

A Redis container named `notification-redis` had already been created from previous project work.

### Resolution

The existing Docker container was checked instead of deleting it.

The container was already running and Redis was available on:

```text
127.0.0.1:6379
```

Therefore, the existing Redis container was reused.

### Result

Redis was successfully available for:

* Django Channels
* Celery
* Notifications
* Real-time WebSocket functionality

No new Redis container was required.

---

## 4. PowerShell API Testing Issues

### Problem

Several issues occurred while testing APIs directly from Windows PowerShell.

Commands using PowerShell tools such as:

```text
Invoke-WebRequest
Invoke-RestMethod
```

sometimes produced errors even though the Django API itself was working correctly.

The main issues included:

* PowerShell interpreting HTTP parameters differently from expected.
* Difficulty formatting request headers correctly.
* JSON request bodies requiring proper conversion.
* Authentication tokens needing to be passed correctly in request headers.
* PowerShell escaping and quoting issues.
* Errors caused by copying command output and accidentally pasting it back into the terminal.
* Commands written for other terminals/tools sometimes requiring different syntax in PowerShell.

### Resolution

PowerShell-compatible syntax was used for API requests.

For JSON request bodies, the data was converted using:

```powershell
ConvertTo-Json
```

For authenticated requests, the JWT access token was added to the `Authorization` header.

Postman was also used for API testing where it was easier to construct requests containing:

* JSON bodies
* Authorization headers
* JWT tokens
* File uploads
* Webhook headers

### Result

After correcting the PowerShell commands, the APIs were successfully tested.

The PowerShell issues were primarily **command-line testing and syntax issues**, rather than problems with the Django API implementation.

---

## 5. PostgreSQL Connection Verification

After changing the database from SQLite to PostgreSQL, the database connection needed to be verified.

### Resolution

Django management commands were used to confirm that Django could connect to the configured PostgreSQL database.

The migrations were successfully detected and verified.

### Result

The PostgreSQL database connection was confirmed to be working correctly.

---

## 6. Final Environment Verification

After resolving the setup problems, the following components were successfully verified:

| Component                    | Status    |
| ---------------------------- | --------- |
| Git repository               | Completed |
| Python virtual environment   | Completed |
| Dependencies                 | Completed |
| `.env` configuration         | Completed |
| PostgreSQL                   | Working   |
| Redis                        | Working   |
| Django                       | Working   |
| Database migrations          | Verified  |
| Authentication API           | Tested    |
| Profile API                  | Tested    |
| Services CRUD                | Tested    |
| Search / Filter / Pagination | Tested    |
| Booking API                  | Tested    |
| Payment API                  | Tested    |
| Payment Webhook              | Tested    |
| Notifications API            | Tested    |
| Celery notifications         | Verified  |
| Service Images               | Tested    |
| WebSocket / Real-time Status | Tested    |

---

## Conclusion

The project initially required several configuration and testing corrections, particularly the migration from **SQLite to PostgreSQL**, Redis container reuse, a stale `ProfileView` reference, and PowerShell API testing syntax.

All identified setup problems were resolved successfully.

The backend is now running correctly with **PostgreSQL, Redis, Celery, Django REST Framework, and Django Channels/WebSockets**, and the required API functionality has been tested successfully.
