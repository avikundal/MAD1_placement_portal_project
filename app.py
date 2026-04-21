from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import db, User, StudentProfile, CompanyProfile, PlacementDrive, Application
from datetime import datetime
import os


app = Flask(__name__)
app.config["SECRET_KEY"] = "placement-portal-secret"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///placement_portal.sqlite3"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/company/drives")
def view_company_drives():
    if "user_id" not in session or session.get("role") != "company":
        return redirect(url_for("login"))

    company = CompanyProfile.query.filter_by(user_id=session.get("user_id")).first()
    if not company or company.approval_status != "approved":
        return redirect(url_for("dashboard"))

    drives = PlacementDrive.query.filter_by(company_id=company.id).order_by(PlacementDrive.id.desc()).all()
    return render_template("company_drives.html", drives=drives, company=company)


@app.route("/company/drives/create", methods=["GET", "POST"])
def create_drive():
    if "user_id" not in session or session.get("role") != "company":
        return redirect(url_for("login"))

    company = CompanyProfile.query.filter_by(user_id=session.get("user_id")).first()
    if not company or company.approval_status != "approved":
        return redirect(url_for("dashboard"))

    if company.blacklisted:
        return redirect(url_for("dashboard"))

    error = None
    success = None

    if request.method == "POST":
        job_title = request.form.get("job_title")
        job_description = request.form.get("job_description")
        eligibility_criteria = request.form.get("eligibility_criteria")
        application_deadline = request.form.get("application_deadline")

        try:
            deadline_obj = datetime.strptime(application_deadline, "%Y-%m-%d").date()

            drive = PlacementDrive(
                company_id=company.id,
                job_title=job_title,
                job_description=job_description,
                eligibility_criteria=eligibility_criteria,
                application_deadline=deadline_obj,
                status="pending"
            )
            db.session.add(drive)
            db.session.commit()
            success = "Placement drive created successfully and sent for admin approval."
        except Exception:
            db.session.rollback()
            error = "Invalid date or input. Please try again."

    return render_template("create_drive.html", error=error, success=success)


@app.route("/company/drive/<int:drive_id>/edit", methods=["GET", "POST"])
def edit_drive(drive_id):
    if "user_id" not in session or session.get("role") != "company":
        return redirect(url_for("login"))

    company = CompanyProfile.query.filter_by(user_id=session.get("user_id")).first()
    if not company or company.blacklisted:
        return redirect(url_for("dashboard"))

    drive = PlacementDrive.query.filter_by(id=drive_id, company_id=company.id).first()
    if not drive:
        return redirect(url_for("view_company_drives"))

    error = None

    if request.method == "POST":
        try:
            drive.job_title = request.form.get("job_title")
            drive.job_description = request.form.get("job_description")
            drive.eligibility_criteria = request.form.get("eligibility_criteria")
            drive.application_deadline = datetime.strptime(
                request.form.get("application_deadline"), "%Y-%m-%d"
            ).date()
            db.session.commit()
            return redirect(url_for("view_company_drives"))
        except Exception:
            db.session.rollback()
            error = "Invalid date or input. Please try again."

    return render_template("edit_drive.html", drive=drive, error=error)


@app.route("/company/drive/<int:drive_id>/close")
def close_drive(drive_id):
    if "user_id" not in session or session.get("role") != "company":
        return redirect(url_for("login"))

    company = CompanyProfile.query.filter_by(user_id=session.get("user_id")).first()
    if not company or company.blacklisted:
        return redirect(url_for("dashboard"))

    drive = PlacementDrive.query.filter_by(id=drive_id, company_id=company.id).first()
    if drive:
        drive.status = "closed"
        db.session.commit()

    return redirect(url_for("view_company_drives"))


@app.route("/company/drive/<int:drive_id>/delete")
def delete_drive(drive_id):
    if "user_id" not in session or session.get("role") != "company":
        return redirect(url_for("login"))

    company = CompanyProfile.query.filter_by(user_id=session.get("user_id")).first()
    if not company or company.blacklisted:
        return redirect(url_for("dashboard"))

    drive = PlacementDrive.query.filter_by(id=drive_id, company_id=company.id).first()
    if drive:
        Application.query.filter_by(drive_id=drive.id).delete()
        db.session.delete(drive)
        db.session.commit()

    return redirect(url_for("view_company_drives"))


@app.route("/company/drive/<int:drive_id>/applicants")
def view_applicants(drive_id):
    if "user_id" not in session or session.get("role") != "company":
        return redirect(url_for("login"))

    company = CompanyProfile.query.filter_by(user_id=session.get("user_id")).first()
    if not company or company.blacklisted:
        return redirect(url_for("dashboard"))

    drive = PlacementDrive.query.filter_by(id=drive_id, company_id=company.id).first()
    if not drive:
        return redirect(url_for("view_company_drives"))

    applications = Application.query.filter_by(drive_id=drive.id).order_by(Application.id.desc()).all()
    students = {s.id: s for s in StudentProfile.query.all()}

    return render_template(
        "view_applicants.html",
        drive=drive,
        applications=applications,
        students=students
    )


