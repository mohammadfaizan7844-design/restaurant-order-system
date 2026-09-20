import qrcode
import os
import time

from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME


# =========================
# FLASK APP
# =========================

app = Flask(__name__)

app.config["SECRET_KEY"] = "cafe_qr_secret_key"

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# =========================
# ADMIN REQUIRED FUNCTION
# =========================

def admin_required():
    return "admin_id" in session
def super_admin_required():
    return "super_admin_id" in session
@app.route("/super-admin/login", methods=["GET", "POST"])
def super_admin_login():

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        super_admin = db.session.execute(
            db.text("""
                SELECT *
                FROM super_admins
                WHERE username = :username
            """),
            {"username": username}
        ).mappings().first()

        if super_admin and check_password_hash(
            super_admin["password"],
            password
        ):
            session["super_admin_id"] = super_admin["id"]
            session["super_admin_name"] = super_admin["name"]

            return redirect(url_for("super_admin_dashboard"))

        return render_template(
            "super_admin/login.html",
            error="Invalid username or password"
        )

    return render_template("super_admin/login.html")
@app.route("/super-admin/dashboard")
def super_admin_dashboard():

    if not super_admin_required():
        return redirect(url_for("super_admin_login"))

    restaurants = db.session.execute(
        db.text("""
            SELECT
                r.id,
                r.name,
                r.phone,
                r.email,
                r.status,
                r.created_at,
                COUNT(a.id) AS admin_count
            FROM restaurants r
            LEFT JOIN admins a
                ON a.restaurant_id = r.id
            GROUP BY
                r.id, r.name, r.phone, r.email, r.created_at
            ORDER BY r.id DESC
        """)
    ).mappings().all()

    return render_template(
        "super_admin/dashboard.html",
        restaurants=restaurants,
        super_admin_name=session["super_admin_name"]
    )
@app.route("/super-admin/restaurants/add", methods=["GET", "POST"])
def add_restaurant():

    if not super_admin_required():
        return redirect(url_for("super_admin_login"))

    if request.method == "POST":

        restaurant_name = request.form["restaurant_name"].strip()
        owner_name = request.form["owner_name"].strip()
        username = request.form["username"].strip()
        password = request.form["password"]
        address = request.form["address"].strip()
        phone = request.form["phone"].strip()
        email = request.form["email"].strip()
        gst_number = request.form["gst_number"].strip()

        # Check username already exists
        existing_admin = db.session.execute(
            db.text("""
                SELECT id
                FROM admins
                WHERE username = :username
            """),
            {"username": username}
        ).first()

        if existing_admin:
            return render_template(
                "super_admin/add_restaurant.html",
                error="This admin username already exists."
            )

        try:
            # Create restaurant
            restaurant_result = db.session.execute(
                db.text("""
                    INSERT INTO restaurants
                    (name, address, phone, email, gst_number)
                    VALUES
                    (:name, :address, :phone, :email, :gst_number)
                """),
                {
                    "name": restaurant_name,
                    "address": address,
                    "phone": phone,
                    "email": email,
                    "gst_number": gst_number
                }
            )

            restaurant_id = restaurant_result.lastrowid

            # Create restaurant admin
            password_hash = generate_password_hash(password)

            db.session.execute(
                db.text("""
                    INSERT INTO admins
                    (restaurant_id, username, password, name)
                    VALUES
                    (:restaurant_id, :username, :password, :name)
                """),
                {
                    "restaurant_id": restaurant_id,
                    "username": username,
                    "password": password_hash,
                    "name": owner_name
                }
            )

            db.session.commit()

            return redirect(url_for("super_admin_dashboard"))

        except Exception as e:

            db.session.rollback()

            return render_template(
                "super_admin/add_restaurant.html",
                error="Unable to create restaurant. Please try again."
            )

    return render_template("super_admin/add_restaurant.html")
# Customer session timeout
CUSTOMER_SESSION_MINUTES = 20


def get_active_customer_session(restaurant_id, table_id):
    active_session = db.session.execute(
        db.text("""
            SELECT *
            FROM sessions
            WHERE restaurant_id = :restaurant_id
            AND table_id = :table_id
            AND status = 'ACTIVE'
            ORDER BY id DESC
            LIMIT 1
        """),
        {
            "restaurant_id": restaurant_id,
            "table_id": table_id
        }
    ).mappings().first()

    if not active_session:
        return None

    # Check 20-minute expiry
    started_at = active_session["started_at"]

    if started_at < datetime.now() - timedelta(
        minutes=CUSTOMER_SESSION_MINUTES
    ):
        db.session.execute(
            db.text("""
                UPDATE sessions
                SET
                    status = 'CLOSED',
                    closed_at = CURRENT_TIMESTAMP
                WHERE id = :session_id
            """),
            {
                "session_id": active_session["id"]
            }
        )

        db.session.commit()

        return None

    return active_session
    # =========================
# EDIT RESTAURANT
# =========================

