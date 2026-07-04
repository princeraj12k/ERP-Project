"""
=================================================================
  BEVERAGE MANUFACTURING ERP — Flask Web Application
  File: app.py
  Run: python app.py
  Open Browser: http://localhost:5000
=================================================================
"""

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import json, os, hashlib, datetime, re, secrets, smtplib
from email.message import EmailMessage
from ml_model import get_sales_forecast, get_demand_clusters, get_anomalies

app = Flask(__name__)
app.secret_key = "bev_erp_secret_2024"

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
ADMIN_EMAIL = "princeraj12k@gmail.com"

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def load(file):
    path = os.path.join(DATA_DIR, file)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []

def save(file, data):
    with open(os.path.join(DATA_DIR, file), "w") as f:
        json.dump(data, f, indent=4)

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def today():
    return datetime.date.today().strftime("%Y-%m-%d")

def username_from_name(name):
    username = re.sub(r"[^a-z0-9]", "", name.lower())
    return username or "user"

def unique_username(name, users):
    base = username_from_name(name)
    existing = {u["username"] for u in users}
    username = base
    count = 2
    while username in existing:
        username = f"{base}{count}"
        count += 1
    return username

def sales_permission_for(user):
    if user.get("role") == "Admin":
        return True
    users = load("users.json")
    saved = next((u for u in users if u["username"] == user["username"]), user)
    return bool(saved.get("can_update_sales", False))

def email_config():
    config = load("email_config.json")
    if isinstance(config, dict):
        return config
    return {}

def send_admin_email(subject, body):
    config = email_config()
    host = os.environ.get("SMTP_HOST") or config.get("smtp_host") or "smtp.gmail.com"
    port = int(os.environ.get("SMTP_PORT") or config.get("smtp_port") or "587")
    smtp_user = os.environ.get("SMTP_USER") or config.get("smtp_user") or ADMIN_EMAIL
    smtp_password = os.environ.get("SMTP_PASSWORD") or os.environ.get("GMAIL_APP_PASSWORD") or config.get("smtp_password")
    sender = os.environ.get("SMTP_FROM") or config.get("smtp_from") or smtp_user or ADMIN_EMAIL

    if not smtp_password:
        print("\n" + "="*50)
        print("EMAIL NOT SENT - Gmail app password is not configured")
        print(f"To: {ADMIN_EMAIL}")
        print(f"Subject: {subject}")
        print(body)
        print("="*50 + "\n")
        return False

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ADMIN_EMAIL
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, port) as smtp:
            smtp.starttls()
            smtp.login(smtp_user, smtp_password)
            smtp.send_message(msg)
        return True
    except Exception as exc:
        print("\n" + "="*50)
        print("EMAIL NOT SENT - SMTP error")
        print(f"To: {ADMIN_EMAIL}")
        print(f"Subject: {subject}")
        print(f"Error: {exc}")
        print(body)
        print("="*50 + "\n")
        return False

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

# ─────────────────────────────────────────────
#  SEED DEFAULT USERS
# ─────────────────────────────────────────────

def seed_users():
    users = load("users.json")
    if not users:
        save("users.json", [
            {"user_id":"USR001","username":"admin","password":hash_pw("admin123"),"full_name":"System Administrator","role":"Admin","is_active":True,"can_update_sales":True},
            {"user_id":"USR002","username":"manager","password":hash_pw("manager123"),"full_name":"Production Manager","role":"Manager","is_active":True,"can_update_sales":False},
            {"user_id":"USR003","username":"staff","password":hash_pw("staff123"),"full_name":"Floor Staff","role":"Staff","is_active":True,"can_update_sales":False},
        ])

