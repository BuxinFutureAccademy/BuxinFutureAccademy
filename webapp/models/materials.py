from datetime import datetime
from ..extensions import db


class LearningMaterial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    class_id = db.Column(db.String(50), nullable=False)
    class_type = db.Column(db.String(20), nullable=False)
    actual_class_id = db.Column(db.Integer, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def class_name(self):
        from .users import User  # local import to avoid circulars
        from .classes import IndividualClass, GroupClass
        if self.class_id and self.class_id.startswith('student_'):
            try:
                student_id = int(self.class_id.replace('student_', ''))
            except Exception:
                return "Unknown Class"
            student = User.query.get(student_id)
            if student:
                return f"👤 {student.first_name} {student.last_name}"
            return "Unknown Student"
        if self.class_type == 'individual':
            cls = IndividualClass.query.get(self.actual_class_id)
            return f"📖 {cls.name}" if cls else "Unknown Individual Class"
        if self.class_type == 'group':
            cls = GroupClass.query.get(self.actual_class_id)
            return f"🎓 {cls.name}" if cls else "Unknown Group Class"
        return "Unknown Class"
