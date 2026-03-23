from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from flask_socketio import emit, join_room, leave_room
from models import db, Message, User, Product
from sqlalchemy import or_, and_

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/api/conversations', methods=['GET'])
@login_required
def get_conversations():
    """Get all unique conversations for the current user"""
    uid = current_user.id
    
    # Get all messages involving current user
    messages = Message.query.filter(
        or_(Message.sender_id == uid, Message.receiver_id == uid)
    ).order_by(Message.timestamp.desc()).all()

    # Build unique conversations
    convos = {}
    for msg in messages:
        other_id = msg.receiver_id if msg.sender_id == uid else msg.sender_id
        key = f"{min(uid, other_id)}-{max(uid, other_id)}-{msg.product_id or 0}"
        
        if key not in convos:
            other = User.query.get(other_id)
            product = Product.query.get(msg.product_id) if msg.product_id else None
            unread = Message.query.filter_by(
                sender_id=other_id, receiver_id=uid,
                product_id=msg.product_id, is_read=False
            ).count()
            
            convos[key] = {
                'other_user': other.to_dict() if other else None,
                'product': product.to_dict() if product else None,
                'last_message': msg.to_dict(),
                'unread_count': unread
            }

    return jsonify({'conversations': list(convos.values())}), 200


@chat_bp.route('/api/messages', methods=['GET'])
@login_required
def get_messages():
    other_id = request.args.get('user_id', type=int)
    product_id = request.args.get('product_id', type=int)

    if not other_id:
        return jsonify({'error': 'user_id is required'}), 400

    uid = current_user.id
    query = Message.query.filter(
        or_(
            and_(Message.sender_id == uid, Message.receiver_id == other_id),
            and_(Message.sender_id == other_id, Message.receiver_id == uid)
        )
    )

    if product_id:
        query = query.filter_by(product_id=product_id)

    messages = query.order_by(Message.timestamp.asc()).all()

    # Mark messages as read
    Message.query.filter_by(
        sender_id=other_id, receiver_id=uid, is_read=False
    ).update({'is_read': True})
    db.session.commit()

    return jsonify({
        'messages': [m.to_dict() for m in messages],
        'other_user': User.query.get(other_id).to_dict() if User.query.get(other_id) else None
    }), 200


@chat_bp.route('/api/messages', methods=['POST'])
@login_required
def send_message():
    data = request.get_json() or {}
    receiver_id = data.get('receiver_id')
    product_id = data.get('product_id')
    message_text = data.get('message', '').strip()

    if not receiver_id or not message_text:
        return jsonify({'error': 'receiver_id and message are required'}), 400

    if receiver_id == current_user.id:
        return jsonify({'error': 'Cannot message yourself'}), 400

    receiver = User.query.get(receiver_id)
    if not receiver:
        return jsonify({'error': 'User not found'}), 404

    msg = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        product_id=product_id,
        message=message_text
    )
    db.session.add(msg)
    db.session.commit()

    return jsonify({'message': msg.to_dict()}), 201


@chat_bp.route('/api/unread-count', methods=['GET'])
@login_required
def unread_count():
    count = Message.query.filter_by(receiver_id=current_user.id, is_read=False).count()
    return jsonify({'count': count}), 200


def init_socketio(socketio):
    @socketio.on('join')
    def on_join(data):
        room = data.get('room')
        if room:
            join_room(room)
            emit('status', {'msg': 'Joined room'}, room=room)

    @socketio.on('leave')
    def on_leave(data):
        room = data.get('room')
        if room:
            leave_room(room)

    @socketio.on('send_message')
    def on_message(data):
        room = data.get('room')
        message = data.get('message')
        sender_name = data.get('sender_name')
        if room and message:
            emit('receive_message', {
                'message': message,
                'sender_name': sender_name,
                'timestamp': data.get('timestamp')
            }, room=room)