def seed_demo_data():
    # Inventory
    if not load("inventory.json"):
        save("inventory.json", [
            {"item_id":"RM001","name":"Mango Pulp","quantity":12,"unit":"kg","min_stock":50,"supplier":"FreshFarm Co.","last_updated":today()},
            {"item_id":"RM002","name":"Sugar","quantity":240,"unit":"kg","min_stock":100,"supplier":"SweetSupply","last_updated":today()},
            {"item_id":"RM003","name":"Water","quantity":1800,"unit":"litre","min_stock":500,"supplier":"AquaSource","last_updated":today()},
            {"item_id":"RM004","name":"Glass Bottles","quantity":0,"unit":"pcs","min_stock":200,"supplier":"PackPro","last_updated":today()},
            {"item_id":"RM005","name":"Citric Acid","quantity":65,"unit":"kg","min_stock":30,"supplier":"ChemBase","last_updated":today()},
            {"item_id":"RM006","name":"Bottle Caps","quantity":420,"unit":"pcs","min_stock":300,"supplier":"PackPro","last_updated":today()},
        ])
    # Production
    if not load("production.json"):
        save("production.json", [
            {"order_id":"PO0035","product":"Mango Juice 1L","batch_size":500,"raw_material":"Mango Pulp","qty_required":50,"start_date":"2024-07-15","end_date":"2024-07-18","supervisor":"Rajesh K.","status":"In Progress","created_on":today()},
            {"order_id":"PO0034","product":"Cola 500ml","batch_size":800,"raw_material":"Sugar","qty_required":80,"start_date":"2024-07-12","end_date":"2024-07-15","supervisor":"Priya M.","status":"Completed","created_on":today()},
            {"order_id":"PO0033","product":"Water 1L","batch_size":1200,"raw_material":"Water","qty_required":1200,"start_date":"2024-07-10","end_date":"2024-07-13","supervisor":"Rahul S.","status":"Completed","created_on":today()},
            {"order_id":"PO0032","product":"Energy Drink","batch_size":300,"raw_material":"Citric Acid","qty_required":30,"start_date":"2024-07-08","end_date":"2024-07-18","supervisor":"Ajay T.","status":"Delayed","created_on":today()},
        ])
    # Sales
    if not load("sales.json"):
        save("sales.json", [
            {"order_id":"SO0089","customer":"Metro Retail","product":"Mango Juice 1L","quantity":200,"price_per_unit":122.5,"total_amount":24500,"delivery_date":"2024-07-20","status":"Pending","order_date":today()},
            {"order_id":"SO0088","customer":"FreshMart","product":"Cola 500ml","quantity":500,"price_per_unit":36,"total_amount":18000,"delivery_date":"2024-07-18","status":"Dispatched","order_date":today()},
            {"order_id":"SO0087","customer":"QuickStore","product":"Water 1L","quantity":1000,"price_per_unit":12,"total_amount":12000,"delivery_date":"2024-07-16","status":"Delivered","order_date":today()},
            {"order_id":"SO0086","customer":"StarMart","product":"Energy Drink","quantity":150,"price_per_unit":150,"total_amount":22500,"delivery_date":"2024-07-14","status":"Delivered","order_date":today()},
            {"order_id":"SO0085","customer":"BigBazaar","product":"Mango Juice 1L","quantity":300,"price_per_unit":120,"total_amount":36000,"delivery_date":"2024-07-12","status":"Cancelled","order_date":today()},
        ])
    # Employees
    if not load("employees.json"):
        save("employees.json", [
            {"emp_id":"EMP001","name":"Rajesh Kumar","department":"Production","role":"Supervisor","basic_salary":45000,"phone":"9876543210","join_date":"2021-01-10"},
            {"emp_id":"EMP002","name":"Priya Mehta","department":"Sales","role":"Sales Executive","basic_salary":38000,"phone":"9876543211","join_date":"2022-03-15"},
            {"emp_id":"EMP003","name":"Ajay Tiwari","department":"Production","role":"Operator","basic_salary":28000,"phone":"9876543212","join_date":"2022-06-01"},
            {"emp_id":"EMP004","name":"Sunita Rao","department":"HR","role":"HR Manager","basic_salary":52000,"phone":"9876543213","join_date":"2020-09-20"},
            {"emp_id":"EMP005","name":"Manoj Singh","department":"Warehouse","role":"Store Keeper","basic_salary":25000,"phone":"9876543214","join_date":"2023-02-05"},
        ])
    # Warehouse
    if not load("warehouse.json"):
        save("warehouse.json", [
            {"stock_id":"WH001","item_name":"Mango Juice 1L","category":"Finished Goods","quantity":320,"unit":"cases","location":"Aisle A1","reorder_level":120,"last_updated":today()},
            {"stock_id":"WH002","item_name":"Cola 500ml","category":"Finished Goods","quantity":540,"unit":"cases","location":"Aisle A2","reorder_level":180,"last_updated":today()},
            {"stock_id":"WH003","item_name":"Glass Bottles","category":"Packaging","quantity":900,"unit":"pcs","location":"Rack P1","reorder_level":500,"last_updated":today()},
            {"stock_id":"WH004","item_name":"Bottle Caps","category":"Packaging","quantity":160,"unit":"pcs","location":"Rack P2","reorder_level":300,"last_updated":today()},
            {"stock_id":"WH005","item_name":"Sugar","category":"Raw Material","quantity":85,"unit":"kg","location":"Cold Store C1","reorder_level":100,"last_updated":today()},
        ])

