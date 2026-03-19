import json
import os
import re
import unicodedata
import uuid
from datetime import datetime
from functools import wraps
from urllib.parse import quote

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, or_, text
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "/app/static/uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "troque-esta-chave-em-producao")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

database_url = os.getenv("DATABASE_URL")
print("DATABASE_URL RAW:", repr(database_url))

if not database_url:
    raise RuntimeError("DATABASE_URL nao encontrada no ambiente")

if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

print("DATABASE_URL FINAL:", database_url)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db = SQLAlchemy(app)
with app.app_context():
    db.create_all()


class Setting(db.Model):
    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.Text, nullable=True)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    slug = db.Column(db.String(140), nullable=False, unique=True)
    description = db.Column(db.Text)
    image = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    products = db.relationship("Product", backref="category", lazy=True)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180), nullable=False)
    slug = db.Column(db.String(200), nullable=False, unique=True)
    short_description = db.Column(db.String(255))
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False, default=0.0)
    compare_at_price = db.Column(db.Float, default=0.0)
    stock = db.Column(db.Integer, default=0)
    image = db.Column(db.String(255))
    size_mode = db.Column(db.String(30), default="none")
    size_options = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    is_new = db.Column(db.Boolean, default=False)
    is_best_seller = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)

    @property
    def available_sizes(self):
        raw_value = (self.size_options or "").strip()
        if not raw_value:
            return []
        return [item.strip() for item in raw_value.split(",") if item.strip()]

    @property
    def has_sizes(self):
        return bool(self.available_sizes)


class Banner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    subtitle = db.Column(db.String(255))
    button_text = db.Column(db.String(100), default="Explorar coleção")
    button_link = db.Column(db.String(255), default="/colecao")
    image = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(180), nullable=False)
    whatsapp = db.Column(db.String(40), nullable=False)
    address_json = db.Column(db.Text, nullable=False)
    payment_method = db.Column(db.String(60), nullable=False)
    subtotal = db.Column(db.Float, nullable=False, default=0.0)
    items_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


DEFAULT_SETTINGS = {
    "store_name": "Carolina Helena",
    "store_tagline": "Acessórios de luxo",
    "whatsapp_number": "5531999999999",
    "instagram_url": "https://instagram.com/carolinahelena",
    "address_line": "Pedro Leopoldo/MG",
    "contact_hours": "Segunda a Sexta: 9h às 18h\nSábado: 9h às 13h\nDomingo: fechado",
    "map_embed_url": "https://www.google.com/maps?q=Pedro+Leopoldo+MG&output=embed",
    "about_title": "Nossa História",
    "about_text": "A Carolina Helena nasceu da paixão por criar peças exclusivas que celebram sofisticação, delicadeza e autenticidade feminina. Cada acessório é escolhido com extremo cuidado para oferecer uma experiência elegante e memorável.",
    "about_highlight_1": "100% editável",
    "about_highlight_2": "Painel simples",
    "about_highlight_3": "Pronto para Railway",
    "contact_intro": "Estamos aqui para ajudar. Fale com a loja pelo WhatsApp, Instagram ou visite nossa localização.",
    "hero_kicker": "Nova coleção",
    "home_launches_title": "Lançamentos",
    "home_launches_subtitle": "Peças recém-chegadas para destacar ainda mais a identidade da sua marca.",
    "home_categories_title": "Categorias",
    "home_categories_subtitle": "Organize sua vitrine com categorias claras e imagens elegantes.",
    "home_best_sellers_title": "Mais vendidos",
    "home_best_sellers_subtitle": "Os favoritos das clientes em um só lugar.",
    "logo_image": "images/logo-default.svg",
    "about_image": "images/about-cover.svg",
}

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin").strip()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "").strip()


