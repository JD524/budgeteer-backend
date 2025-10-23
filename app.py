from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///deals.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# Database Models
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


# Initialize database
with app.app_context():
    db.create_all()

    # Add initial stores if they don't exist
    stores_to_add = [
        {'name': 'walmart', 'display_name': 'Walmart', 'website': 'https://www.walmart.com'},
        {'name': 'target', 'display_name': 'Target', 'website': 'https://www.target.com'},
        {'name': 'kroger', 'display_name': 'Kroger', 'website': 'https://www.kroger.com'},
    ]

    for store_data in stores_to_add:
        if not Store.query.filter_by(name=store_data['name']).first():
            store = Store(**store_data)
            db.session.add(store)

    db.session.commit()


# API Endpoints

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})


@app.route('/api/stores', methods=['GET'])
def get_stores():
    """Get all active stores"""
    stores = Store.query.filter_by(is_active=True).all()
    return jsonify({
        'stores': [store.to_dict() for store in stores],
        'count': len(stores)
    })


@app.route('/api/deals', methods=['GET'])
def get_deals():
    """
    Get deals with optional filtering
    Query params:
    - store: Filter by store name (e.g., 'walmart')
    - category: Filter by category (e.g., 'groceries')
    - search: Search in product name
    - limit: Max number of results (default 100)
    """
    query = Deal.query

    # Filter by store
    store_name = request.args.get('store')
    if store_name:
        query = query.filter(Deal.store_name.ilike(f'%{store_name}%'))

    # Filter by category
    category = request.args.get('category')
    if category:
        query = query.filter(Deal.category.ilike(f'%{category}%'))

    # Search in product name
    search = request.args.get('search')
    if search:
        query = query.filter(Deal.product_name.ilike(f'%{search}%'))

    # Only show deals that are still valid
    query = query.filter(
        (Deal.valid_until.is_(None)) | (Deal.valid_until > datetime.utcnow())
    )

    # Order by most recent FIRST
    query = query.order_by(Deal.created_at.desc())

    # THEN limit results
    limit = request.args.get('limit', 100, type=int)
    query = query.limit(min(limit, 500))  # Max 500 results

    deals = query.all()

    return jsonify({
        'deals': [deal.to_dict() for deal in deals],
        'count': len(deals)
    })


@app.route('/api/deals/<store_name>', methods=['GET'])
def get_deals_by_store(store_name):
    """Get all deals for a specific store"""
    deals = Deal.query.filter(
        Deal.store_name.ilike(f'%{store_name}%'),
        (Deal.valid_until.is_(None)) | (Deal.valid_until > datetime.utcnow())
    ).order_by(Deal.created_at.desc()).all()

    return jsonify({
        'store': store_name,
        'deals': [deal.to_dict() for deal in deals],
        'count': len(deals)
    })


@app.route('/api/deals/search', methods=['GET'])
def search_deals():
    """
    Search deals by product name or category
    Query param: q (search query)
    """
    query_text = request.args.get('q', '')
    if not query_text:
        return jsonify({'error': 'Missing search query'}), 400

    deals = Deal.query.filter(
        (Deal.product_name.ilike(f'%{query_text}%')) |
        (Deal.category.ilike(f'%{query_text}%')) |
        (Deal.description.ilike(f'%{query_text}%')),
        (Deal.valid_until.is_(None)) | (Deal.valid_until > datetime.utcnow())
    ).order_by(Deal.created_at.desc()).limit(100).all()

    return jsonify({
        'query': query_text,
        'deals': [deal.to_dict() for deal in deals],
        'count': len(deals)
    })


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get database statistics"""
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


# Admin endpoints (for scraper use)

@app.route('/api/admin/deals/bulk', methods=['POST'])
def bulk_add_deals():
    """
    Bulk add deals (used by scrapers)
    Expects JSON array of deal objects
    """
    data = request.get_json()
    if not isinstance(data, list):
        return jsonify({'error': 'Expected array of deals'}), 400

    added = 0
    for deal_data in data:
        try:
            # Parse datetime strings back to datetime objects
            if 'valid_from' in deal_data and isinstance(deal_data['valid_from'], str):
                deal_data['valid_from'] = datetime.fromisoformat(deal_data['valid_from'])

            if 'valid_until' in deal_data and isinstance(deal_data['valid_until'], str):
                deal_data['valid_until'] = datetime.fromisoformat(deal_data['valid_until'])

            # Check if deal already exists (by store + product name)
            existing = Deal.query.filter_by(
                store_name=deal_data.get('store_name'),
                product_name=deal_data.get('product_name')
            ).first()

            if existing:
                # Update existing deal
                for key, value in deal_data.items():
                    setattr(existing, key, value)
                existing.updated_at = datetime.utcnow()
            else:
                # Create new deal
                deal = Deal(**deal_data)
                db.session.add(deal)

            added += 1
        except Exception as e:
            print(f"Error adding deal: {e}")
            db.session.rollback()
            continue

    db.session.commit()

    # THIS IS THE MISSING PART - ADD IT!
    return jsonify({
        'success': True,
        'deals_processed': len(data),
        'deals_added': added
    })

    db.session.commit()


@app.route('/api/admin/deals/cleanup', methods=['POST'])
def cleanup_old_deals():
    """Remove deals older than 30 days"""
    cutoff_date = datetime.utcnow() - timedelta(days=30)
    deleted = Deal.query.filter(Deal.created_at < cutoff_date).delete()
    db.session.commit()

    return jsonify({
        'success': True,
        'deleted_count': deleted
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)