# ─────────────────────────────────────────────
#  AUTH ROUTES
# ─────────────────────────────────────────────

@app.route("/", methods=["GET","POST"])
def login_page():
    error = None
    message = request.args.get("message")
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","").strip()
        users = load("users.json")
        hashed = hash_pw(password)
        for u in users:
            if u["username"] == username and u["password"] == hashed and u["is_active"]:
                session["user"] = u
                return redirect(url_for("dashboard"))
        error = "Invalid username or password. Please try again."
    return render_template("login.html", error=error, message=message)

@app.route("/forgot-password", methods=["POST"])
def forgot_password():
    username = request.form.get("username", "").strip()
    users = load("users.json")
    user = next((u for u in users if u["username"] == username and u.get("is_active", True)), None)
    if user:
        token = secrets.token_urlsafe(24)
        requests = load("password_reset_requests.json")
        reset_link = url_for("reset_password", token=token, _external=True)
        requests.append({
            "token": token,
            "username": username,
            "requested_on": datetime.datetime.now().isoformat(timespec="seconds"),
            "used": False,
            "reset_link": reset_link,
            "email_sent": False
        })
        save("password_reset_requests.json", requests)
        email_sent = send_admin_email(
            "BevERP password reset request",
            f"Password reset requested for {user['full_name']} ({username}).\n\nReset link: {reset_link}"
        )
        requests[-1]["email_sent"] = email_sent
        save("password_reset_requests.json", requests)
        if email_sent:
            return redirect(url_for("login_page", message="Password reset link sent to admin email."))
        return redirect(url_for("login_page", message="Password reset request submitted. Please contact Admin."))
    return redirect(url_for("login_page", message="If the username exists, a reset request was created."))

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    requests = load("password_reset_requests.json")
    reset_request = next((r for r in requests if r["token"] == token and not r.get("used")), None)
    if not reset_request:
        return render_template("login.html", error="This reset link is invalid or already used.", message=None)

    if request.method == "POST":
        new_password = request.form.get("password", "").strip()
        if len(new_password) < 6:
            return render_template("login.html", error="Password must be at least 6 characters.", message=None)
        users = load("users.json")
        for user in users:
            if user["username"] == reset_request["username"]:
                user["password"] = hash_pw(new_password)
                break
        reset_request["used"] = True
        save("users.json", users)
        save("password_reset_requests.json", requests)
        return redirect(url_for("login_page", message="Password updated. You can log in now."))

    default_password = f"{reset_request['username']}123"
    return render_template("login.html", error=None, message=f"Reset password for {reset_request['username']}. Suggested: {default_password}", reset_token=token, default_password=default_password)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

# ─────────────────────────────────────────────
#  DASHBOARD
# ─────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    inventory  = load("inventory.json")
    sales      = load("sales.json")
    production = load("production.json")
    employees  = load("employees.json")
    warehouse  = load("warehouse.json")
    users      = load("users.json")
    reset_requests = load("password_reset_requests.json")
    mail_config = email_config()

    total_revenue = sum(s["total_amount"] for s in sales if s["status"] == "Delivered")
    open_orders   = len([s for s in sales if s["status"] in ["Pending","Confirmed"]])
    inv_value     = sum(i["quantity"] for i in inventory)
    prod_output   = sum(p["batch_size"] for p in production if p["status"] == "Completed")
    low_stock     = [i for i in inventory if i["quantity"] <= i["min_stock"]]
    warehouse_qty = sum(w["quantity"] for w in warehouse)
    warehouse_low = [w for w in warehouse if w["quantity"] <= w["reorder_level"]]
    warehouse_locations = len({w["location"] for w in warehouse})
    can_update_sales = sales_permission_for(session["user"])

    return render_template("dashboard.html",
        user=session["user"],
        total_revenue=total_revenue,
        open_orders=open_orders,
        inv_value=inv_value,
        prod_output=prod_output,
        low_stock=low_stock,
        inventory=inventory,
        sales=sales,
        production=production,
        employees=employees,
        warehouse=warehouse,
        warehouse_qty=warehouse_qty,
        warehouse_low=warehouse_low,
        warehouse_locations=warehouse_locations,
        users=users,
        admin_email=ADMIN_EMAIL,
        can_update_sales=can_update_sales,
        reset_requests=reset_requests,
        mail_configured=bool(mail_config.get("smtp_password") or os.environ.get("SMTP_PASSWORD") or os.environ.get("GMAIL_APP_PASSWORD")),
        mail_user=mail_config.get("smtp_user", ADMIN_EMAIL),
    )