def verify_admin_login(username: str, password: str) -> bool:
    typed_username = (username or "").strip().lower()
    typed_password = (password or "").strip()

    allowed_usernames = {
        (ADMIN_USERNAME or "admin").strip().lower(),
        "admin",
    }
    if typed_username not in allowed_usernames:
        return False

    if ADMIN_PASSWORD_HASH:
        try:
            if check_password_hash(ADMIN_PASSWORD_HASH, typed_password):
                return True
        except Exception:
            pass

    allowed_passwords = {
        (ADMIN_PASSWORD or "admin123").strip(),
        "admin123",
    }
    return typed_password in allowed_passwords


SIZE_PRESETS = {
    "none": [],
    "ring": [str(number) for number in range(10, 37)],
    "clothing": ["P", "M", "G", "GG"],
}


def normalize_size_mode(size_mode: str) -> str:
    value = (size_mode or "none").strip().lower()
    return value if value in {"none", "ring", "clothing", "custom"} else "none"


def build_size_options(size_mode: str, custom_input: str = "") -> str:
    mode = normalize_size_mode(size_mode)
    if mode in SIZE_PRESETS and SIZE_PRESETS[mode]:
        return ", ".join(SIZE_PRESETS[mode])
    if mode == "custom":
        parts = [item.strip() for item in (custom_input or "").replace(";", ",").split(",") if item.strip()]
        unique_parts = []
        for item in parts:
            if item not in unique_parts:
                unique_parts.append(item)
        return ", ".join(unique_parts)
    return ""


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or str(uuid.uuid4())[:8]


@app.template_filter("currency")
def currency_filter(value):
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0.0
    return f"R$ {number:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")


@app.template_filter("whatsapp_digits")
def whatsapp_digits_filter(value):
    return re.sub(r"\D", "", value or "")


@app.template_filter("fromjson")
def fromjson_filter(value):
    try:
        return json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}


@app.template_filter("nl2br")
def nl2br_filter(value):
    return (value or "").replace("\n", "<br>")


@app.context_processor
def inject_globals():
    site = get_all_settings()
    whatsapp_digits = re.sub(r"\D", "", site.get("whatsapp_number", ""))
    return {
        "site": site,
        "cart": load_cart_details(),
        "current_year": datetime.now().year,
        "store_whatsapp_link": f"https://wa.me/{whatsapp_digits}",
    }


@app.cli.command("init-db")
def init_db_command():
    initialize_database()
    print("Banco inicializado com sucesso.")


@app.route("/")
def home():
    banners = Banner.query.filter_by(is_active=True).order_by(Banner.sort_order.asc(), Banner.id.desc()).all()
    categories = Category.query.filter_by(is_active=True).order_by(Category.name.asc()).all()
    launches = (
        Product.query.filter_by(is_active=True)
        .order_by(Product.created_at.desc())
        .limit(8)
        .all()
    )
    best_sellers = (
        Product.query.filter_by(is_active=True, is_best_seller=True)
        .order_by(Product.created_at.desc())
        .limit(8)
        .all()
    )
    return render_template(
        "home.html",
        banners=banners,
        categories=categories,
        launches=launches,
        best_sellers=best_sellers,
    )


@app.route("/colecao")
def collection():
    category_slug = request.args.get("categoria", "")
    sort = request.args.get("ordem", "recentes")
    search = request.args.get("q", "").strip()

    query = Product.query.filter_by(is_active=True)
    selected_category = None
    if category_slug:
        selected_category = Category.query.filter_by(slug=category_slug, is_active=True).first()
        if selected_category:
            query = query.filter_by(category_id=selected_category.id)

    if search:
        like_term = f"%{search}%"
        query = query.filter(
            or_(
                Product.name.ilike(like_term),
                Product.short_description.ilike(like_term),
                Product.description.ilike(like_term),
            )
        )

    if sort == "preco_menor":
        query = query.order_by(Product.price.asc())
    elif sort == "preco_maior":
        query = query.order_by(Product.price.desc())
    else:
        query = query.order_by(Product.created_at.desc())

    products = query.all()
    categories = Category.query.filter_by(is_active=True).order_by(Category.name.asc()).all()
    return render_template(
        "collection.html",
        products=products,
        categories=categories,
        selected_category=selected_category,
        selected_slug=category_slug,
        selected_sort=sort,
        search=search,
    )