@app.route(
    "/super-admin/restaurants/edit/<int:restaurant_id>",
    methods=["GET", "POST"]
)
def edit_restaurant(restaurant_id):

    if not super_admin_required():
        return redirect(url_for("super_admin_login"))

    restaurant = db.session.execute(
        db.text("""
            SELECT *
            FROM restaurants
            WHERE id = :restaurant_id
        """),
        {"restaurant_id": restaurant_id}
    ).mappings().first()

    if not restaurant:
        return "Restaurant not found", 404

    admin = db.session.execute(
        db.text("""
            SELECT *
            FROM admins
            WHERE restaurant_id = :restaurant_id
            LIMIT 1
        """),
        {"restaurant_id": restaurant_id}
    ).mappings().first()

    if request.method == "POST":

        restaurant_name = request.form["restaurant_name"].strip()
        owner_name = request.form["owner_name"].strip()
        address = request.form["address"].strip()
        phone = request.form["phone"].strip()
        email = request.form["email"].strip()
        gst_number = request.form["gst_number"].strip()

        db.session.execute(
            db.text("""
                UPDATE restaurants
                SET
                    name = :name,
                    address = :address,
                    phone = :phone,
                    email = :email,
                    gst_number = :gst_number
                WHERE id = :restaurant_id
            """),
            {
                "name": restaurant_name,
                "address": address,
                "phone": phone,
                "email": email,
                "gst_number": gst_number,
                "restaurant_id": restaurant_id
            }
        )

        if admin:
            db.session.execute(
                db.text("""
                    UPDATE admins
                    SET name = :name
                    WHERE restaurant_id = :restaurant_id
                """),
                {
                    "name": owner_name,
                    "restaurant_id": restaurant_id
                }
            )

        db.session.commit()

        return redirect(url_for("super_admin_dashboard"))

    return render_template(
        "super_admin/edit_restaurant.html",
        restaurant=restaurant,
        admin=admin
    )

# =========================
# ENABLE / DISABLE RESTAURANT
# =========================

@app.route(
    "/super-admin/restaurants/toggle/<int:restaurant_id>",
    methods=["POST"]
)
def toggle_restaurant(restaurant_id):

    if not super_admin_required():
        return redirect(url_for("super_admin_login"))

    restaurant = db.session.execute(
        db.text("""
            SELECT id, status
            FROM restaurants
            WHERE id = :restaurant_id
        """),
        {
            "restaurant_id": restaurant_id
        }
    ).mappings().first()

    if not restaurant:
        return "Restaurant not found", 404

    new_status = (
        "DISABLED"
        if restaurant["status"] == "ACTIVE"
        else "ACTIVE"
    )

    db.session.execute(
        db.text("""
            UPDATE restaurants
            SET status = :status
            WHERE id = :restaurant_id
        """),
        {
            "status": new_status,
            "restaurant_id": restaurant_id
        }
    )

    db.session.commit()

    return redirect(url_for("super_admin_dashboard"))

@app.route("/super-admin/logout")
def super_admin_logout():

    session.pop("super_admin_id", None)
    session.pop("super_admin_name", None)

    return redirect(url_for("super_admin_login"))

# =========================
# HOME
# =========================

@app.route("/")
def home():
    return redirect(url_for("login"))


# =========================
# LOGIN
# =========================



@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        admin = db.session.execute(
            db.text("""
                SELECT
                    a.*,
                    r.status AS restaurant_status
                FROM admins a
                JOIN restaurants r
                    ON r.id = a.restaurant_id
                WHERE a.username = :username
            """),
            {
                "username": username
            }
        ).mappings().first()

        # Username not found
        if not admin:
            return render_template(
                "admin/login.html",
                error="Invalid username or password"
            )

        # Restaurant disabled
        if admin["restaurant_status"] == "DISABLED":
            return render_template(
                "admin/login.html",
                error="This restaurant is currently disabled."
            )

        # Check password
        if not check_password_hash(
            admin["password"],
            password
        ):
            return render_template(
                "admin/login.html",
                error="Invalid username or password"
            )

        # Successful login
        session["admin_id"] = admin["id"]
        session["restaurant_id"] = admin["restaurant_id"]
        session["admin_name"] = admin["name"]

        return redirect(url_for("dashboard"))

    return render_template("admin/login.html")


# =========================
# DASHBOARD
# =========================

@app.route("/admin/dashboard")
def dashboard():

    if not admin_required():
        return redirect(url_for("login"))

    restaurant_id = session["restaurant_id"]

    restaurant = db.session.execute(
        db.text("""
            SELECT *
            FROM restaurants
            WHERE id = :restaurant_id
        """),
        {
            "restaurant_id": restaurant_id
        }
    ).mappings().first()

    menu_count = db.session.execute(
        db.text("""
            SELECT COUNT(*) AS total
            FROM menu_items
            WHERE restaurant_id = :restaurant_id
        """),
        {
            "restaurant_id": restaurant_id
        }
    ).scalar()

    table_count = db.session.execute(
        db.text("""
            SELECT COUNT(*) AS total
            FROM cafe_tables
            WHERE restaurant_id = :restaurant_id
        """),
        {
            "restaurant_id": restaurant_id
        }
    ).scalar()

    order_count = db.session.execute(
        db.text("""
            SELECT COUNT(*) AS total
            FROM orders
            WHERE restaurant_id = :restaurant_id
            AND status NOT IN ('COMPLETED', 'CANCELLED')
        """),
        {
            "restaurant_id": restaurant_id
        }
    ).scalar()

    return render_template(
        "admin/dashboard.html",
        restaurant=restaurant,
        admin_name=session["admin_name"],
        menu_count=menu_count,
        table_count=table_count,
        order_count=order_count
    )