# ─────────────────────────────────────────────
#  INVENTORY ROUTES
# ─────────────────────────────────────────────

@app.route("/inventory/add", methods=["POST"])
@login_required
def add_inventory():
    inv = load("inventory.json")
    item = {
        "item_id":    request.form["item_id"],
        "name":       request.form["name"],
        "quantity":   float(request.form["quantity"]),
        "unit":       request.form["unit"],
        "min_stock":  float(request.form["min_stock"]),
        "supplier":   request.form["supplier"],
        "last_updated": today()
    }
    inv.append(item)
    save("inventory.json", inv)
    return redirect(url_for("dashboard") + "#inventory")

@app.route("/inventory/delete/<item_id>")
@login_required
def delete_inventory(item_id):
    inv = [i for i in load("inventory.json") if i["item_id"] != item_id]
    save("inventory.json", inv)
    return redirect(url_for("dashboard") + "#inventory")

# ─────────────────────────────────────────────
#  SALES ROUTES
# ─────────────────────────────────────────────

@app.route("/warehouse/add", methods=["POST"])
@login_required
def add_warehouse_stock():
    stocks = load("warehouse.json")
    stock = {
        "stock_id":      f"WH{str(len(stocks)+1).zfill(3)}",
        "item_name":     request.form["item_name"],
        "category":      request.form["category"],
        "quantity":      float(request.form["quantity"]),
        "unit":          request.form["unit"],
        "location":      request.form["location"],
        "reorder_level": float(request.form["reorder_level"]),
        "last_updated":  today()
    }
    stocks.append(stock)
    save("warehouse.json", stocks)
    return redirect(url_for("dashboard") + "#warehouse")

@app.route("/warehouse/delete/<stock_id>")
@login_required
def delete_warehouse_stock(stock_id):
    stocks = [s for s in load("warehouse.json") if s["stock_id"] != stock_id]
    save("warehouse.json", stocks)
    return redirect(url_for("dashboard") + "#warehouse")

@app.route("/users/add", methods=["POST"])
@login_required
def add_user_access():
    if session["user"]["role"] != "Admin":
        return redirect(url_for("dashboard"))
    users = load("users.json")
    full_name = request.form["full_name"].strip()
    username = unique_username(full_name, users)
    password = f"{username}123"
    users.append({
        "user_id": f"USR{str(len(users)+1).zfill(3)}",
        "username": username,
        "password": hash_pw(password),
        "full_name": full_name,
        "role": request.form["role"],
        "is_active": True,
        "can_update_sales": request.form.get("can_update_sales") == "on"
    })
    save("users.json", users)
    return redirect(url_for("dashboard", created_user=username, created_password=password) + "#access")

@app.route("/users/sales-permission", methods=["POST"])
@login_required
def update_sales_permission():
    if session["user"]["role"] != "Admin":
        return redirect(url_for("dashboard"))
    username = request.form["username"]
    allow = request.form.get("can_update_sales") == "on"
    users = load("users.json")
    for user in users:
        if user["username"] == username and user["role"] != "Admin":
            user["can_update_sales"] = allow
            break
    save("users.json", users)
    return redirect(url_for("dashboard") + "#access")

@app.route("/email-settings/save", methods=["POST"])
@login_required
def save_email_settings():
    if session["user"]["role"] != "Admin":
        return redirect(url_for("dashboard"))
    smtp_user = request.form.get("smtp_user", ADMIN_EMAIL).strip() or ADMIN_EMAIL
    smtp_password = request.form.get("smtp_password", "").strip()
    current = email_config()
    config = {
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_user": smtp_user,
        "smtp_from": smtp_user,
        "smtp_password": smtp_password or current.get("smtp_password", "")
    }
    save("email_config.json", config)
    return redirect(url_for("dashboard", email_settings="saved") + "#access")

