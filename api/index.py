from flask import Flask, request, jsonify, session, render_template
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import os

app = Flask(
    __name__,
    template_folder="../templates",
    static_folder="../static"
)

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "resolvehub-dev-secret-change-me"
)

database_url = os.getenv("DATABASE_URL", "").strip()

if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = (
    database_url or "sqlite:///resolvehub_local.db"
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# =========================
# DATABASE MODELS
# =========================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="user")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    requests = db.relationship(
        "ServiceRequest",
        backref="user",
        lazy=True
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(
            self.password_hash,
            password
        )


class ServiceRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=False)
    request_type = db.Column(db.String(30), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    priority = db.Column(db.String(20), default="Medium")
    status = db.Column(db.String(30), default="Submitted")

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )


# =========================
# AUTHENTICATION
# =========================

def login_required(fn):

    @wraps(fn)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:
            return jsonify({
                "error": "Authentication required"
            }), 401

        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):

    @wraps(fn)
    def wrapper(*args, **kwargs):

        uid = session.get("user_id")

        if not uid:
            return jsonify({
                "error": "Authentication required"
            }), 401

        user = db.session.get(User, uid)

        if not user or user.role != "admin":
            return jsonify({
                "error": "Admin access required"
            }), 403

        return fn(*args, **kwargs)

    return wrapper


# =========================
# REQUEST SERIALIZER
# =========================

def req_json(r):

    return {
        "id": r.id,
        "request_id": f"REQ-{1000 + r.id}",
        "subject": r.subject,
        "description": r.description,
        "request_type": r.request_type,
        "category": r.category,
        "priority": r.priority,
        "status": r.status,
        "created_at": r.created_at.strftime("%d %b %Y"),
        "updated_at": r.updated_at.strftime("%d %b %Y %H:%M")
    }


# =========================
# HOME
# =========================

@app.get("/")
def home():
    return render_template("index.html")


# =========================
# REGISTER
# =========================

@app.post("/api/register")
def register():

    data = request.get_json() or {}

    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not name or not email or len(password) < 6:
        return jsonify({
            "error": "Name, valid email and password of at least 6 characters are required"
        }), 400

    if User.query.filter_by(email=email).first():
        return jsonify({
            "error": "Email already registered"
        }), 409

    user = User(
        name=name,
        email=email
    )

    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    return jsonify({
        "message": "Account created successfully"
    }), 201


# =========================
# LOGIN
# =========================

@app.post("/api/login")
def login():

    data = request.get_json() or {}

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return jsonify({
            "error": "Invalid email or password"
        }), 401

    session["user_id"] = user.id

    return jsonify({
        "message": "Login successful",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role
        }
    })


# =========================
# LOGOUT
# =========================

@app.post("/api/logout")
def logout():

    session.clear()

    return jsonify({
        "message": "Logged out"
    })


# =========================
# CURRENT USER
# =========================

@app.get("/api/me")
@login_required
def me():

    user = db.session.get(
        User,
        session["user_id"]
    )

    return jsonify({
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role
    })


# =========================
# LIST REQUESTS
# =========================

@app.get("/api/requests")
@login_required
def list_requests():

    user = db.session.get(
        User,
        session["user_id"]
    )

    if user.role == "admin":
        query = ServiceRequest.query
    else:
        query = ServiceRequest.query.filter_by(
            user_id=user.id
        )

    status = request.args.get("status")
    category = request.args.get("category")
    search = request.args.get(
        "search",
        ""
    ).lower()

    if status and status != "All":
        query = query.filter_by(
            status=status
        )

    if category and category != "All":
        query = query.filter_by(
            category=category
        )

    rows = query.order_by(
        ServiceRequest.created_at.desc()
    ).all()

    if search:

        rows = [
            r for r in rows
            if search in (
                r.subject
                + " "
                + r.description
                + " "
                + r.category
            ).lower()
        ]

    return jsonify([
        req_json(r)
        for r in rows
    ])