# =========================
# RESTAURANT SETTINGS
# =========================

@app.route("/admin/settings", methods=["GET", "POST"])
def settings():

    if not admin_required():
        return redirect(url_for("login"))

    restaurant_id = session["restaurant_id"]

    if request.method == "POST":

        name = request.form["name"]
        address = request.form["address"]
        phone = request.form["phone"]
        email = request.form["email"]
        gst_number = request.form["gst_number"]

        # -------------------------
        # RESTAURANT LOGO
        # -------------------------
        logo = request.files.get("logo")

        if logo and logo.filename:
            import os
            from werkzeug.utils import secure_filename

            filename = secure_filename(logo.filename)

            # Save logo in static/images
            logo_folder = os.path.join(
                app.root_path,
                "static",
                "images"
            )

            os.makedirs(logo_folder, exist_ok=True)

            logo_path = os.path.join(
                logo_folder,
                filename
            )

            # Save new logo
            logo.save(logo_path)

            # Get old logo
            old_restaurant = db.session.execute(
                db.text("""
                    SELECT logo
                    FROM restaurants
                    WHERE id = :restaurant_id
                """),
                {
                    "restaurant_id": restaurant_id
                }
            ).mappings().first()

            old_logo = old_restaurant["logo"] if old_restaurant else None

            # Update database with new logo
            db.session.execute(
                db.text("""
                    UPDATE restaurants
                    SET logo = :logo
                    WHERE id = :restaurant_id
                """),
                {
                    "logo": filename,
                    "restaurant_id": restaurant_id
                }
            )

            # Delete old logo if different
            if old_logo and old_logo != filename:
                old_logo_path = os.path.join(
                    logo_folder,
                    old_logo
                )

                if os.path.exists(old_logo_path):
                    os.remove(old_logo_path)

        # -------------------------
        # RESTAURANT INFORMATION
        # -------------------------
        db.session.execute(
            db.text("""
                UPDATE restaurants
                SET
                    name = :name,
                    address = :address,
                    phone = :phone,
                    email = :email,
                    gst_number = :gst_number
                WHERE id = :restaurant_id
            """),
            {
                "name": name,
                "address": address,
                "phone": phone,
                "email": email,
                "gst_number": gst_number,
                "restaurant_id": restaurant_id
            }
        )

        db.session.commit()

        return redirect(url_for("settings"))

    restaurant = db.session.execute(
        db.text("""
            SELECT *
            FROM restaurants
            WHERE id = :restaurant_id
        """),
        {
            "restaurant_id": restaurant_id
        }
    ).mappings().first()

    return render_template(
        "admin/settings.html",
        restaurant=restaurant
    )
# =========================
# CHANGE ADMIN PASSWORD
# =========================

@app.route("/admin/change-password", methods=["GET", "POST"])
def change_password():

    if not admin_required():
        return redirect(url_for("login"))

    admin_id = session["admin_id"]

    if request.method == "POST":

        current_password = request.form["current_password"]
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        # Get current admin
        admin = db.session.execute(
            db.text("""
                SELECT *
                FROM admins
                WHERE id = :admin_id
            """),
            {
                "admin_id": admin_id
            }
        ).mappings().first()

        # Check current password
        if not admin or not check_password_hash(
            admin["password"],
            current_password
        ):
            return render_template(
                "admin/change_password.html",
                error="Current password is incorrect."
            )

        # Check new password
        if new_password != confirm_password:
            return render_template(
                "admin/change_password.html",
                error="New passwords do not match."
            )

        if len(new_password) < 6:
            return render_template(
                "admin/change_password.html",
                error="Password must be at least 6 characters."
            )

        # Generate new password hash
        new_password_hash = generate_password_hash(new_password)

        # Update password
        db.session.execute(
            db.text("""
                UPDATE admins
                SET password = :password
                WHERE id = :admin_id
            """),
            {
                "password": new_password_hash,
                "admin_id": admin_id
            }
        )

        db.session.commit()

        return render_template(
            "admin/change_password.html",
            success="Password changed successfully."
        )

    return render_template("admin/change_password.html")
# =========================
# MENU MANAGEMENT
# =========================

@app.route("/admin/menu")
def menu():

    if not admin_required():
        return redirect(url_for("login"))

    restaurant_id = session["restaurant_id"]

    menu_items = db.session.execute(
        db.text("""
            SELECT *
            FROM menu_items
            WHERE restaurant_id = :restaurant_id
            ORDER BY id DESC
        """),
        {
            "restaurant_id": restaurant_id
        }
    ).mappings().all()

    return render_template(
        "admin/menu.html",
        menu_items=menu_items
    )


# =========================
# ADD MENU ITEM
# =========================

@app.route("/admin/menu/add", methods=["POST"])
def add_menu():

    if not admin_required():
        return redirect(url_for("login"))

    restaurant_id = session["restaurant_id"]

    name = request.form["name"]
    category = request.form["category"]
    description = request.form["description"]
    price = request.form["price"]

    db.session.execute(
        db.text("""
            INSERT INTO menu_items
            (
                restaurant_id,
                name,
                category,
                description,
                price,
                available
            )
            VALUES
            (
                :restaurant_id,
                :name,
                :category,
                :description,
                :price,
                TRUE
            )
        """),
        {
            "restaurant_id": restaurant_id,
            "name": name,
            "category": category,
            "description": description,
            "price": price
        }
    )

    db.session.commit()

    return redirect(url_for("menu"))


