from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import os

app=Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"]=os.getenv("SECRET_KEY","resolvehub-dev-secret-change-me")
app.config["SQLALCHEMY_DATABASE_URI"]="sqlite:///resolvehub.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"]=False
db=SQLAlchemy(app)

class User(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(100),nullable=False)
    email=db.Column(db.String(120),unique=True,nullable=False)
    password_hash=db.Column(db.String(255),nullable=False)
    role=db.Column(db.String(20),default="user")
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    requests=db.relationship("ServiceRequest",backref="user",lazy=True)
    def set_password(self,p): self.password_hash=generate_password_hash(p)
    def check_password(self,p): return check_password_hash(self.password_hash,p)

class ServiceRequest(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    subject=db.Column(db.String(180),nullable=False)
    description=db.Column(db.Text,nullable=False)
    request_type=db.Column(db.String(30),nullable=False)
    category=db.Column(db.String(50),nullable=False)
    priority=db.Column(db.String(20),default="Medium")
    status=db.Column(db.String(30),default="Submitted")
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    updated_at=db.Column(db.DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)
    user_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False)

def login_required(fn):
    @wraps(fn)
    def wrapper(*a,**kw):
        if "user_id" not in session: return jsonify({"error":"Authentication required"}),401
        return fn(*a,**kw)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*a,**kw):
        uid=session.get("user_id")
        if not uid: return jsonify({"error":"Authentication required"}),401
        if db.session.get(User,uid).role!="admin": return jsonify({"error":"Admin access required"}),403
        return fn(*a,**kw)
    return wrapper

def req_json(r):
    return {"id":r.id,"request_id":f"REQ-{1000+r.id}","subject":r.subject,"description":r.description,
            "request_type":r.request_type,"category":r.category,"priority":r.priority,"status":r.status,
            "created_at":r.created_at.strftime("%d %b %Y"),"updated_at":r.updated_at.strftime("%d %b %Y %H:%M")}

@app.get("/")
def home(): return render_template("index.html")

@app.post("/api/register")
def register():
    data=request.get_json() or {}
    name,email,password=data.get("name","").strip(),data.get("email","").strip().lower(),data.get("password","")
    if not name or not email or len(password)<6: return jsonify({"error":"Name, valid email and password of at least 6 characters are required"}),400
    if User.query.filter_by(email=email).first(): return jsonify({"error":"Email already registered"}),409
    u=User(name=name,email=email);u.set_password(password);db.session.add(u);db.session.commit()
    return jsonify({"message":"Account created successfully"}),201

@app.post("/api/login")
def login():
    data=request.get_json() or {}; u=User.query.filter_by(email=data.get("email","").lower()).first()
    if not u or not u.check_password(data.get("password","")): return jsonify({"error":"Invalid email or password"}),401
    session["user_id"]=u.id
    return jsonify({"message":"Login successful","user":{"id":u.id,"name":u.name,"email":u.email,"role":u.role}})

@app.post("/api/logout")
def logout(): session.clear(); return jsonify({"message":"Logged out"})

@app.get("/api/me")
@login_required
def me():
    u=db.session.get(User,session["user_id"]);return jsonify({"id":u.id,"name":u.name,"email":u.email,"role":u.role})

@app.get("/api/requests")
@login_required
def list_requests():
    u=db.session.get(User,session["user_id"])
    q=ServiceRequest.query if u.role=="admin" else ServiceRequest.query.filter_by(user_id=u.id)
    status=request.args.get("status");category=request.args.get("category");search=request.args.get("search","").lower()
    if status and status!="All": q=q.filter_by(status=status)
    if category and category!="All": q=q.filter_by(category=category)
    rows=q.order_by(ServiceRequest.created_at.desc()).all()
    if search: rows=[r for r in rows if search in (r.subject+" "+r.description+" "+r.category).lower()]
    return jsonify([req_json(r) for r in rows])

@app.post("/api/requests")
@login_required
def create_request():
    data=request.get_json() or {}
    required=["subject","description","request_type","category","priority"]
    if any(not data.get(x) for x in required): return jsonify({"error":"All request fields are required"}),400
    r=ServiceRequest(user_id=session["user_id"],**{x:data[x] for x in required})
    db.session.add(r);db.session.commit()
    return jsonify(req_json(r)),201

@app.get("/api/requests/<int:rid>")
@login_required
def get_request(rid):
    u=db.session.get(User,session["user_id"]);r=db.session.get(ServiceRequest,rid)
    if not r:return jsonify({"error":"Request not found"}),404
    if r.user_id!=u.id and u.role!="admin":return jsonify({"error":"Forbidden"}),403
    return jsonify(req_json(r))

@app.patch("/api/requests/<int:rid>")
@admin_required
def update_request(rid):
    r=db.session.get(ServiceRequest,rid)
    if not r:return jsonify({"error":"Request not found"}),404
    data=request.get_json() or {}
    for field in ["status","priority","category"]: 
        if field in data:r.__setattr__(field,data[field])
    db.session.commit();return jsonify(req_json(r))

@app.delete("/api/requests/<int:rid>")
@login_required
def delete_request(rid):
    u=db.session.get(User,session["user_id"]);r=db.session.get(ServiceRequest,rid)
    if not r:return jsonify({"error":"Request not found"}),404
    if r.user_id!=u.id and u.role!="admin":return jsonify({"error":"Forbidden"}),403
    db.session.delete(r);db.session.commit();return jsonify({"message":"Request deleted"})

@app.get("/api/admin/stats")
@admin_required
def stats():
    rows=ServiceRequest.query.all()
    by_status={s:sum(r.status==s for r in rows) for s in ["Submitted","In Progress","Resolved","Closed"]}
    by_category={c:sum(r.category==c for r in rows) for c in ["Technical","Facilities","Account","Other"]}
    return jsonify({"total":len(rows),"high_priority":sum(r.priority=="High" for r in rows),"by_status":by_status,"by_category":by_category,
                    "users":User.query.count()})

with app.app_context():
    db.create_all()
    if not User.query.filter_by(email="admin@resolvehub.local").first():
        a=User(name="System Admin",email="admin@resolvehub.local",role="admin");a.set_password("Admin@123");db.session.add(a);db.session.commit()

if __name__=="__main__": app.run(debug=True)
