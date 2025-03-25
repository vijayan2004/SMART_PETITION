from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os
from datetime import datetime
from ai_utils import categorize_petition, analyze_sentiment, predict_petition_success
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length
from flask import session
from flask_session import Session

app = Flask(__name__)

# Database Configurations
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///smart_petitions.db'  # Single database for all models
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SESSION_TYPE'] = 'filesystem'  # Store sessions in filesystem
app.config['SESSION_PERMANENT'] = False  # Session expires when browser closes
app.config['SESSION_KEY_PREFIX'] = 'smart_petitions_'  # Unique prefix for session keys
app.config['SESSION_FILE_DIR'] = './flask_session/'  # Unique prefix for session keys

Session(app)  # ✅ Correct way to initialize Flask-Session


# Initialize SQLAlchemy with the app
db = SQLAlchemy(app)

# Initialize Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ---------------------------
# Database Models
# ---------------------------

# User Model
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # "admin", "user", "officer"
    city = db.Column(db.String(100), nullable=True)  # Location tracking
    tags = db.Column(db.String(255)) 

# Petition Model
class Petition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    priority = db.Column(db.String(50), default="Medium")
    city = db.Column(db.String(100), nullable=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    sentiment = db.Column(db.String(50), nullable=True)
    success_prediction = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(50), default="Pending")
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', foreign_keys=[user_id], backref='petitions')
    assigned_admin = db.relationship('User', foreign_keys=[assigned_to], backref='assigned_petitions')

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    petition_id = db.Column(db.Integer, db.ForeignKey('petition.id'), nullable=False)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    success_prediction = db.Column(db.Float, nullable=True)
    sentiment = db.Column(db.String(20), nullable=True)
    officer_assigned = db.Column(db.String(100), nullable=True)

    def __repr__(self):
        return f'<Report {self.id}>'

# ---------------------------
# Flask-Login User Loader
# ---------------------------
@login_manager.user_loader
def load_user(user_id):
    if '_user_id' in session:
        return User.query.get(int(session['_user_id']))
    return None

# ---------------------------
# Routes
# ---------------------------

@app.route('/')
def home():
    return redirect(url_for('login'))

# Login Route
from flask import session

from flask_login import login_user

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session.clear()  # Clear previous session
            login_user(user)  # Standard Flask-Login authentication

            # ✅ Store user ID in session explicitly
            session['_user_id'] = str(user.id)

            flash('Login successful!', 'success')

            if user.role == "admin":
                return redirect(url_for('admin_dashboard'))
            elif user.role == "officer":
                return redirect(url_for('officer_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))

        flash('Invalid username or password', 'danger')

    return render_template('login.html')


# Registration Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        city = request.form.get('city')

        if not username or not password or not role:
            flash("All fields are required!", "danger")
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash("Username already exists!", "danger")
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password, role=role, city=city)
        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

# ---------------------------
# Dashboard Routes
# ---------------------------

@app.route('/user_dashboard')
@login_required
def user_dashboard():
    petitions = Petition.query.filter_by(user_id=current_user.id).all()

    # Debugging: Print values to verify
    print(f"Total Petitions: {len(petitions)}")
    for p in petitions:
        print(f"Petition: {p.title}, Status: {p.status}")

    # Count petitions based on status
    total_petitions = len(petitions)
    pending_count = sum(1 for p in petitions if p.status.lower() == "pending")
    resolved_count = sum(1 for p in petitions if p.status.lower() == "resolved")

    return render_template('user_dashboard.html', 
                           petitions=petitions, 
                           total_petitions=total_petitions, 
                           pending_count=pending_count, 
                           resolved_count=resolved_count)

@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('user_dashboard'))

    # Fetch the admin's city from the database
    admin_city = current_user.city  

    # Get petitions only from users in the same city as the admin
    petitions = Petition.query.join(User, Petition.user_id == User.id).filter(User.city == admin_city).all()


    return render_template('admin_dashboard.html', petitions=petitions, admin_city=admin_city)