# =========================
# DELETE MENU ITEM
# =========================

@app.route("/admin/menu/delete/<int:item_id>")
def delete_menu(item_id):

    if not admin_required():
        return redirect(url_for("login"))

    restaurant_id = session["restaurant_id"]

    db.session.execute(
        db.text("""
            DELETE FROM menu_items
            WHERE id = :item_id
            AND restaurant_id = :restaurant_id
        """),
        {
            "item_id": item_id,
            "restaurant_id": restaurant_id
        }
    )

    db.session.commit()

    return redirect(url_for("menu"))


# =========================
# TOGGLE MENU AVAILABILITY
# =========================

@app.route("/admin/menu/toggle/<int:item_id>")
def toggle_menu(item_id):

    if not admin_required():
        return redirect(url_for("login"))

    restaurant_id = session["restaurant_id"]

    db.session.execute(
        db.text("""
            UPDATE menu_items
            SET available = NOT available
            WHERE id = :item_id
            AND restaurant_id = :restaurant_id
        """),
        {
            "item_id": item_id,
            "restaurant_id": restaurant_id
        }
    )

    db.session.commit()

    return redirect(url_for("menu"))


# =========================
# TABLE MANAGEMENT
# =========================

@app.route("/admin/tables")
def tables():

    if not admin_required():
        return redirect(url_for("login"))

    restaurant_id = session["restaurant_id"]

    tables = db.session.execute(
        db.text("""
            SELECT *
            FROM cafe_tables
            WHERE restaurant_id = :restaurant_id
            ORDER BY table_number
        """),
        {
            "restaurant_id": restaurant_id
        }
    ).mappings().all()

    return render_template(
        "admin/tables.html",
        tables=tables
    )


# =========================
# ADD TABLE
# =========================

@app.route("/admin/tables/add", methods=["POST"])
def add_table():

    if not admin_required():
        return redirect(url_for("login"))

    restaurant_id = session["restaurant_id"]

    table_number = request.form["table_number"]

    existing_table = db.session.execute(
        db.text("""
            SELECT id
            FROM cafe_tables
            WHERE restaurant_id = :restaurant_id
            AND table_number = :table_number
        """),
        {
            "restaurant_id": restaurant_id,
            "table_number": table_number
        }
    ).first()

    if existing_table:
        return redirect(url_for("tables"))

    db.session.execute(
        db.text("""
            INSERT INTO cafe_tables
            (
                restaurant_id,
                table_number,
                status
            )
            VALUES
            (
                :restaurant_id,
                :table_number,
                'AVAILABLE'
            )
        """),
        {
            "restaurant_id": restaurant_id,
            "table_number": table_number
        }
    )

    db.session.commit()

    return redirect(url_for("tables"))


# =========================
# DELETE TABLE
# =========================

@app.route("/admin/tables/delete/<int:table_id>")
def delete_table(table_id):

    if not admin_required():
        return redirect(url_for("login"))

    restaurant_id = session["restaurant_id"]

    db.session.execute(
        db.text("""
            DELETE FROM cafe_tables
            WHERE id = :table_id
            AND restaurant_id = :restaurant_id
        """),
        {
            "table_id": table_id,
            "restaurant_id": restaurant_id
        }
    )

    db.session.commit()

    return redirect(url_for("tables"))


# =========================
# GENERATE TABLE QR
# =========================

@app.route("/admin/tables/qr/<int:table_id>")
def generate_table_qr(table_id):

    if not admin_required():
        return redirect(url_for("login"))

    restaurant_id = session["restaurant_id"]

    table = db.session.execute(
        db.text("""
            SELECT *
            FROM cafe_tables
            WHERE id = :table_id
            AND restaurant_id = :restaurant_id
        """),
        {
            "table_id": table_id,
            "restaurant_id": restaurant_id
        }
    ).mappings().first()

    if not table:
        return "Table not found", 404

    menu_url = (
        f"https://restaurant-order-system-production-df75.up.railway.app/menu"
        f"?restaurant={restaurant_id}"
        f"&table={table['table_number']}"
    )

    qr_folder = os.path.join(
        "static",
        "qr"
    )

    os.makedirs(
        qr_folder,
        exist_ok=True
    )

    qr_filename = (
        f"restaurant_{restaurant_id}"
        f"_table_{table['table_number']}.png"
    )

    qr_path = os.path.join(
        qr_folder,
        qr_filename
    )

    qr = qrcode.make(menu_url)

    qr.save(qr_path)

    return render_template(
        "admin/qr.html",
        table=table,
        qr_filename=qr_filename,
        menu_url=menu_url
    )


# =========================
# CUSTOMER MENU
# =========================

