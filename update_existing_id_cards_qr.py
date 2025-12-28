#!/usr/bin/env python3
"""
Script to update existing ID cards with QR codes if they don't have one
"""
import os
import sys

# Set the database URL
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_Mk5tHxKfBIn9@ep-sweet-surf-a43sacap-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require'

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from webapp import create_app
from webapp.extensions import db
from webapp.models.id_cards import IDCard
from flask import url_for

def update_existing_qr_codes():
    """Update existing ID cards with QR codes if missing"""
    app = create_app()
    
    # Configure app for URL generation outside request context
    app.config['SERVER_NAME'] = 'edu.techbuxin.com'
    app.config['PREFERRED_URL_SCHEME'] = 'https'
    app.config['APPLICATION_ROOT'] = '/'
    
    with app.app_context():
        try:
            # Find all ID cards without QR codes
            id_cards_without_qr = IDCard.query.filter(
                (IDCard.qr_code_data == None) | (IDCard.qr_code_data == '')
            ).all()
            
            print(f"Found {len(id_cards_without_qr)} ID cards without QR codes")
            
            updated_count = 0
            for id_card in id_cards_without_qr:
                try:
                    # Generate QR code URL
                    qr_url = url_for('main.qr_code_redirect', id_card_id=id_card.id, _external=True)
                    id_card.qr_code_data = qr_url
                    updated_count += 1
                    print(f"[OK] Updated ID card {id_card.id} ({id_card.entity_type}) with QR code")
                except Exception as e:
                    print(f"[ERROR] Failed to update ID card {id_card.id}: {e}")
            
            if updated_count > 0:
                db.session.commit()
                print(f"\n[OK] Successfully updated {updated_count} ID cards with QR codes!")
            else:
                print("\n[INFO] No ID cards needed updating")
                
        except Exception as e:
            print(f"[ERROR] Error updating QR codes: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True

if __name__ == '__main__':
    success = update_existing_qr_codes()
    sys.exit(0 if success else 1)