# =========================
# CREATE REQUEST
# =========================

@app.post("/api/requests")
@login_required
def create_request():

    data = request.get_json() or {}

    required = [
        "subject",
        "description",
        "request_type",
        "category",
        "priority"
    ]

    if any(not data.get(field) for field in required):

        return jsonify({
            "error": "All request fields are required"
        }), 400

    new_request = ServiceRequest(
        user_id=session["user_id"],
        **{
            field: data[field]
            for field in required
        }
    )

    db.session.add(new_request)
    db.session.commit()

    return jsonify(
        req_json(new_request)
    ), 201


# =========================
# GET SINGLE REQUEST
# =========================

@app.get("/api/requests/<int:rid>")
@login_required
def get_request(rid):

    user = db.session.get(
        User,
        session["user_id"]
    )

    service_request = db.session.get(
        ServiceRequest,
        rid
    )

    if not service_request:
        return jsonify({
            "error": "Request not found"
        }), 404

    if (
        service_request.user_id != user.id
        and user.role != "admin"
    ):
        return jsonify({
            "error": "Forbidden"
        }), 403

    return jsonify(
        req_json(service_request)
    )


# =========================
# UPDATE REQUEST - ADMIN
# =========================

@app.patch("/api/requests/<int:rid>")
@admin_required
def update_request(rid):

    service_request = db.session.get(
        ServiceRequest,
        rid
    )

    if not service_request:
        return jsonify({
            "error": "Request not found"
        }), 404

    data = request.get_json() or {}

    allowed_fields = [
        "status",
        "priority",
        "category"
    ]

    for field in allowed_fields:

        if field in data:
            setattr(
                service_request,
                field,
                data[field]
            )

    db.session.commit()

    return jsonify(
        req_json(service_request)
    )


# =========================
# DELETE REQUEST
# =========================

@app.delete("/api/requests/<int:rid>")
@login_required
def delete_request(rid):

    user = db.session.get(
        User,
        session["user_id"]
    )

    service_request = db.session.get(
        ServiceRequest,
        rid
    )

    if not service_request:
        return jsonify({
            "error": "Request not found"
        }), 404

    if (
        service_request.user_id != user.id
        and user.role != "admin"
    ):
        return jsonify({
            "error": "Forbidden"
        }), 403

    db.session.delete(service_request)
    db.session.commit()

    return jsonify({
        "message": "Request deleted"
    })


# =========================
# ADMIN DASHBOARD STATS
# =========================

@app.get("/api/admin/stats")
@admin_required
def stats():

    rows = ServiceRequest.query.all()

    status_list = [
        "Submitted",
        "In Progress",
        "Resolved",
        "Closed"
    ]

    category_list = [
        "Technical",
        "Facilities",
        "Account",
        "Other"
    ]

    by_status = {
        status: sum(
            r.status == status
            for r in rows
        )
        for status in status_list
    }

    by_category = {
        category: sum(
            r.category == category
            for r in rows
        )
        for category in category_list
    }

    return jsonify({
        "total": len(rows),
        "high_priority": sum(
            r.priority == "High"
            for r in rows
        ),
        "by_status": by_status,
        "by_category": by_category,
        "users": User.query.count()
    })


# =========================
# DATABASE INITIALIZATION
# =========================

def initialize_database():

    with app.app_context():

        db.create_all()

        admin_email = os.getenv(
            "ADMIN_EMAIL",
            "admin@resolvehub.local"
        )

        admin_password = os.getenv(
            "ADMIN_PASSWORD",
            "Admin@123"
        )

        existing_admin = User.query.filter_by(
            email=admin_email
        ).first()

        if not existing_admin:

            admin = User(
                name="System Admin",
                email=admin_email,
                role="admin"
            )

            admin.set_password(
                admin_password
            )

            db.session.add(admin)
            db.session.commit()


initialize_database()


# Local development only
if __name__ == "__main__":
    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000
    )