# ---------------------------
# Flask-WTF Form
# ---------------------------

class PetitionForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=100)])
    
    description = TextAreaField("Description", validators=[DataRequired(), Length(max=500)])
    
 
    submit = SubmitField("Submit Petition")

# ---------------------------
# Create & View Petitions
# ---------------------------

@app.route('/create_petition', methods=['GET', 'POST'])
@login_required
def create_petition():
    form = PetitionForm()
    if form.validate_on_submit():
        try:
            user_id = current_user.id
            city = current_user.city
            # AI-Powered Categorization
            category, priority, officer = categorize_petition(
                title=form.title.data, description=form.description.data
            )

            # AI Sentiment Analysis
            sentiment, polarity = analyze_sentiment(form.description.data)

            # Predict Success Probability
            success_prediction = predict_petition_success(
                title=form.title.data, description=form.description.data
            )

            admin = User.query.filter_by(role='admin', city=current_user.city).first()
            
            # Save petition to DB
            new_petition = Petition(
                title=form.title.data,
                description=form.description.data,
                category=category,
                priority=priority,
                city=city,
                date_created=datetime.utcnow(),
                sentiment=sentiment,
                success_prediction=success_prediction,
                status="Pending",
                user_id=user_id,
                assigned_to=admin.id if admin else None,
                
                
            )
            db.session.add(new_petition)
            db.session.commit()

            flash("Your petition has been submitted successfully!", "success")
            return redirect(url_for('user_dashboard'))

        except Exception as e:
            db.session.rollback()
            flash(f"Error processing petition: {str(e)}", "danger")
            return redirect(url_for('create_petition'))

    return render_template("create_petition.html", form=form)


@app.route('/submit_petition', methods=['POST'])
@login_required
def submit_petition():
    title = request.form['title']
    description = request.form['description']
    category = request.form['category']
    city = current_user.city

    # Generate AI-based tags
    tags = generate_tags(description)

    new_petition = Petition(title=title, description=description, category=category, tags=tags, city=city)
    db.session.add(new_petition)
    db.session.commit()
    
    flash("Petition submitted successfully!", "success")
    return redirect(url_for('user_dashboard'))



@app.route('/view_petitions/<int:petition_id>')
@login_required
def view_petitions(petition_id):
    petition = Petition.query.get_or_404(petition_id)
    return render_template('view_petition.html', petition=petition)


@app.route('/track_petition/<int:petition_id>')
def track_petition(petition_id):
    petition = Petition.query.get_or_404(petition_id)
    return render_template('track_petition.html', petition=petition)


@app.route('/delete_petition/<int:petition_id>', methods=['POST'])
@login_required
def delete_petition(petition_id):
    petition = Petition.query.get_or_404(petition_id)

    # Only allow the creator OR an admin to delete it
    if current_user.id != petition.user_id and current_user.role != 'admin':
        flash("You do not have permission to delete this petition!", "danger")
        return redirect(url_for('user_dashboard'))

    db.session.delete(petition)
    db.session.commit()
    
    flash("Petition deleted successfully!", "success")
    
    # Redirect based on role
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('user_dashboard'))


@app.route('/admin/pending_petitions')
@login_required
def admin_pending_petitions():
    if current_user.role != "admin":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("admin_dashboard"))

    # Explicitly specify the foreign key relationship
    pending_petitions = (
        Petition.query
        .join(User, Petition.user_id == User.id)  # Explicit join condition
        .filter(Petition.status == "Pending", User.city == current_user.city)
        .all()
    )

    return render_template("pending_petition.html", petitions=pending_petitions)

@app.route('/petition/in-progress/<int:petition_id>')
@login_required
def in_progress_petition(petition_id):
    petition = Petition.query.get_or_404(petition_id)
    petition.status = "In Progress"
    db.session.commit()
    flash("Petition marked as In Progress.", "info")
    return redirect(url_for('admin_pending_petitions'))