@app.route("/menu")
def customer_menu():

    restaurant_id = request.args.get("restaurant")
    table_number = request.args.get("table")

    if not restaurant_id or not table_number:
        return "Invalid QR Code", 400

    # Get restaurant
    restaurant = db.session.execute(
        db.text("""
            SELECT *
            FROM restaurants
            WHERE id = :restaurant_id
        """),
        {
            "restaurant_id": restaurant_id
        }
    ).mappings().first()

    if not restaurant:
        return "Restaurant not found", 404

    # Check restaurant status
    if restaurant["status"] == "DISABLED":
        return "This restaurant is currently unavailable.", 403

    # Get table
    table = db.session.execute(
        db.text("""
            SELECT *
            FROM cafe_tables
            WHERE restaurant_id = :restaurant_id
            AND table_number = :table_number
        """),
        {
            "restaurant_id": restaurant_id,
            "table_number": table_number
        }
    ).mappings().first()

    if not table:
        return "Table not found", 404

    # ==========================================
    # CREATE / REUSE 20-MINUTE CUSTOMER SESSION
    # ==========================================

    active_session = get_active_customer_session(
        restaurant_id,
        table["id"]
    )

    # If no active session OR previous session expired
    if not active_session:

        result = db.session.execute(
            db.text("""
                INSERT INTO sessions
                (
                    restaurant_id,
                    table_id,
                    status
                )
                VALUES
                (
                    :restaurant_id,
                    :table_id,
                    'ACTIVE'
                )
            """),
            {
                "restaurant_id": restaurant_id,
                "table_id": table["id"]
            }
        )

        db.session.commit()

        session_id = result.lastrowid

        # Get newly created session
        active_session = db.session.execute(
            db.text("""
                SELECT *
                FROM sessions
                WHERE id = :session_id
            """),
            {
                "session_id": session_id
            }
        ).mappings().first()

    # Save customer session in browser
    session["customer_session_id"] = active_session["id"]
    session["customer_restaurant_id"] = int(restaurant_id)
    session["customer_table_id"] = table["id"]

    # ==========================================
    # GET AVAILABLE MENU ITEMS
    # ==========================================

    menu_items = db.session.execute(
        db.text("""
            SELECT *
            FROM menu_items
            WHERE restaurant_id = :restaurant_id
            AND available = TRUE
            ORDER BY category, name
        """),
        {
            "restaurant_id": restaurant_id
        }
    ).mappings().all()

    # ==========================================
    # SHOW CUSTOMER MENU
    # ==========================================

    return render_template(
        "customer/menu.html",
        restaurant=restaurant,
        table=table,
        menu_items=menu_items
    )

# =========================
# ADD TO CART
# =========================

@app.route("/cart/add", methods=["POST"])
def add_to_cart():

    restaurant_id = request.form["restaurant_id"]
    table_number = request.form["table_number"]
    item_id = request.form["item_id"]

    # Check 20-minute customer session
    customer_session_id = session.get("customer_session_id")
    customer_restaurant_id = session.get("customer_restaurant_id")
    customer_table_id = session.get("customer_table_id")

    if not customer_session_id:
        session.pop("cart", None)
        return "Customer session expired. Please scan the QR code again.", 403

    if (
        customer_restaurant_id != int(restaurant_id)
        or customer_table_id is None
    ):
        session.pop("cart", None)
        return "Invalid customer session. Please scan the QR code again.", 403

    # Check that the session is still active and within 20 minutes
    active_session = db.session.execute(
        db.text("""
            SELECT *
            FROM sessions
            WHERE id = :session_id
            AND restaurant_id = :restaurant_id
            AND table_id = :table_id
            AND status = 'ACTIVE'
            LIMIT 1
        """),
        {
            "session_id": customer_session_id,
            "restaurant_id": restaurant_id,
            "table_id": customer_table_id
        }
    ).mappings().first()

    if not active_session:
        session.pop("cart", None)
        return "Customer session expired. Please scan the QR code again.", 403

    if active_session["started_at"] < datetime.now() - timedelta(
        minutes=CUSTOMER_SESSION_MINUTES
    ):
        db.session.execute(
            db.text("""
                UPDATE sessions
                SET
                    status = 'CLOSED',
                    closed_at = CURRENT_TIMESTAMP
                WHERE id = :session_id
            """),
            {
                "session_id": customer_session_id
            }
        )

        db.session.commit()

        session.pop("cart", None)

        return "Customer session expired. Please scan the QR code again.", 403

    # Check menu item
    item = db.session.execute(
        db.text("""
            SELECT *
            FROM menu_items
            WHERE id = :item_id
            AND restaurant_id = :restaurant_id
            AND available = TRUE
        """),
        {
            "item_id": item_id,
            "restaurant_id": restaurant_id
        }
    ).mappings().first()

    if not item:
        return "Item not found", 404

    cart = session.get("cart", [])

    # Cart belongs to one restaurant/table
    if cart:
        first = cart[0]

        if (
            first.get("restaurant_id") != int(restaurant_id)
            or first.get("table_number") != int(table_number)
        ):
            session.pop("cart", None)
            cart = []

    found = False

    for cart_item in cart:

        if (
            cart_item["item_id"] == int(item_id)
            and cart_item["restaurant_id"] == int(restaurant_id)
            and cart_item["table_number"] == int(table_number)
        ):
            cart_item["quantity"] += 1
            found = True
            break

    if not found:

        cart.append({
            "item_id": item["id"],
            "name": item["name"],
            "price": float(item["price"]),
            "quantity": 1,
            "restaurant_id": int(restaurant_id),
            "table_number": int(table_number)
        })

    session["cart"] = cart

    return redirect(
        url_for(
            "customer_menu",
            restaurant=restaurant_id,
            table=table_number
        )
    )
