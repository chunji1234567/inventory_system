# PostgreSQL Setup

1. Install PostgreSQL 14+ on your machine/server and ensure the service is running (`brew install postgresql@15`, `apt install postgresql`, etc.).
2. Create a dedicated database & user:
   ```bash
   createuser --interactive --pwprompt inventory_user
   createdb -O inventory_user inventory_db
   ```
3. Create `.env` (or update your environment variables) and set:
   ```
   POSTGRES_DB=inventory_db
   POSTGRES_USER=inventory_user
   POSTGRES_PASSWORD=your_password
   POSTGRES_HOST=127.0.0.1
   POSTGRES_PORT=5432
   # optional: DATABASE_URL=postgres://inventory_user:your_password@127.0.0.1:5432/inventory_db
   ```
4. Install dependencies and run migrations:
   ```bash
   pip install -r requirements.txt
   python manage.py migrate
   ```
5. Start the server (`python manage.py runserver` or gunicorn) and confirm you can log in.

For production, point the env vars (or `DATABASE_URL`) at your managed PostgreSQL instance and keep `psycopg2-binary` installed.