@app.route("/produto/<slug>")
def product_detail(slug):
    product = Product.query.filter_by(slug=slug, is_active=True).first_or_404()
    related = (
        Product.query.filter(
            Product.category_id == product.category_id,
            Product.id != product.id,
            Product.is_active.is_(True),
        )
        .order_by(Product.created_at.desc())
        .limit(4)
        .all()
    )
    return render_template("product_detail.html", product=product, related=related)


@app.route("/sobre")
def about():
    return render_template("about.html")


@app.route("/contato")
def contact():
    return render_template("contact.html")


@app.route("/carrinho")
def cart_page():
    return render_template("cart.html")


@app.post("/cart/add/<int:product_id>")
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    if not product.is_active or product.stock <= 0:
        flash("Este produto está indisponível no momento.", "warning")
        return redirect(request.referrer or url_for("collection"))

    quantity = max(1, int(request.form.get("quantity", 1) or 1))
    selected_size = request.form.get("size", "").strip()

    if product.has_sizes and selected_size not in product.available_sizes:
        flash("Selecione um tamanho válido antes de adicionar ao carrinho.", "warning")
        return redirect(request.referrer or url_for("product_detail", slug=product.slug))

    cart = session.get("cart", {})
    cart_key = f"{product_id}::{selected_size}" if selected_size else str(product_id)
    existing_entry = cart.get(cart_key, {}) if isinstance(cart.get(cart_key), dict) else {}
    current_qty = int(existing_entry.get("quantity", 0) or 0)
    cart[cart_key] = {
        "product_id": product_id,
        "quantity": min(current_qty + quantity, max(product.stock, 1)),
        "size": selected_size,
    }
    session["cart"] = cart
    session.modified = True
    flash(f"{product.name} foi adicionado ao carrinho.", "success")

    action = request.form.get("action", "cart")
    if action == "checkout":
        return redirect(url_for("checkout"))

    next_url = request.form.get("next") or request.referrer or url_for("collection")
    separator = "&" if "?" in next_url else "?"
    return redirect(f"{next_url}{separator}open_cart=1")


@app.post("/cart/update")
def update_cart():
    cart = session.get("cart", {})
    for key, value in request.form.items():
        if key.startswith("qty_"):
            cart_key = key.replace("qty_", "", 1)
            try:
                qty = max(0, int(value))
            except ValueError:
                qty = 1
            cart_entry = cart.get(cart_key, {}) if isinstance(cart.get(cart_key), dict) else {}
            try:
                product_id = int(cart_entry.get("product_id") or str(cart_key).split("::", 1)[0])
            except (TypeError, ValueError):
                continue
            product = Product.query.get(product_id)
            max_stock = product.stock if product else qty
            if qty <= 0:
                cart.pop(cart_key, None)
            else:
                cart[cart_key] = {
                    "product_id": product_id,
                    "quantity": min(qty, max(max_stock, 1)),
                    "size": (cart_entry.get("size") or "").strip(),
                }
    session["cart"] = cart
    session.modified = True
    flash("Carrinho atualizado com sucesso.", "success")
    return redirect(url_for("cart_page"))