# =========================
# CART
# =========================

@app.route("/cart")
def cart():

    cart = session.get("cart", [])

    total = 0

    for item in cart:

        item["subtotal"] = (
            item["price"] *
            item["quantity"]
        )

        total += item["subtotal"]

    restaurant_id = cart[0]["restaurant_id"] if cart else request.args.get("restaurant")
    table_number = cart[0]["table_number"] if cart else request.args.get("table")

    return render_template(
        "customer/cart.html",
        cart=cart,
        total=total,
        restaurant_id=restaurant_id,
        table_number=table_number
    )


# =========================
# REMOVE CART ITEM
# =========================

@app.route("/cart/remove/<int:item_id>")
def remove_from_cart(item_id):

    cart = session.get("cart", [])

    cart = [
        item
        for item in cart
        if item["item_id"] != item_id
    ]

    session["cart"] = cart

    return redirect(url_for("cart"))


# =========================
# CLEAR CART
# =========================

@app.route("/cart/clear")
def clear_cart():

    session.pop("cart", None)

    return redirect(url_for("cart"))


# =========================
# PLACE ORDER
# =========================

@app.route("/place-order", methods=["POST"])
def place_order():

    cart = session.get("cart", [])

    if not cart:
        return "Cart is empty", 400

    restaurant_id = int(cart[0]["restaurant_id"])
    table_number = int(cart[0]["table_number"])

    # =========================
    # CHECK TABLE
    # =========================

    table = db.session.execute(
        db.text("""
            SELECT *
            FROM cafe_tables
            WHERE restaurant_id = :restaurant_id
            AND table_number = :table_number
        """),
        {
            "restaurant_id": restaurant_id,
            "table_number": table_number
        }
    ).mappings().first()

    if not table:
        return "Table not found", 404

    table_id = table["id"]

    # =========================
    # FIND ACTIVE SESSION
    # =========================

    active_session = db.session.execute(
        db.text("""
            SELECT *
            FROM sessions
            WHERE restaurant_id = :restaurant_id
            AND table_id = :table_id
            AND status = 'ACTIVE'
            ORDER BY id DESC
            LIMIT 1
        """),
        {
            "restaurant_id": restaurant_id,
            "table_id": table_id
        }
    ).mappings().first()

    # =========================
    # CREATE SESSION
    # =========================

    if active_session:

        session_id = active_session["id"]

    else:

        db.session.execute(
            db.text("""
                INSERT INTO sessions
                (
                    restaurant_id,
                    table_id,
                    status
                )
                VALUES
                (
                    :restaurant_id,
                    :table_id,
                    'ACTIVE'
                )
            """),
            {
                "restaurant_id": restaurant_id,
                "table_id": table_id
            }
        )

        session_id = db.session.execute(
            db.text("SELECT LAST_INSERT_ID()")
        ).scalar()

    # =========================
    # CALCULATE TOTAL
    # =========================

    total_amount = 0.0
    verified_items = []

    for cart_item in cart:

        item_id = int(cart_item["item_id"])
        quantity = int(cart_item["quantity"])

        if quantity <= 0:
            continue

        # Get latest price directly from database
        item = db.session.execute(
            db.text("""
                SELECT id, name, price
                FROM menu_items
                WHERE id = :item_id
                AND restaurant_id = :restaurant_id
                AND available = TRUE
            """),
            {
                "item_id": item_id,
                "restaurant_id": restaurant_id
            }
        ).mappings().first()

        if not item:
            db.session.rollback()
            return f"Menu item '{cart_item['name']}' is not available.", 400

        price = float(item["price"])
        subtotal = price * quantity

        total_amount += subtotal

        verified_items.append({
            "id": item["id"],
            "name": item["name"],
            "price": price,
            "quantity": quantity,
            "subtotal": subtotal
        })

    # Make sure total is not zero
    if total_amount <= 0:
        db.session.rollback()
        return "Order total cannot be zero.", 400

    # =========================
    # ORDER NUMBER
    # =========================

    order_number = "ORD-" + str(int(time.time()))

    # =========================
    # CREATE ORDER
    # =========================

    db.session.execute(
        db.text("""
            INSERT INTO orders
            (
                restaurant_id,
                session_id,
                table_id,
                order_number,
                status,
                total_amount
            )
            VALUES
            (
                :restaurant_id,
                :session_id,
                :table_id,
                :order_number,
                'NEW',
                :total_amount
            )
        """),
        {
            "restaurant_id": restaurant_id,
            "session_id": session_id,
            "table_id": table_id,
            "order_number": order_number,
            "total_amount": total_amount
        }
    )

    order_id = db.session.execute(
        db.text("SELECT LAST_INSERT_ID()")
    ).scalar()

    # =========================
    # CREATE ORDER ITEMS
    # =========================

    for item in verified_items:

        db.session.execute(
            db.text("""
                INSERT INTO order_items
                (
                    order_id,
                    menu_item_id,
                    quantity,
                    price,
                    subtotal
                )
                VALUES
                (
                    :order_id,
                    :menu_item_id,
                    :quantity,
                    :price,
                    :subtotal
                )
            """),
            {
                "order_id": order_id,
                "menu_item_id": item["id"],
                "quantity": item["quantity"],
                "price": item["price"],
                "subtotal": item["subtotal"]
            }
        )

    # =========================
    # PAYMENT PENDING
    # =========================

    db.session.execute(
        db.text("""
            INSERT INTO payments
            (
                order_id,
                payment_method,
                amount,
                status
            )
            VALUES
            (
                :order_id,
                'CASH',
                :amount,
                'PENDING'
            )
        """),
        {
            "order_id": order_id,
            "amount": total_amount
        }
    )

    # =========================
    # TABLE OCCUPIED
    # =========================

    db.session.execute(
        db.text("""
            UPDATE cafe_tables
            SET status = 'OCCUPIED'
            WHERE id = :table_id
            AND restaurant_id = :restaurant_id
        """),
        {
            "table_id": table_id,
            "restaurant_id": restaurant_id
        }
    )

    # =========================
    # SAVE EVERYTHING
    # =========================

    db.session.commit()

    # Clear cart
    session.pop("cart", None)

    # =========================
    # ORDER SUCCESS
    # =========================

    return render_template(
        "customer/order_success.html",
        order_number=order_number,
        total=total_amount,
        table_number=table_number,
        restaurant_id=restaurant_id
    )

