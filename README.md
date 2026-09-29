# ResolveHub — Full-Stack Online Complaint & Service Request Management System

## Resume-grade implementation
This version upgrades the static portfolio UI into a functional full-stack application.

### Stack
- Frontend: HTML5, CSS3, JavaScript
- Backend: Python Flask
- Database: SQLite with SQLAlchemy ORM
- Security: password hashing + session authentication
- Authorization: user/admin role checks
- API: REST-style JSON endpoints
- CRUD: create, read, update, delete requests
- Dashboard: live request statistics and filtering

### Features
1. User registration and login
2. Password hashing
3. Session-based authentication
4. User request submission
5. Request categories and priorities
6. Request status lifecycle
7. Search and status filtering
8. User-only request visibility
9. Admin-only request updates and analytics API
10. SQLite persistence
11. Responsive professional UI

## Run in VS Code / Windows

Open a terminal inside `backend`:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open:
http://127.0.0.1:5000

### Admin demo
Email: `admin@resolvehub.local`
Password: `Admin@123`

For a real deployment, change the admin password and SECRET_KEY.

## Suggested resume description
**Online Complaint & Service Request Management System** — Developed a full-stack Flask and SQLite application with secure user authentication, role-based access, request CRUD operations, categorization, priority/status tracking, filtering, and an admin analytics dashboard. Implemented REST-style APIs and SQLAlchemy ORM for persistent request management.

## Stronger next upgrades
- JWT authentication / refresh tokens
- PostgreSQL
- Email notifications
- File/attachment upload
- Admin assignment to support staff
- SLA / response-time tracking
- Pagination
- Audit logs
- Unit/API tests
- Deployment on Render/Railway