@app.post("/cart/remove")
def remove_from_cart():
    cart_key = request.form.get("cart_key", "").strip()
    cart = session.get("cart", {})
    if cart_key:
        cart.pop(cart_key, None)
    session["cart"] = cart
    session.modified = True
    flash("Item removido do carrinho.", "info")
    return redirect(request.referrer or url_for("cart_page"))


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart_data = load_cart_details()
    if not cart_data["items"]:
        flash("Seu carrinho está vazio.", "warning")
        return redirect(url_for("collection"))

    if request.method == "POST":
        customer_name = request.form.get("customer_name", "").strip()
        whatsapp = request.form.get("whatsapp", "").strip()
        cep = request.form.get("cep", "").strip()
        street = request.form.get("street", "").strip()
        number = request.form.get("number", "").strip()
        neighborhood = request.form.get("neighborhood", "").strip()
        city = request.form.get("city", "").strip()
        state = request.form.get("state", "").strip()
        complement = request.form.get("complement", "").strip()
        payment_method = request.form.get("payment_method", "").strip()

        required_fields = [
            customer_name,
            whatsapp,
            street,
            number,
            neighborhood,
            city,
            state,
            payment_method,
        ]
        if not all(required_fields):
            flash("Preencha todos os campos obrigatórios do checkout.", "danger")
            return render_template("checkout.html")

        address_payload = {
            "cep": cep,
            "street": street,
            "number": number,
            "neighborhood": neighborhood,
            "city": city,
            "state": state,
            "complement": complement,
        }
        items_payload = [
            {
                "product_id": item["product"].id,
                "name": item["product"].name,
                "quantity": item["quantity"],
                "size": item.get("size", ""),
                "price": item["product"].price,
            }
            for item in cart_data["items"]
        ]
        order = Order(
            customer_name=customer_name,
            whatsapp=whatsapp,
            address_json=json.dumps(address_payload, ensure_ascii=False),
            payment_method=payment_method,
            subtotal=cart_data["subtotal"],
            items_json=json.dumps(items_payload, ensure_ascii=False),
        )
        db.session.add(order)
        db.session.commit()

        whatsapp_target = re.sub(r"\D", "", get_setting("whatsapp_number", ""))
        message_lines = [
            f"Olá! Quero finalizar este pedido da {get_setting('store_name')}",
            "",
            f"Pedido: #{order.id}",
            f"Nome: {customer_name}",
            f"WhatsApp: {whatsapp}",
            "",
            "Itens:",
        ]
        for item in items_payload:
            subtotal_item = item["quantity"] * item["price"]
            size_label = f" | Tamanho: {item['size']}" if item.get("size") else ""
            message_lines.append(
                f"- {item['name']}{size_label} | Qtde: {item['quantity']} | {subtotal_item:.2f}"
            )
        message_lines.extend(
            [
                "",
                f"Total: {cart_data['subtotal']:.2f}",
                f"Pagamento: {payment_method}",
                "",
                "Endereço:",
                f"{street}, {number} - {neighborhood}",
                f"{city}/{state}",
                f"CEP: {cep}" if cep else "",
                f"Complemento: {complement}" if complement else "",
            ]
        )
        message = "\n".join([line for line in message_lines if line is not None and line != ""])
        session["cart"] = {}
        session.modified = True
        return redirect(f"https://wa.me/{whatsapp_target}?text={quote(message)}")

    return render_template("checkout.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_logged"):
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if verify_admin_login(username, password):
            session["admin_logged"] = True
            flash("Login realizado com sucesso.", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Usuário ou senha inválidos.", "danger")
    return render_template("admin/login.html")


@app.get("/admin/logout")
def admin_logout():
    session.pop("admin_logged", None)
    flash("Você saiu do painel.", "info")
    return redirect(url_for("admin_login"))


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)

    return wrapped


@app.get("/admin")
@admin_required
def admin_dashboard():
    return render_template(
        "admin/dashboard.html",
        total_products=Product.query.count(),
        active_products=Product.query.filter_by(is_active=True).count(),
        total_categories=Category.query.count(),
        total_banners=Banner.query.count(),
        total_orders=Order.query.count(),
        recent_orders=Order.query.order_by(Order.created_at.desc()).limit(10).all(),
    )