# =========================
# ADMIN ORDERS
# =========================

@app.route("/admin/orders")
def admin_orders():

    if not admin_required():
        return redirect(url_for("login"))

    restaurant_id = session["restaurant_id"]

    orders = db.session.execute(
        db.text("""
            SELECT
                o.id,
                o.order_number,
                o.status,
                o.total_amount,
                o.created_at,
                ct.table_number
            FROM orders o
            JOIN cafe_tables ct
                ON o.table_id = ct.id
            WHERE o.restaurant_id = :restaurant_id
            ORDER BY o.created_at DESC
        """),
        {
            "restaurant_id": restaurant_id
        }
    ).mappings().all()

    return render_template(
        "admin/orders.html",
        orders=orders
    )


# =========================
# ADMIN ORDER DETAIL
# =========================

@app.route("/admin/orders/<int:order_id>")
def admin_order_detail(order_id):

    if not admin_required():
        return redirect(url_for("login"))

    restaurant_id = session["restaurant_id"]

    order = db.session.execute(
        db.text("""
            SELECT
                o.*,
                ct.table_number
            FROM orders o
            JOIN cafe_tables ct
                ON o.table_id = ct.id
            WHERE o.id = :order_id
            AND o.restaurant_id = :restaurant_id
        """),
        {
            "order_id": order_id,
            "restaurant_id": restaurant_id
        }
    ).mappings().first()

    if not order:
        return "Order not found", 404

    order_items = db.session.execute(
        db.text("""
            SELECT
                oi.*,
                mi.name
            FROM order_items oi
            JOIN menu_items mi
                ON oi.menu_item_id = mi.id
            WHERE oi.order_id = :order_id
        """),
        {
            "order_id": order_id
        }
    ).mappings().all()

    payment = db.session.execute(
        db.text("""
            SELECT *
            FROM payments
            WHERE order_id = :order_id
            ORDER BY id DESC
            LIMIT 1
        """),
        {
            "order_id": order_id
        }
    ).mappings().first()

    return render_template(
        "admin/order_detail.html",
        order=order,
        order_items=order_items,
        payment=payment
    )


# =========================
# UPDATE ORDER STATUS
# =========================

@app.route(
    "/admin/orders/status/<int:order_id>",
    methods=["POST"]
)
def update_order_status(order_id):

    if not admin_required():
        return redirect(url_for("login"))

    restaurant_id = session["restaurant_id"]

    status = request.form["status"]

    allowed_statuses = [
        "NEW",
        "PREPARING",
        "READY",
        "SERVED",
        "CANCELLED"
    ]

    if status not in allowed_statuses:
        return "Invalid status", 400

    db.session.execute(
        db.text("""
            UPDATE orders
            SET status = :status
            WHERE id = :order_id
            AND restaurant_id = :restaurant_id
        """),
        {
            "status": status,
            "order_id": order_id,
            "restaurant_id": restaurant_id
        }
    )

    db.session.commit()

    return redirect(
        url_for(
            "admin_order_detail",
            order_id=order_id
        )
    )
# =========================
# BILL / INVOICE
# =========================

@app.route("/admin/orders/<int:order_id>/bill")
def generate_bill(order_id):

    if not admin_required():
        return redirect(url_for("login"))

    restaurant_id = session["restaurant_id"]

    order = db.session.execute(
        db.text("""
            SELECT
                o.*,
                ct.table_number,
                r.name AS restaurant_name,
                r.address,
                r.phone,
                r.email,
                r.gst_number
            FROM orders o
            JOIN cafe_tables ct
                ON o.table_id = ct.id
            JOIN restaurants r
                ON o.restaurant_id = r.id
            WHERE o.id = :order_id
            AND o.restaurant_id = :restaurant_id
        """),
        {
            "order_id": order_id,
            "restaurant_id": restaurant_id
        }
    ).mappings().first()

    if not order:
        return "Order not found", 404

    order_items = db.session.execute(
        db.text("""
            SELECT
                oi.quantity,
                oi.price,
                oi.subtotal,
                mi.name
            FROM order_items oi
            JOIN menu_items mi
                ON oi.menu_item_id = mi.id
            WHERE oi.order_id = :order_id
        """),
        {
            "order_id": order_id
        }
    ).mappings().all()

    payment = db.session.execute(
        db.text("""
            SELECT *
            FROM payments
            WHERE order_id = :order_id
            ORDER BY id DESC
            LIMIT 1
        """),
        {
            "order_id": order_id
        }
    ).mappings().first()

    return render_template(
        "admin/bill.html",
        order=order,
        order_items=order_items,
        payment=payment
    )