@app.route("/approve_petition/<int:petition_id>")
@login_required
def approve_petition(petition_id):
    petition = Petition.query.get_or_404(petition_id)
    petition.status = "resolved"
    db.session.commit()
    flash("Petition resolved successfully!", "success")
    return redirect(url_for("admin_pending_petitions"))


@app.route('/petition/reject/<int:petition_id>', methods=['POST'])
@login_required
def reject_petition(petition_id):
    petition = Petition.query.get_or_404(petition_id)  # Fetch petition or return 404
    petition.status = "Rejected"  # Update status to Rejected
    db.session.commit()
    flash("Petition has been rejected.", "danger")
    return redirect(url_for('admin_pending_petitions'))



from flask_login import login_required, current_user

@app.route("/admin/reports")
@login_required
def admin_reports():
    if not current_user.is_authenticated or current_user.role != "admin":
        return redirect(url_for("admin_login"))
    
    petitions = Petition.query.all()
    return render_template("reports.html", petitions=petitions)


@app.route('/view_petition/<int:petition_id>')
@login_required
def view_petition(petition_id):
    petition = Petition.query.get_or_404(petition_id)

    # Ensure users can only view their own petitions
    if current_user.role == "user" and petition.user_id != current_user.id:
        flash("Unauthorized access!", "danger")
        return redirect(url_for('user_dashboard'))

    # Officers can only view petitions assigned to them
    if current_user.role == "officer" and petition.assigned_to != current_user.id:
        flash("Unauthorized access!", "danger")
        return redirect(url_for('officer_dashboard'))

    return render_template("view_petition.html", petition=petition)


import csv
from flask import Response

@app.route('/download_petitions_csv')
@login_required
def download_petitions_csv():
    if current_user.role != "admin":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("admin_dashboard"))

    petitions = Petition.query.all()  # Fetch all petitions

    # Create CSV response
    output = []
    output.append(["Title", "Category", "Description", "Status", "City", "Date Created"])

    for petition in petitions:
        output.append([
            petition.title,
            petition.category,
            petition.description,
            petition.status,
            petition.city,
            petition.date_created.strftime("%Y-%m-%d"),
        ])

    # Generate response
    response = Response("\n".join([",".join(row) for row in output]), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=petitions.csv"

    return response


from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO

@app.route('/download_petitions_pdf')
@login_required
def download_petitions_pdf():
    if current_user.role != "admin":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("admin_reports"))

    petitions = Petition.query.all()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setFont("Helvetica", 12)

    pdf.drawString(200, 750, "SMART PETITIONS - Analytics Report")
    pdf.line(50, 740, 550, 740)  

    y = 720
    for petition in petitions:
        pdf.drawString(50, y, f"Title: {petition.title}")
        pdf.drawString(50, y - 20, f"Category: {petition.category}")
        pdf.drawString(50, y - 40, f"Status: {petition.status}")
        pdf.drawString(50, y - 60, f"City: {petition.city}")
        pdf.drawString(50, y - 80, "-" * 50)
        y -= 100  

        if y < 50:
            pdf.showPage()
            y = 750

    pdf.save()
    buffer.seek(0)

    return Response(buffer, mimetype="application/pdf", headers={"Content-Disposition": "attachment; filename=petitions_report.pdf"})



# ---------------------------
# Logout Route
# ---------------------------

@app.route('/logout')
@login_required
def logout():
    # ✅ Remove only the current user's session
    session.pop('_user_id', None)
    
    logout_user()
    flash("Logged out successfully!", "success")
    return redirect(url_for('login'))

# ---------------------------
# Run Flask App
# ---------------------------

if __name__ == '__main__':
    with app.app_context():  # Ensure that we are in an application context
        # Create all tables
        db.create_all()

    app.run(debug=True)
