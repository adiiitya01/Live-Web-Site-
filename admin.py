from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, User, Product, Report, Message
from functools import wraps
import os

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/api/admin/stats', methods=['GET'])
@login_required
@admin_required
def get_stats():
    return jsonify({
        'total_users': User.query.count(),
        'total_products': Product.query.count(),
        'active_products': Product.query.filter_by(is_available=True).count(),
        'total_messages': Message.query.count(),
        'pending_reports': Report.query.filter_by(status='pending').count()
    }), 200


@admin_bp.route('/api/admin/users', methods=['GET'])
@login_required
@admin_required
def get_users():
    page = request.args.get('page', 1, type=int)
    users = User.query.paginate(page=page, per_page=20, error_out=False)
    return jsonify({
        'users': [u.to_dict() for u in users.items],
        'total': users.total,
        'pages': users.pages
    }), 200


@admin_bp.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        return jsonify({'error': 'Cannot delete admin'}), 403
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': 'User deleted'}), 200


@admin_bp.route('/api/admin/products', methods=['GET'])
@login_required
@admin_required
def get_all_products():
    page = request.args.get('page', 1, type=int)
    products = Product.query.order_by(Product.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return jsonify({
        'products': [p.to_dict(include_seller=True) for p in products.items],
        'total': products.total,
        'pages': products.pages
    }), 200


@admin_bp.route('/api/admin/products/<int:product_id>', methods=['DELETE'])
@login_required
@admin_required
def admin_delete_product(product_id):
    from flask import current_app
    product = Product.query.get_or_404(product_id)
    for img in product.images:
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], img.filename)
        if os.path.exists(filepath):
            os.remove(filepath)
    db.session.delete(product)
    db.session.commit()
    return jsonify({'message': 'Product deleted'}), 200


@admin_bp.route('/api/admin/reports', methods=['GET'])
@login_required
@admin_required
def get_reports():
    status = request.args.get('status', 'pending')
    reports = Report.query.filter_by(status=status).order_by(Report.created_at.desc()).all()
    result = []
    for r in reports:
        result.append({
            'id': r.id,
            'reporter_id': r.reporter_id,
            'product_id': r.product_id,
            'reason': r.reason,
            'description': r.description,
            'status': r.status,
            'created_at': r.created_at.isoformat(),
            'product': r.product.to_dict() if r.product else None
        })
    return jsonify({'reports': result}), 200


@admin_bp.route('/api/admin/reports/<int:report_id>', methods=['PUT'])
@login_required
@admin_required
def update_report(report_id):
    report = Report.query.get_or_404(report_id)
    data = request.get_json() or {}
    status = data.get('status')
    if status in ('reviewed', 'dismissed'):
        report.status = status
        db.session.commit()
    return jsonify({'message': 'Report updated'}), 200
