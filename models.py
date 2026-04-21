from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, company, student
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class StudentProfile(db.Model):
    __tablename__ = "student_profile"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    contact = db.Column(db.String(20), nullable=False)
    department = db.Column(db.String(100))
    cgpa = db.Column(db.Float)
    resume_filename = db.Column(db.String(255))
    blacklisted = db.Column(db.Boolean, default=False)


class CompanyProfile(db.Model):
    __tablename__ = "company_profile"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    company_name = db.Column(db.String(150), nullable=False)
    hr_contact = db.Column(db.String(20), nullable=False)
    website = db.Column(db.String(255))
    approval_status = db.Column(db.String(20), default="pending")  # pending, approved, rejected
    blacklisted = db.Column(db.Boolean, default=False)


class PlacementDrive(db.Model):
    __tablename__ = "placement_drive"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company_profile.id"), nullable=False)
    job_title = db.Column(db.String(150), nullable=False)
    job_description = db.Column(db.Text, nullable=False)
    eligibility_criteria = db.Column(db.String(255))
    application_deadline = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default="pending")  # pending, approved, closed, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Application(db.Model):
    __tablename__ = "application"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student_profile.id"), nullable=False)
    drive_id = db.Column(db.Integer, db.ForeignKey("placement_drive.id"), nullable=False)
    application_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="applied")  # applied, shortlisted, selected, rejected

    __table_args__ = (
        db.UniqueConstraint("student_id", "drive_id", name="unique_student_drive_application"),
    )