@app.route("/email-settings/test", methods=["POST"])
@login_required
def test_email_settings():
    if session["user"]["role"] != "Admin":
        return redirect(url_for("dashboard"))
    sent = send_admin_email(
        "BevERP email test",
        "This is a test email from BevERP. Password reset emails will use the same Gmail settings."
    )
    status = "sent" if sent else "failed"
    return redirect(url_for("dashboard", email_test=status) + "#access")

@app.route("/sales/add", methods=["POST"])
@login_required
def add_sales():
    if not sales_permission_for(session["user"]):
        return redirect(url_for("dashboard") + "#sales")
    orders = load("sales.json")
    qty   = int(request.form["quantity"])
    price = float(request.form["price_per_unit"])
    order = {
        "order_id":      f"SO{str(len(orders)+1).zfill(4)}",
        "customer":      request.form["customer"],
        "product":       request.form["product"],
        "quantity":      qty,
        "price_per_unit":price,
        "total_amount":  qty * price,
        "delivery_date": request.form["delivery_date"],
        "status":        "Pending",
        "order_date":    today()
    }
    orders.append(order)
    save("sales.json", orders)
    return redirect(url_for("dashboard") + "#sales")

@app.route("/sales/update/<order_id>", methods=["POST"])
@login_required
def update_sales_order(order_id):
    if not sales_permission_for(session["user"]):
        return redirect(url_for("dashboard") + "#sales")
    allowed_statuses = {"Pending", "Confirmed", "Dispatched", "Delivered", "Cancelled"}
    status = request.form.get("status")
    if status not in allowed_statuses:
        return redirect(url_for("dashboard") + "#sales")
    orders = load("sales.json")
    for order in orders:
        if order["order_id"] == order_id:
            order["status"] = status
            break
    save("sales.json", orders)
    return redirect(url_for("dashboard") + "#sales")

# ─────────────────────────────────────────────
#  PRODUCTION ROUTES
# ─────────────────────────────────────────────

@app.route("/production/add", methods=["POST"])
@login_required
def add_production():
    orders = load("production.json")
    order = {
        "order_id":     f"PO{str(len(orders)+1).zfill(4)}",
        "product":      request.form["product"],
        "batch_size":   int(request.form["batch_size"]),
        "raw_material": request.form["raw_material"],
        "qty_required": float(request.form["qty_required"]),
        "start_date":   request.form["start_date"],
        "end_date":     request.form["end_date"],
        "supervisor":   request.form["supervisor"],
        "status":       "Planned",
        "created_on":   today()
    }
    orders.append(order)
    save("production.json", orders)
    return redirect(url_for("dashboard") + "#production")

# ─────────────────────────────────────────────
#  HR ROUTES
# ─────────────────────────────────────────────

@app.route("/hr/add", methods=["POST"])
@login_required
def add_employee():
    employees = load("employees.json")
    emp = {
        "emp_id":      f"EMP{str(len(employees)+1).zfill(3)}",
        "name":        request.form["name"],
        "department":  request.form["department"],
        "role":        request.form["role"],
        "basic_salary":float(request.form["basic_salary"]),
        "phone":       request.form["phone"],
        "join_date":   request.form["join_date"]
    }
    employees.append(emp)
    save("employees.json", employees)
    return redirect(url_for("dashboard") + "#hr")

# ─────────────────────────────────────────────
#  ML API ROUTES
# ─────────────────────────────────────────────

@app.route("/api/ml/forecast")
@login_required
def ml_forecast():
    sales = load("sales.json")
    result = get_sales_forecast(sales)
    return jsonify(result)

@app.route("/api/ml/clusters")
@login_required
def ml_clusters():
    sales = load("sales.json")
    result = get_demand_clusters(sales)
    return jsonify(result)

@app.route("/api/ml/anomalies")
@login_required
def ml_anomalies():
    sales = load("sales.json")
    result = get_anomalies(sales)
    return jsonify(result)

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    seed_users()
    seed_demo_data()
    print("\n" + "="*50)
    print("  🥤 Beverage ERP — Starting Web Server")
    print("  Open browser: http://localhost:5000")
    print("  Login: admin / admin123")
    print("="*50 + "\n")
    app.run(debug=True, port=5000)
