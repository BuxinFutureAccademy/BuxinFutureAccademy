from datetime import datetime
from ..extensions import db


class SiteSettings(db.Model):
    """Model for storing site-wide settings like contact information"""
    __tablename__ = 'site_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Relationships
    updater = db.relationship('User', foreign_keys=[updated_by], lazy='select')
    
    def __repr__(self):
        return f'<SiteSettings {self.setting_key}: {self.setting_value}>'
    
    @staticmethod
    def get_setting(key, default=None):
        """Get a setting value by key"""
        setting = SiteSettings.query.filter_by(setting_key=key).first()
        return setting.setting_value if setting else default
    
    @staticmethod
    def set_setting(key, value, user_id=None):
        """Set or update a setting value"""
        setting = SiteSettings.query.filter_by(setting_key=key).first()
        if setting:
            setting.setting_value = value
            setting.updated_at = datetime.utcnow()
            if user_id:
                setting.updated_by = user_id
        else:
            setting = SiteSettings(
                setting_key=key,
                setting_value=value,
                updated_by=user_id
            )
            db.session.add(setting)
        db.session.commit()
        return setting