# =========================
# UPDATE PAYMENT
# =========================

@app.route(
    "/admin/orders/<int:order_id>/payment",
    methods=["POST"]
)
def update_payment(order_id):

    if not admin_required():
        return redirect(url_for("login"))

    restaurant_id = session["restaurant_id"]

    payment_method = request.form["payment_method"]

    if payment_method not in ["CASH", "UPI", "CARD"]:
        return "Invalid payment method", 400

    order = db.session.execute(
        db.text("""
            SELECT *
            FROM orders
            WHERE id = :order_id
            AND restaurant_id = :restaurant_id
        """),
        {
            "order_id": order_id,
            "restaurant_id": restaurant_id
        }
    ).mappings().first()

    if not order:
        return "Order not found", 404

    db.session.execute(
        db.text("""
            UPDATE payments
            SET
                payment_method = :payment_method,
                status = 'PAID',
                paid_at = CURRENT_TIMESTAMP
            WHERE order_id = :order_id
        """),
        {
            "payment_method": payment_method,
            "order_id": order_id
        }
    )

    db.session.commit()

    return redirect(
        url_for(
            "generate_bill",
            order_id=order_id
        )
    )


# =========================
# CLEAR TABLE
# =========================

@app.route(
    "/admin/orders/<int:order_id>/clear-table",
    methods=["POST"]
)
def clear_table(order_id):

    if not admin_required():
        return redirect(url_for("login"))

    restaurant_id = session["restaurant_id"]

    # =========================
    # GET ORDER
    # =========================

    order = db.session.execute(
        db.text("""
            SELECT *
            FROM orders
            WHERE id = :order_id
            AND restaurant_id = :restaurant_id
        """),
        {
            "order_id": order_id,
            "restaurant_id": restaurant_id
        }
    ).mappings().first()

    if not order:
        return "Order not found", 404

    # =========================
    # CHECK PAYMENT
    # =========================

    payment = db.session.execute(
        db.text("""
            SELECT *
            FROM payments
            WHERE order_id = :order_id
            AND status = 'PAID'
            LIMIT 1
        """),
        {
            "order_id": order_id
        }
    ).mappings().first()

    if not payment:
        return "Payment is not completed", 400

    # =========================
    # COMPLETE ONLY THIS ORDER
    # =========================

    db.session.execute(
        db.text("""
            UPDATE orders
            SET status = 'COMPLETED'
            WHERE id = :order_id
            AND restaurant_id = :restaurant_id
        """),
        {
            "order_id": order_id,
            "restaurant_id": restaurant_id
        }
    )

    # =========================
    # CHECK OTHER ORDERS
    # IN SAME SESSION
    # =========================

    pending_orders = db.session.execute(
        db.text("""
            SELECT COUNT(*) AS total
            FROM orders
            WHERE session_id = :session_id
            AND restaurant_id = :restaurant_id
            AND id != :order_id
            AND status NOT IN ('COMPLETED', 'CANCELLED')
        """),
        {
            "session_id": order["session_id"],
            "restaurant_id": restaurant_id,
            "order_id": order_id
        }
    ).scalar()

    # =========================
    # IF OTHER ORDERS EXIST
    # KEEP TABLE OCCUPIED
    # =========================

    if pending_orders > 0:

        db.session.commit()

        return redirect(
            url_for("admin_orders")
        )

    # =========================
    # NO OTHER ORDERS
    # NOW CLOSE SESSION
    # =========================

    db.session.execute(
        db.text("""
            UPDATE sessions
            SET
                status = 'CLOSED',
                closed_at = CURRENT_TIMESTAMP
            WHERE id = :session_id
            AND restaurant_id = :restaurant_id
        """),
        {
            "session_id": order["session_id"],
            "restaurant_id": restaurant_id
        }
    )

    # =========================
    # MAKE TABLE AVAILABLE
    # =========================

    db.session.execute(
        db.text("""
            UPDATE cafe_tables
            SET status = 'AVAILABLE'
            WHERE id = :table_id
            AND restaurant_id = :restaurant_id
        """),
        {
            "table_id": order["table_id"],
            "restaurant_id": restaurant_id
        }
    )

    db.session.commit()

    return redirect(
        url_for("admin_orders")
    )
# =========================
# LOGOUT
# =========================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# =========================
# DATABASE TEST
# =========================

@app.route("/db-test")
def db_test():

    try:

        db.session.execute(
            db.text("SELECT 1")
        )

        return "MySQL Database Connected Successfully!"

    except Exception as e:

        return f"Database Connection Error: {e}"


# =========================
# RUN
# =========================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)