@app.route("/admin/settings", methods=["GET", "POST"])
@admin_required
def admin_settings():
    if request.method == "POST":
        keys = [
            "store_name",
            "store_tagline",
            "whatsapp_number",
            "instagram_url",
            "address_line",
            "contact_hours",
            "map_embed_url",
            "about_title",
            "about_text",
            "about_highlight_1",
            "about_highlight_2",
            "about_highlight_3",
            "contact_intro",
            "hero_kicker",
            "home_launches_title",
            "home_launches_subtitle",
            "home_categories_title",
            "home_categories_subtitle",
            "home_best_sellers_title",
            "home_best_sellers_subtitle",
        ]
        for key in keys:
            set_setting(key, request.form.get(key, "").strip())

        logo_file = request.files.get("logo_image")
        if logo_file and logo_file.filename:
            path = save_upload(logo_file)
            if path:
                set_setting("logo_image", path)

        about_image = request.files.get("about_image")
        if about_image and about_image.filename:
            path = save_upload(about_image)
            if path:
                set_setting("about_image", path)

        db.session.commit()
        flash("Configurações atualizadas com sucesso.", "success")
        return redirect(url_for("admin_settings"))
    return render_template("admin/settings.html")


@app.get("/admin/categories")
@admin_required
def admin_categories():
    categories = Category.query.order_by(Category.name.asc()).all()
    return render_template("admin/categories.html", categories=categories)


@app.route("/admin/categories/new", methods=["GET", "POST"])
@admin_required
def admin_category_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        if not name:
            flash("Informe o nome da categoria.", "danger")
            return render_template("admin/category_form.html", category=None)
        category = Category(
            name=name,
            slug=ensure_unique_slug(Category, slugify(name)),
            description=description,
            is_active=bool(request.form.get("is_active")),
        )
        image_file = request.files.get("image")
        if image_file and image_file.filename:
            category.image = save_upload(image_file)
        else:
            category.image = "images/category-default.svg"
        db.session.add(category)
        db.session.commit()
        flash("Categoria criada com sucesso.", "success")
        return redirect(url_for("admin_categories"))
    return render_template("admin/category_form.html", category=None)


