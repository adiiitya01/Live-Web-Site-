from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from models import db, Product, ProductImage, Wishlist, Report
from werkzeug.utils import secure_filename
import os
import uuid
from PIL import Image

products_bp = Blueprint('products', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
CATEGORIES = ['Electronics', 'Furniture', 'Clothing', 'Books', 'Vehicles', 'Sports', 'Home & Garden', 'Toys', 'Music', 'Other']

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_image(file):
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    filepath = os.path.join(upload_folder, filename)
    
    img = Image.open(file)
    img.thumbnail((1200, 1200), Image.LANCZOS)
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    img.save(filepath, quality=85, optimize=True)
    return filename


@products_bp.route('/api/products', methods=['GET'])
def get_products():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 12, type=int)
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    location = request.args.get('location', '').strip()
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    sort = request.args.get('sort', 'newest')

    query = Product.query.filter_by(is_available=True)

    if search:
        query = query.filter(
            db.or_(
                Product.title.ilike(f'%{search}%'),
                Product.description.ilike(f'%{search}%')
            )
        )
    if category:
        query = query.filter_by(category=category)
    if location:
        query = query.filter(Product.location.ilike(f'%{location}%'))
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    if sort == 'price_asc':
        query = query.order_by(Product.price.asc())
    elif sort == 'price_desc':
        query = query.order_by(Product.price.desc())
    elif sort == 'popular':
        query = query.order_by(Product.views.desc())
    else:
        query = query.order_by(Product.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    products = [p.to_dict(include_seller=True) for p in pagination.items]

    return jsonify({
        'products': products,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page,
        'per_page': per_page
    }), 200


@products_bp.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    product = Product.query.get_or_404(product_id)
    product.views += 1
    db.session.commit()

    data = product.to_dict(include_seller=True)
    if current_user.is_authenticated:
        wishlist = Wishlist.query.filter_by(user_id=current_user.id, product_id=product_id).first()
        data['in_wishlist'] = wishlist is not None
    else:
        data['in_wishlist'] = False

    return jsonify({'product': data}), 200


@products_bp.route('/api/products', methods=['POST'])
@login_required
def create_product():
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    price = request.form.get('price')
    category = request.form.get('category', '').strip()
    condition = request.form.get('condition', 'Good').strip()
    location = request.form.get('location', '').strip()

    if not all([title, description, price, category, location]):
        return jsonify({'error': 'All fields are required'}), 400

    try:
        price = float(price)
        if price < 0:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid price'}), 400

    if category not in CATEGORIES:
        return jsonify({'error': 'Invalid category'}), 400

    product = Product(
        user_id=current_user.id,
        title=title,
        description=description,
        price=price,
        category=category,
        condition=condition,
        location=location
    )
    db.session.add(product)
    db.session.flush()

    files = request.files.getlist('images')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': 'At least one image is required'}), 400

    for file in files[:5]:  # Max 5 images
        if file and allowed_file(file.filename):
            filename = save_image(file)
            img = ProductImage(product_id=product.id, filename=filename)
            db.session.add(img)

    db.session.commit()
    return jsonify({'message': 'Product created', 'product': product.to_dict()}), 201


@products_bp.route('/api/products/<int:product_id>', methods=['PUT'])
@login_required
def update_product(product_id):
    product = Product.query.get_or_404(product_id)
    if product.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json() or {}

    if 'title' in data and data['title'].strip():
        product.title = data['title'].strip()
    if 'description' in data:
        product.description = data['description'].strip()
    if 'price' in data:
        try:
            product.price = float(data['price'])
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid price'}), 400
    if 'category' in data and data['category'] in CATEGORIES:
        product.category = data['category']
    if 'condition' in data:
        product.condition = data['condition']
    if 'location' in data:
        product.location = data['location'].strip()
    if 'is_available' in data:
        product.is_available = bool(data['is_available'])

    db.session.commit()
    return jsonify({'message': 'Product updated', 'product': product.to_dict()}), 200


@products_bp.route('/api/products/<int:product_id>', methods=['DELETE'])
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    if product.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    # Delete image files
    for img in product.images:
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], img.filename)
        if os.path.exists(filepath):
            os.remove(filepath)

    db.session.delete(product)
    db.session.commit()
    return jsonify({'message': 'Product deleted'}), 200


@products_bp.route('/api/categories', methods=['GET'])
def get_categories():
    return jsonify({'categories': CATEGORIES}), 200


@products_bp.route('/api/wishlist', methods=['GET'])
@login_required
def get_wishlist():
    items = Wishlist.query.filter_by(user_id=current_user.id).all()
    products = []
    for item in items:
        p = item.product
        if p and p.is_available:
            products.append(p.to_dict(include_seller=True))
    return jsonify({'products': products}), 200


@products_bp.route('/api/wishlist/<int:product_id>', methods=['POST'])
@login_required
def toggle_wishlist(product_id):
    product = Product.query.get_or_404(product_id)
    existing = Wishlist.query.filter_by(user_id=current_user.id, product_id=product_id).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({'message': 'Removed from wishlist', 'in_wishlist': False}), 200
    else:
        w = Wishlist(user_id=current_user.id, product_id=product_id)
        db.session.add(w)
        db.session.commit()
        return jsonify({'message': 'Added to wishlist', 'in_wishlist': True}), 200


@products_bp.route('/api/products/<int:product_id>/report', methods=['POST'])
@login_required
def report_product(product_id):
    product = Product.query.get_or_404(product_id)
    data = request.get_json() or {}
    reason = data.get('reason', '').strip()
    description = data.get('description', '').strip()

    if not reason:
        return jsonify({'error': 'Reason is required'}), 400

    report = Report(
        reporter_id=current_user.id,
        product_id=product_id,
        reason=reason,
        description=description
    )
    db.session.add(report)
    db.session.commit()
    return jsonify({'message': 'Report submitted'}), 201


@products_bp.route('/api/dashboard', methods=['GET'])
@login_required
def dashboard():
    products = Product.query.filter_by(user_id=current_user.id).order_by(Product.created_at.desc()).all()
    wishlist_count = Wishlist.query.filter_by(user_id=current_user.id).count()
    total_views = sum(p.views for p in products)

    return jsonify({
        'products': [p.to_dict() for p in products],
        'stats': {
            'total_listings': len(products),
            'active_listings': sum(1 for p in products if p.is_available),
            'total_views': total_views,
            'wishlist_count': wishlist_count
        }
    }), 200
