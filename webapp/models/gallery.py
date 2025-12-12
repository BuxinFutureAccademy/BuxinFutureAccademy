from datetime import datetime
from ..extensions import db


class HomeGallery(db.Model):
    """Model for homepage gallery items (images and videos)"""
    __tablename__ = 'home_gallery'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    media_type = db.Column(db.String(20), nullable=False)  # 'image' or 'video'
    media_url = db.Column(db.String(500), nullable=False)
    thumbnail_url = db.Column(db.String(500))  # For videos
    
    # Source tracking
    source_type = db.Column(db.String(50), default='admin')  # 'admin' or 'student_project'
    source_project_id = db.Column(db.Integer, db.ForeignKey('student_project.id'), nullable=True)
    
    # Display settings
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    display_order = db.Column(db.Integer, default=0)
    
    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    source_project = db.relationship('StudentProject', foreign_keys=[source_project_id], lazy='select')
    creator = db.relationship('User', foreign_keys=[created_by], lazy='select')
    
    def get_embed_url(self):
        """Convert video URL to embed URL for various platforms"""
        try:
            if not self.media_url or self.media_type != 'video':
                return None
            url = self.media_url
            
            # YouTube
            if 'youtube.com' in url or 'youtu.be' in url:
                if 'youtu.be/' in url:
                    video_id = url.split('youtu.be/')[-1].split('?')[0]
                elif 'watch?v=' in url:
                    video_id = url.split('watch?v=')[-1].split('&')[0]
                elif 'embed/' in url:
                    return url
                elif 'shorts/' in url:
                    video_id = url.split('shorts/')[-1].split('?')[0]
                else:
                    return None
                return f"https://www.youtube.com/embed/{video_id}"
            
            # Facebook
            if 'facebook.com' in url or 'fb.watch' in url:
                # Facebook videos need special handling
                encoded_url = url.replace('/', '%2F').replace(':', '%3A')
                return f"https://www.facebook.com/plugins/video.php?href={encoded_url}&show_text=false"
            
            # TikTok
            if 'tiktok.com' in url:
                # Extract video ID from TikTok URL
                if '/video/' in url:
                    video_id = url.split('/video/')[-1].split('?')[0]
                    return f"https://www.tiktok.com/embed/v2/{video_id}"
                return None
            
            # Instagram
            if 'instagram.com' in url:
                if '/reel/' in url or '/p/' in url:
                    # Get the post ID
                    if '/reel/' in url:
                        post_id = url.split('/reel/')[-1].split('/')[0].split('?')[0]
                    else:
                        post_id = url.split('/p/')[-1].split('/')[0].split('?')[0]
                    return f"https://www.instagram.com/p/{post_id}/embed"
                return None
            
            # Direct video URL (MP4, WebM, etc.) - return as is
            if any(ext in url.lower() for ext in ['.mp4', '.webm', '.mov', '.ogg']):
                return url
            
            # Unknown platform - return as is
            return url
        except Exception:
            return None
    
    def get_youtube_embed_url(self):
        """Backward compatible method - calls get_embed_url"""
        return self.get_embed_url()
    
    def is_direct_video(self):
        """Check if URL is a direct video file"""
        if not self.media_url:
            return False
        return any(ext in self.media_url.lower() for ext in ['.mp4', '.webm', '.mov', '.ogg'])
    
    def get_aspect_ratio_class(self):
        """Get CSS class for video aspect ratio - defaults to 16:9"""
        return 'ratio-16x9'  # Horizontal video (default)


class StudentVictory(db.Model):
    """Model for student achievements/victories"""
    __tablename__ = 'student_victory'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    achievement_type = db.Column(db.String(50))  # 'competition', 'certification', 'project', etc.
    image_url = db.Column(db.String(500))
    achievement_date = db.Column(db.Date)
    
    # Student info
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    student_name = db.Column(db.String(200))  # For non-registered students
    
    # Display settings
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    display_order = db.Column(db.Integer, default=0)
    
    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    student = db.relationship('User', foreign_keys=[student_id], lazy='select')
    creator = db.relationship('User', foreign_keys=[created_by], lazy='select')