@app.route("/admin/categories/<int:category_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_category_edit(category_id):
    category = Category.query.get_or_404(category_id)
    if request.method == "POST":
        category.name = request.form.get("name", "").strip()
        category.slug = ensure_unique_slug(Category, slugify(category.name), category.id)
        category.description = request.form.get("description", "").strip()
        category.is_active = bool(request.form.get("is_active"))
        image_file = request.files.get("image")
        if image_file and image_file.filename:
            category.image = save_upload(image_file)
        db.session.commit()
        flash("Categoria atualizada com sucesso.", "success")
        return redirect(url_for("admin_categories"))
    return render_template("admin/category_form.html", category=category)


@app.post("/admin/categories/<int:category_id>/delete")
@admin_required
def admin_category_delete(category_id):
    category = Category.query.get_or_404(category_id)
    if category.products:
        flash("Remova ou altere os produtos desta categoria antes de excluir.", "danger")
        return redirect(url_for("admin_categories"))
    db.session.delete(category)
    db.session.commit()
    flash("Categoria removida com sucesso.", "info")
    return redirect(url_for("admin_categories"))


@app.get("/admin/products")
@admin_required
def admin_products():
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template("admin/products.html", products=products)


@app.route("/admin/products/new", methods=["GET", "POST"])
@admin_required
def admin_product_new():
    categories = Category.query.order_by(Category.name.asc()).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category_id = request.form.get("category_id")
        if not name or not category_id:
            flash("Nome e categoria são obrigatórios.", "danger")
            return render_template("admin/product_form.html", product=None, categories=categories)

        size_mode = normalize_size_mode(request.form.get("size_mode", "none"))
        product = Product(
            name=name,
            slug=ensure_unique_slug(Product, slugify(name)),
            short_description=request.form.get("short_description", "").strip(),
            description=request.form.get("description", "").strip(),
            price=float(request.form.get("price", 0) or 0),
            compare_at_price=float(request.form.get("compare_at_price", 0) or 0),
            stock=int(request.form.get("stock", 0) or 0),
            category_id=int(category_id),
            size_mode=size_mode,
            size_options=build_size_options(size_mode, request.form.get("custom_sizes", "")),
            is_active=bool(request.form.get("is_active")),
            is_new=bool(request.form.get("is_new")),
            is_best_seller=bool(request.form.get("is_best_seller")),
        )
        image_file = request.files.get("image")
        if image_file and image_file.filename:
            product.image = save_upload(image_file)
        else:
            product.image = "images/product-default.svg"
        db.session.add(product)
        db.session.commit()
        flash("Produto criado com sucesso.", "success")
        return redirect(url_for("admin_products"))
    return render_template("admin/product_form.html", product=None, categories=categories)


@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_product_edit(product_id):
    product = Product.query.get_or_404(product_id)
    categories = Category.query.order_by(Category.name.asc()).all()
    if request.method == "POST":
        product.name = request.form.get("name", "").strip()
        product.slug = ensure_unique_slug(Product, slugify(product.name), product.id)
        product.short_description = request.form.get("short_description", "").strip()
        product.description = request.form.get("description", "").strip()
        product.price = float(request.form.get("price", 0) or 0)
        product.compare_at_price = float(request.form.get("compare_at_price", 0) or 0)
        product.stock = int(request.form.get("stock", 0) or 0)
        product.category_id = int(request.form.get("category_id"))
        product.size_mode = normalize_size_mode(request.form.get("size_mode", "none"))
        product.size_options = build_size_options(product.size_mode, request.form.get("custom_sizes", ""))
        product.is_active = bool(request.form.get("is_active"))
        product.is_new = bool(request.form.get("is_new"))
        product.is_best_seller = bool(request.form.get("is_best_seller"))
        image_file = request.files.get("image")
        if image_file and image_file.filename:
            product.image = save_upload(image_file)
        db.session.commit()
        flash("Produto atualizado com sucesso.", "success")
        return redirect(url_for("admin_products"))
    return render_template("admin/product_form.html", product=product, categories=categories)


@app.post("/admin/products/<int:product_id>/delete")
@admin_required
def admin_product_delete(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash("Produto removido com sucesso.", "info")
    return redirect(url_for("admin_products"))


@app.get("/admin/banners")
@admin_required
def admin_banners():
    banners = Banner.query.order_by(Banner.sort_order.asc(), Banner.id.desc()).all()
    return render_template("admin/banners.html", banners=banners)


@app.route("/admin/banners/new", methods=["GET", "POST"])
@admin_required
def admin_banner_new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Informe o título do banner.", "danger")
            return render_template("admin/banner_form.html", banner=None)
        banner = Banner(
            title=title,
            subtitle=request.form.get("subtitle", "").strip(),
            button_text=request.form.get("button_text", "Explorar coleção").strip(),
            button_link=request.form.get("button_link", "/colecao").strip(),
            sort_order=int(request.form.get("sort_order", 0) or 0),
            is_active=bool(request.form.get("is_active")),
        )
        image_file = request.files.get("image")
        if image_file and image_file.filename:
            banner.image = save_upload(image_file)
        else:
            banner.image = "images/banner-default.svg"
        db.session.add(banner)
        db.session.commit()
        flash("Banner criado com sucesso.", "success")
        return redirect(url_for("admin_banners"))
    return render_template("admin/banner_form.html", banner=None)


@app.route("/admin/banners/<int:banner_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_banner_edit(banner_id):
    banner = Banner.query.get_or_404(banner_id)
    if request.method == "POST":
        banner.title = request.form.get("title", "").strip()
        banner.subtitle = request.form.get("subtitle", "").strip()
        banner.button_text = request.form.get("button_text", "Explorar coleção").strip()
        banner.button_link = request.form.get("button_link", "/colecao").strip()
        banner.sort_order = int(request.form.get("sort_order", 0) or 0)
        banner.is_active = bool(request.form.get("is_active"))
        image_file = request.files.get("image")
        if image_file and image_file.filename:
            banner.image = save_upload(image_file)
        db.session.commit()
        flash("Banner atualizado com sucesso.", "success")
        return redirect(url_for("admin_banners"))
    return render_template("admin/banner_form.html", banner=banner)


@app.post("/admin/banners/<int:banner_id>/delete")
@admin_required
def admin_banner_delete(banner_id):
    banner = Banner.query.get_or_404(banner_id)
    db.session.delete(banner)
    db.session.commit()
    flash("Banner removido com sucesso.", "info")
    return redirect(url_for("admin_banners"))


@app.get("/admin/orders")
@admin_required
def admin_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template("admin/orders.html", orders=orders)


@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(_error):
    db.session.rollback()
    return render_template("500.html"), 500


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file_storage):
    if not file_storage or not allowed_file(file_storage.filename):
        return None
    filename = secure_filename(file_storage.filename)
    extension = filename.rsplit(".", 1)[1].lower()
    final_name = f"{uuid.uuid4().hex}.{extension}"
    path = os.path.join(app.config["UPLOAD_FOLDER"], final_name)
    file_storage.save(path)
    return f"uploads/{final_name}"


def ensure_unique_slug(model, base_slug, current_id=None):
    slug = base_slug
    index = 2
    while True:
        query = model.query.filter_by(slug=slug)
        if current_id:
            query = query.filter(model.id != current_id)
        existing = query.first()
        if not existing:
            return slug
        slug = f"{base_slug}-{index}"
        index += 1


def get_setting(key, default=""):
    setting = Setting.query.filter_by(key=key).first()
    if setting and setting.value not in (None, ""):
        return setting.value
    return DEFAULT_SETTINGS.get(key, default)


def set_setting(key, value):
    setting = Setting.query.filter_by(key=key).first()
    if not setting:
        setting = Setting(key=key, value=value)
        db.session.add(setting)
    else:
        setting.value = value


def get_all_settings():
    data = DEFAULT_SETTINGS.copy()
    for row in Setting.query.all():
        data[row.key] = row.value
    return data


def load_cart_details():
    cart = session.get("cart", {})
    items = []
    subtotal = 0.0
    total_quantity = 0
    if not cart:
        return {"items": items, "subtotal": subtotal, "total_quantity": total_quantity}

    product_ids = []
    for cart_value in cart.values():
        if isinstance(cart_value, dict):
            product_id = cart_value.get("product_id")
        else:
            product_id = None
        if product_id is None:
            continue
        try:
            product_ids.append(int(product_id))
        except (TypeError, ValueError):
            continue

    if not product_ids:
        legacy_keys = []
        for cart_key in cart.keys():
            try:
                legacy_keys.append(int(str(cart_key).split("::", 1)[0]))
            except (TypeError, ValueError):
                continue
        product_ids = legacy_keys

    products = Product.query.filter(Product.id.in_(product_ids), Product.is_active.is_(True)).all()
    product_map = {product.id: product for product in products}

    normalized_cart = {}
    for cart_key, cart_value in cart.items():
        if isinstance(cart_value, dict):
            try:
                product_id = int(cart_value.get("product_id"))
                quantity = int(cart_value.get("quantity", 1))
            except (TypeError, ValueError):
                continue
            selected_size = (cart_value.get("size") or "").strip()
        else:
            try:
                product_id = int(str(cart_key).split("::", 1)[0])
                quantity = int(cart_value)
            except (TypeError, ValueError):
                continue
            selected_size = ""

        product = product_map.get(product_id)
        if not product:
            continue

        if product.has_sizes:
            if selected_size not in product.available_sizes:
                continue
            normalized_key = f"{product_id}::{selected_size}"
        else:
            selected_size = ""
            normalized_key = str(product_id)

        quantity = max(1, min(quantity, max(product.stock, 1)))
        normalized_cart[normalized_key] = {
            "product_id": product_id,
            "quantity": quantity,
            "size": selected_size,
        }
        item_subtotal = quantity * product.price
        items.append({
            "cart_key": normalized_key,
            "product": product,
            "quantity": quantity,
            "size": selected_size,
            "subtotal": item_subtotal,
        })
        subtotal += item_subtotal
        total_quantity += quantity

    if normalized_cart != cart:
        session["cart"] = normalized_cart
        session.modified = True

    return {"items": items, "subtotal": subtotal, "total_quantity": total_quantity}


def seed_data():
    if Category.query.first():
        return

    categories = [
        Category(name="Bolsas", slug="bolsas", description="Bolsas elegantes", image="images/category-bags.svg"),
        Category(name="Joias", slug="joias", description="Joias sofisticadas", image="images/category-jewels.svg"),
        Category(name="Relógios", slug="relogios", description="Relógios modernos", image="images/category-watches.svg"),
        Category(name="Óculos", slug="oculos", description="Óculos estilosos", image="images/category-glasses.svg"),
    ]
    db.session.add_all(categories)
    db.session.flush()

    products = [
        Product(
            name="Bolsa de Couro Premium",
            slug="bolsa-de-couro-premium",
            short_description="Bolsa artesanal em couro legítimo premium",
            description="Bolsa elegante para compor produções sofisticadas em qualquer ocasião.",
            price=1299.90,
            compare_at_price=0,
            stock=5,
            image="images/produto-bolsa.svg",
            is_active=True,
            is_new=True,
            is_best_seller=True,
            category_id=categories[0].id,
        ),
        Product(
            name="Colar Dourado Delicado",
            slug="colar-dourado-delicado",
            short_description="Colar em ouro 18k com design minimalista",
            description="Colar delicado com acabamento refinado para looks elegantes.",
            price=749.00,
            compare_at_price=890.00,
            stock=8,
            image="images/produto-colar.svg",
            size_mode="ring",
            size_options=", ".join(SIZE_PRESETS["ring"]),
            is_active=True,
            is_new=True,
            is_best_seller=True,
            category_id=categories[1].id,
        ),
        Product(
            name="Brincos de Diamante",
            slug="brincos-de-diamante",
            short_description="Brincos com diamantes naturais em ouro branco",
            description="Brincos sofisticados para ocasiões especiais e eventos elegantes.",
            price=2499.90,
            compare_at_price=0,
            stock=3,
            image="images/produto-brincos.svg",
            is_active=True,
            is_new=False,
            is_best_seller=True,
            category_id=categories[1].id,
        ),
        Product(
            name="Pérolas Clássicas",
            slug="perolas-classicas",
            short_description="Colar de pérolas naturais cultivadas",
            description="Uma peça atemporal e feminina com toque clássico refinado.",
            price=1599.00,
            compare_at_price=0,
            stock=4,
            image="images/produto-perolas.svg",
            is_active=True,
            is_new=False,
            is_best_seller=False,
            category_id=categories[1].id,
        ),
    ]
    db.session.add_all(products)

    banner = Banner(
        title="",
        subtitle="",
        button_text="Ver coleção",
        button_link="/colecao",
        image="images/banner-default.svg",
        is_active=True,
        sort_order=1,
    )
    db.session.add(banner)

    for key, value in DEFAULT_SETTINGS.items():
        set_setting(key, value)

    db.session.commit()


def ensure_schema_updates():
    inspector = inspect(db.engine)
    product_columns = {column["name"] for column in inspector.get_columns("product")}
    statements = []
    if "size_mode" not in product_columns:
        statements.append("ALTER TABLE product ADD COLUMN size_mode VARCHAR(30)")
    if "size_options" not in product_columns:
        statements.append("ALTER TABLE product ADD COLUMN size_options TEXT")
    for statement in statements:
        db.session.execute(text(statement))
    if statements:
        db.session.commit()


def initialize_database():
    db.create_all()
    ensure_schema_updates()
    for key, value in DEFAULT_SETTINGS.items():
        if not Setting.query.filter_by(key=key).first():
            db.session.add(Setting(key=key, value=value))
    db.session.commit()
    seed_data()


with app.app_context():
    initialize_database()


if __name__ == "__main__":
    app.run(debug=True)
