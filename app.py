from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# --- Database configuration ---
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///deals.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# Ensure SSL on Railway Postgres unless already set
if DATABASE_URL.startswith('postgresql://') and 'sslmode=' not in DATABASE_URL:
    sep = '&' if '?' in DATABASE_URL else '?'
    DATABASE_URL = f"{DATABASE_URL}{sep}sslmode=require"

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}

db = SQLAlchemy(app)

# --- Models ---
class Deal(db.Model):
    __tablename__ = 'deals'
    id = db.Column(db.Integer, primary_key=True)
    store_name = db.Column(db.String(100), nullable=False, index=True)
    product_name = db.Column(db.String(500), nullable=False)
    price = db.Column(db.String(50))
    original_price = db.Column(db.String(50))
    discount = db.Column(db.String(50))
    category = db.Column(db.String(100), index=True)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    deal_url = db.Column(db.String(500))
    valid_from = db.Column(db.DateTime, default=datetime.utcnow)
    valid_until = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'store_name': self.store_name,
            'product_name': self.product_name,
            'price': self.price,
            'original_price': self.original_price,
            'discount': self.discount,
            'category': self.category,
            'description': self.description,
            'image_url': self.image_url,
            'deal_url': self.deal_url,
            'valid_from': self.valid_from.isoformat() if self.valid_from else None,
            'valid_until': self.valid_until.isoformat() if self.valid_until else None,
        }

class Store(db.Model):
    __tablename__ = 'stores'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    display_name = db.Column(db.String(100))
    website = db.Column(db.String(200))
    logo_url = db.Column(db.String(500))
    last_scraped = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'display_name': self.display_name,
            'website': self.website,
            'logo_url': self.logo_url,
            'last_scraped': self.last_scraped.isoformat() if self.last_scraped else None,
        }

# --- One-time DB init at import (Flask 3.x compatible) ---
def _init_db_once():
    try:
        from sqlalchemy import select
        with app.app_context():
            db.create_all()
            # idempotent seed
            seeds = [
                {'name': 'walmart', 'display_name': 'Walmart', 'website': 'https://www.walmart.com'},
                {'name': 'target',  'display_name': 'Target',  'website': 'https://www.target.com'},
                {'name': 'kroger',  'display_name': 'Kroger',  'website': 'https://www.kroger.com'},
            ]
            for s in seeds:
                exists = db.session.execute(
                    select(Store.id).where(Store.name == s['name'])
                ).first()
                if not exists:
                    db.session.add(Store(**s))
            db.session.commit()
    except Exception as e:
        print("DB init error:", e)
        try: db.session.rollback()
        except: pass

_init_db_once()

# --- API Endpoints ---
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

@app.route('/api/stores', methods=['GET'])
def get_stores():
    stores = Store.query.filter_by(is_active=True).all()
    return jsonify({'stores': [s.to_dict() for s in stores], 'count': len(stores)})

@app.route('/api/deals', methods=['GET'])
def get_deals():
    query = Deal.query
    store_name = request.args.get('store')
    if store_name:
        query = query.filter(Deal.store_name.ilike(f'%{store_name}%'))
    category = request.args.get('category')
    if category:
        query = query.filter(Deal.category.ilike(f'%{category}%'))
    search = request.args.get('search')
    if search:
        query = query.filter(Deal.product_name.ilike(f'%{search}%'))

    query = query.filter((Deal.valid_until.is_(None)) | (Deal.valid_until > datetime.utcnow()))
    query = query.order_by(Deal.created_at.desc())
    limit = request.args.get('limit', 100, type=int)
    deals = query.limit(min(limit, 500)).all()
    return jsonify({'deals': [d.to_dict() for d in deals], 'count': len(deals)})

@app.route('/api/deals/<store_name>', methods=['GET'])
def get_deals_by_store(store_name):
    deals = Deal.query.filter(
        Deal.store_name.ilike(f'%{store_name}%'),
        (Deal.valid_until.is_(None)) | (Deal.valid_until > datetime.utcnow())
    ).order_by(Deal.created_at.desc()).all()
    return jsonify({'store': store_name, 'deals': [d.to_dict() for d in deals], 'count': len(deals)})

@app.route('/api/deals/search', methods=['GET'])
def search_deals():
    q = request.args.get('q', '')
    if not q:
        return jsonify({'error': 'Missing search query'}), 400
    deals = Deal.query.filter(
        (Deal.product_name.ilike(f'%{q}%')) |
        (Deal.category.ilike(f'%{q}%')) |
        (Deal.description.ilike(f'%{q}%')),
        (Deal.valid_until.is_(None)) | (Deal.valid_until > datetime.utcnow())
    ).order_by(Deal.created_at.desc()).limit(100).all()
    return jsonify({'query': q, 'deals': [d.to_dict() for d in deals], 'count': len(deals)})

@app.route('/api/stats', methods=['GET'])
def get_stats():
    total_deals = Deal.query.count()
    active_deals = Deal.query.filter(
        (Deal.valid_until.is_(None)) | (Deal.valid_until > datetime.utcnow())
    ).count()
    stores = Store.query.filter_by(is_active=True).count()
    return jsonify({
        'total_deals': total_deals,
        'active_deals': active_deals,
        'active_stores': stores,
        'last_updated': datetime.utcnow().isoformat()
    })

@app.route('/api/admin/deals/bulk', methods=['POST'])
def bulk_add_deals():
    data = request.get_json()
    if not isinstance(data, list):
        return jsonify({'error': 'Expected array of deals'}), 400
    added = 0
    for deal_data in data:
        try:
            if 'valid_from' in deal_data and isinstance(deal_data['valid_from'], str):
                deal_data['valid_from'] = datetime.fromisoformat(deal_data['valid_from'])
            if 'valid_until' in deal_data and isinstance(deal_data['valid_until'], str):
                deal_data['valid_until'] = datetime.fromisoformat(deal_data['valid_until'])
            existing = Deal.query.filter_by(
                store_name=deal_data.get('store_name'),
                product_name=deal_data.get('product_name')
            ).first()
            if existing:
                for k, v in deal_data.items():
                    setattr(existing, k, v)
                existing.updated_at = datetime.utcnow()
            else:
                db.session.add(Deal(**deal_data))
            added += 1
        except Exception as e:
            print(f"Error adding deal: {e}")
            db.session.rollback()
            continue
    db.session.commit()
    return jsonify({'success': True, 'deals_processed': len(data), 'deals_added': added})

@app.route('/api/admin/deals/cleanup', methods=['POST'])
def cleanup_old_deals():
    cutoff_date = datetime.utcnow() - timedelta(days=30)
    deleted = Deal.query.filter(Deal.created_at < cutoff_date).delete()
    db.session.commit()
    return jsonify({'success': True, 'deleted_count': deleted})

if __name__ == '__main__':
    # Local dev only (Railway uses Gunicorn via Procfile)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