@app.route("/company/application/<int:application_id>/status/<string:new_status>")
def update_application_status(application_id, new_status):
    if "user_id" not in session or session.get("role") != "company":
        return redirect(url_for("login"))

    allowed_statuses = ["shortlisted", "selected", "rejected"]
    if new_status not in allowed_statuses:
        return redirect(url_for("dashboard"))

    company = CompanyProfile.query.filter_by(user_id=session.get("user_id")).first()
    if not company or company.blacklisted:
        return redirect(url_for("dashboard"))

    application = Application.query.filter_by(id=application_id).first()
    if not application:
        return redirect(url_for("dashboard"))

    drive = PlacementDrive.query.filter_by(id=application.drive_id, company_id=company.id).first()
    if not drive:
        return redirect(url_for("dashboard"))

    application.status = new_status
    db.session.commit()

    return redirect(url_for("view_applicants", drive_id=drive.id))


@app.route("/admin/drives")
def manage_drives():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    drives = PlacementDrive.query.order_by(PlacementDrive.id.desc()).all()
    companies = {c.id: c for c in CompanyProfile.query.all()}
    return render_template("manage_drives.html", drives=drives, companies=companies)


@app.route("/admin/drive/<int:drive_id>/approve")
def approve_drive(drive_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    drive = PlacementDrive.query.get(drive_id)
    if drive:
        drive.status = "approved"
        db.session.commit()

    return redirect(url_for("manage_drives"))


@app.route("/admin/drive/<int:drive_id>/reject")
def reject_drive(drive_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    drive = PlacementDrive.query.get(drive_id)
    if drive:
        drive.status = "rejected"
        db.session.commit()

    return redirect(url_for("manage_drives"))


@app.route("/student/drives")
def student_drives():
    if "user_id" not in session or session.get("role") != "student":
        return redirect(url_for("login"))

    student = StudentProfile.query.filter_by(user_id=session.get("user_id")).first()
    drives = PlacementDrive.query.filter_by(status="approved").order_by(PlacementDrive.id.desc()).all()
    companies = {c.id: c for c in CompanyProfile.query.all()}

    applied_drive_ids = set()
    if student:
        applications = Application.query.filter_by(student_id=student.id).all()
        applied_drive_ids = {a.drive_id for a in applications}

    return render_template(
        "student_drives.html",
        drives=drives,
        companies=companies,
        applied_drive_ids=applied_drive_ids
    )


@app.route("/student/apply/<int:drive_id>")
def apply_drive(drive_id):
    if "user_id" not in session or session.get("role") != "student":
        return redirect(url_for("login"))

    student = StudentProfile.query.filter_by(user_id=session.get("user_id")).first()
    drive = PlacementDrive.query.filter_by(id=drive_id, status="approved").first()

    if not student or not drive:
        return redirect(url_for("student_drives"))

    if student.blacklisted:
        return redirect(url_for("student_drives"))

    existing_application = Application.query.filter_by(student_id=student.id, drive_id=drive.id).first()
    if not existing_application:
        application = Application(
            student_id=student.id,
            drive_id=drive.id,
            status="applied"
        )
        db.session.add(application)
        db.session.commit()

    return redirect(url_for("student_drives"))


@app.route("/student/applications")
def my_applications():
    if "user_id" not in session or session.get("role") != "student":
        return redirect(url_for("login"))

    student = StudentProfile.query.filter_by(user_id=session.get("user_id")).first()
    applications = []
    companies = {}

    if student:
        applications = Application.query.filter_by(student_id=student.id).order_by(Application.id.desc()).all()
        companies = {c.id: c for c in CompanyProfile.query.all()}

    drives = {d.id: d for d in PlacementDrive.query.all()}

    return render_template(
        "my_applications.html",
        applications=applications,
        drives=drives,
        companies=companies
    )


@app.route("/admin/applications")
def admin_applications():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    applications = Application.query.order_by(Application.id.desc()).all()
    students = {s.id: s for s in StudentProfile.query.all()}
    drives = {d.id: d for d in PlacementDrive.query.all()}
    companies = {c.id: c for c in CompanyProfile.query.all()}

    return render_template(
        "admin_applications.html",
        applications=applications,
        students=students,
        drives=drives,
        companies=companies
    )


@app.route("/admin/students")
def manage_students():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    q = request.args.get("q", "").strip()

    query = StudentProfile.query
    if q:
        query = query.filter(
            (StudentProfile.full_name.ilike(f"%{q}%")) |
            (StudentProfile.contact.ilike(f"%{q}%")) |
            (StudentProfile.id.cast(db.String).ilike(f"%{q}%"))
        )

    students = query.order_by(StudentProfile.id.desc()).all()
    return render_template("manage_students.html", students=students, q=q)


@app.route("/admin/student/<int:student_id>/delete")
def delete_student(student_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    student = StudentProfile.query.get(student_id)
    if student:
        Application.query.filter_by(student_id=student.id).delete()
        user = User.query.get(student.user_id)

        if student.resume_filename:
            file_path = os.path.join(app.root_path, "static", "uploads", student.resume_filename)
            if os.path.exists(file_path):
                os.remove(file_path)

        db.session.delete(student)
        if user and user.role != "admin":
            db.session.delete(user)
        db.session.commit()

    return redirect(url_for("manage_students"))


@app.route("/admin/student/<int:student_id>/toggle_blacklist")
def toggle_student_blacklist(student_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    student = StudentProfile.query.get(student_id)
    if student:
        student.blacklisted = not student.blacklisted
        db.session.commit()

    return redirect(url_for("manage_students"))


@app.route("/admin/companies/search")
def search_companies():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    q = request.args.get("q", "").strip()

    query = CompanyProfile.query
    if q:
        query = query.filter(CompanyProfile.company_name.ilike(f"%{q}%"))

    companies = query.order_by(CompanyProfile.id.desc()).all()
    return render_template("search_companies.html", companies=companies, q=q)


@app.route("/admin/company/<int:company_id>/delete")
def delete_company(company_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    company = CompanyProfile.query.get(company_id)
    if company:
        drives = PlacementDrive.query.filter_by(company_id=company.id).all()
        for drive in drives:
            Application.query.filter_by(drive_id=drive.id).delete()
            db.session.delete(drive)

        user = User.query.get(company.user_id)
        db.session.delete(company)
        if user and user.role != "admin":
            db.session.delete(user)
        db.session.commit()

    return redirect(url_for("search_companies"))


@app.route("/admin/company/<int:company_id>/toggle_blacklist")
def toggle_company_blacklist(company_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    company = CompanyProfile.query.get(company_id)
    if company:
        company.blacklisted = not company.blacklisted
        db.session.commit()

    return redirect(url_for("search_companies"))


@app.route("/admin/user/<int:user_id>/toggle_active")
def toggle_user_active(user_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    user = User.query.get(user_id)
    if user and user.role != "admin":
        user.active = not user.active
        db.session.commit()

    return redirect(url_for("dashboard"))


@app.route("/student/profile", methods=["GET", "POST"])
def edit_student_profile():
    if "user_id" not in session or session.get("role") != "student":
        return redirect(url_for("login"))

    student = StudentProfile.query.filter_by(user_id=session.get("user_id")).first()
    if not student:
        return redirect(url_for("dashboard"))

    success = None
    error = None

    if request.method == "POST":
        try:
            student.full_name = request.form.get("full_name")
            student.contact = request.form.get("contact")
            student.department = request.form.get("department")

            cgpa = request.form.get("cgpa")
            student.cgpa = float(cgpa) if cgpa else None

            resume = request.files.get("resume")
            if resume and resume.filename:
                filename = secure_filename(resume.filename)
                upload_folder = os.path.join("static", "uploads")
                os.makedirs(upload_folder, exist_ok=True)

                filename = f"{student.user_id}_{filename}"
                file_path = os.path.join(upload_folder, filename)
                resume.save(file_path)

                student.resume_filename = filename

            db.session.commit()
            success = "Profile updated successfully."
        except Exception as e:
            db.session.rollback()
            error = f"Error updating profile: {str(e)}"

    return render_template(
        "edit_student_profile.html",
        student=student,
        success=success,
        error=error
    )


@app.route("/resume/<path:filename>")
def uploaded_resume(filename):
    if "user_id" not in session:
        return redirect(url_for("login"))

    upload_folder = os.path.join(app.root_path, "static", "uploads")
    return send_from_directory(upload_folder, filename, as_attachment=False)


@app.route("/register/student", methods=["GET", "POST"])
def register_student():
    error = None
    success = None

    if request.method == "POST":
        full_name = request.form.get("full_name")
        email = request.form.get("email")
        password = request.form.get("password")
        contact = request.form.get("contact")
        department = request.form.get("department")
        cgpa = request.form.get("cgpa")

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            error = "Email already registered"
        else:
            user = User(
                email=email,
                password=generate_password_hash(password),
                role="student",
                active=True
            )
            db.session.add(user)
            db.session.commit()

            student_profile = StudentProfile(
                user_id=user.id,
                full_name=full_name,
                contact=contact,
                department=department,
                cgpa=float(cgpa) if cgpa else None,
                blacklisted=False
            )
            db.session.add(student_profile)
            db.session.commit()

            success = "Student registration successful. Please login."

    return render_template("register_student.html", error=error, success=success)


@app.route("/register/company", methods=["GET", "POST"])
def register_company():
    error = None
    success = None

    if request.method == "POST":
        company_name = request.form.get("company_name")
        email = request.form.get("email")
        password = request.form.get("password")
        hr_contact = request.form.get("hr_contact")
        website = request.form.get("website")

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            error = "Email already registered"
        else:
            user = User(
                email=email,
                password=generate_password_hash(password),
                role="company",
                active=True
            )
            db.session.add(user)
            db.session.commit()

            company_profile = CompanyProfile(
                user_id=user.id,
                company_name=company_name,
                hr_contact=hr_contact,
                website=website,
                approval_status="pending",
                blacklisted=False
            )
            db.session.add(company_profile)
            db.session.commit()

            success = "Company registration submitted. Wait for admin approval."

    return render_template("register_company.html", error=error, success=success)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if user and not user.active:
            error = "Your account is deactivated. Contact admin."
            return render_template("login.html", error=error)

        if user and check_password_hash(user.password, password):
            if user.role == "student":
                student = StudentProfile.query.filter_by(user_id=user.id).first()
                if student and student.blacklisted:
                    error = "Your student account is blacklisted."
                    return render_template("login.html", error=error)

            if user.role == "company":
                company = CompanyProfile.query.filter_by(user_id=user.id).first()

                if company and company.blacklisted:
                    error = "Your company account is blacklisted."
                    return render_template("login.html", error=error)

                if not company or company.approval_status != "approved":
                    error = "Company account is pending admin approval."
                    return render_template("login.html", error=error)

            session["user_id"] = user.id
            session["role"] = user.role
            session["email"] = user.email
            return redirect(url_for("dashboard"))

        error = "Invalid email or password"

    return render_template("login.html", error=error)


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session.get("user_id")
    role = session.get("role")
    email = session.get("email")

    if role == "admin":
        total_students = StudentProfile.query.count()
        total_companies = CompanyProfile.query.count()
        total_applications = Application.query.count()
        total_drives = PlacementDrive.query.count()

        return render_template(
            "admin_dashboard.html",
            email=email,
            total_students=total_students,
            total_companies=total_companies,
            total_applications=total_applications,
            total_drives=total_drives
        )

    if role == "student":
        student = StudentProfile.query.filter_by(user_id=user_id).first()
        approved_drives_count = PlacementDrive.query.filter_by(status="approved").count()
        applied_count = 0
        selected_count = 0
        if student:
            applied_count = Application.query.filter_by(student_id=student.id).count()
            selected_count = Application.query.filter_by(student_id=student.id, status="selected").count()
        return render_template(
            "student_dashboard.html",
            email=email,
            student=student,
            approved_drives_count=approved_drives_count,
            applied_count=applied_count,
            selected_count=selected_count
        )

    if role == "company":
        company = CompanyProfile.query.filter_by(user_id=user_id).first()
        total_drives = 0
        total_applicants = 0
        approved_drives = 0
        if company:
            company_drives = PlacementDrive.query.filter_by(company_id=company.id).all()
            total_drives = len(company_drives)
            approved_drives = sum(1 for d in company_drives if d.status == "approved")
            drive_ids = [d.id for d in company_drives]
            if drive_ids:
                total_applicants = Application.query.filter(Application.drive_id.in_(drive_ids)).count()
        return render_template(
            "company_dashboard.html",
            email=email,
            company=company,
            total_drives=total_drives,
            approved_drives=approved_drives,
            total_applicants=total_applicants
        )

    return redirect(url_for("logout"))


@app.route("/admin/companies")
def manage_companies():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    companies = CompanyProfile.query.order_by(CompanyProfile.id).all()
    return render_template("manage_companies.html", companies=companies)


@app.route("/admin/company/<int:company_id>/approve")
def approve_company(company_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    company = CompanyProfile.query.get(company_id)
    if company:
        company.approval_status = "approved"
        db.session.commit()

    return redirect(url_for("manage_companies"))


@app.route("/admin/company/<int:company_id>/reject")
def reject_company(company_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    company = CompanyProfile.query.get(company_id)
    if company:
        company.approval_status = "rejected"
        db.session.commit()

    return redirect(url_for("manage_companies"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


def setup_database():
    with app.app_context():
        db.create_all()

        admin = User.query.filter_by(email="admin@placement.com", role="admin").first()
        if not admin:
            admin = User(
                email="admin@placement.com",
                password=generate_password_hash("admin123"),
                role="admin",
                active=True,
            )
            db.session.add(admin)
            db.session.commit()
            print("Admin created: admin@placement.com / admin123")
        else:
            print("Admin already exists.")


if __name__ == "__main__":
    setup_database()
    app.run(debug=True)