import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from flask_login import (
    LoginManager,
    login_user,
    login_required,
    logout_user,
    current_user,
    UserMixin
)
from werkzeug.security import generate_password_hash, check_password_hash

# ---- App & Config ----
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI']   = 'sqlite:///photos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER']            = 'static/uploads'
app.config['SECRET_KEY']               = 'your_secret_key'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'home'

# ---- Models ----
class User(UserMixin, db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role     = db.Column(db.String(20), nullable=False)

class Photo(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    title     = db.Column(db.String(100))
    caption   = db.Column(db.String(255))
    image_url = db.Column(db.String(255))
    likes     = db.relationship('Like', backref='photo', lazy=True)
    comments  = db.relationship('Comment', backref='photo', lazy=True)

class Like(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    photo_id = db.Column(db.Integer, db.ForeignKey('photo.id'), nullable=False)
    user_id  = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user     = db.relationship('User', backref='likes')

class Comment(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    content   = db.Column(db.String(255))
    photo_id  = db.Column(db.Integer, db.ForeignKey('photo.id'), nullable=False)
    user_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user      = db.relationship('User', backref='comments')

class Notification(db.Model):
    id      = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(255))

# ---- Login Loader ----
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---- Routes ----

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role     = request.form['role']
        user = User.query.filter_by(username=username, role=role).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('upload' if role == 'creator' else 'photos'))
        flash('Invalid credentials or role.', 'danger')
    return render_template('index.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if current_user.role != 'creator':
        flash('Only creators may upload.', 'danger')
        return redirect(url_for('photos'))
    if request.method == 'POST':
        title   = request.form['title']
        caption = request.form['caption']
        file    = request.files['image']
        if file and file.filename:
            fn   = secure_filename(file.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], fn)
            file.save(path)
            url = f'/static/uploads/{fn}'
            db.session.add(Photo(title=title, caption=caption, image_url=url))
            db.session.add(Notification(message=f'New photo uploaded: {title}'))
            db.session.commit()
            flash('Photo uploaded!', 'success')
            return redirect(url_for('photos'))
        flash('No file selected.', 'danger')
    return render_template('upload.html')

@app.route('/photos')
@login_required
def photos():
    return render_template('photos.html', photos=Photo.query.all())

@app.route('/like/<int:photo_id>', methods=['POST'])
@login_required
def like(photo_id):
    db.session.add(Like(photo_id=photo_id, user_id=current_user.id))
    db.session.add(Notification(message=f'Photo {photo_id} liked by {current_user.username}'))
    db.session.commit()
    return redirect(url_for('photos'))

@app.route('/comment/<int:photo_id>', methods=['POST'])
@login_required
def comment(photo_id):
    text = request.form['comment_content']
    db.session.add(Comment(photo_id=photo_id, content=text, user_id=current_user.id))
    db.session.add(Notification(message=f'{current_user.username} commented on {photo_id}: {text}'))
    db.session.commit()
    return redirect(url_for('photos'))

@app.route('/notifications')
@login_required
def notifications_page():
    return render_template('notifications.html', notifications=Notification.query.all())

# ---- Database Initialization ----
def create_db_and_seed():
    db.create_all()
    if not User.query.filter_by(username='creator1').first():
        db.session.add(User(username='creator1', password=generate_password_hash('creatorpass'), role='creator'))
    if not User.query.filter_by(username='consumer1').first():
        db.session.add(User(username='consumer1', password=generate_password_hash('consumerpass1'), role='consumer'))
    if not User.query.filter_by(username='consumer2').first():
        db.session.add(User(username='consumer2', password=generate_password_hash('consumerpass2'), role='consumer'))
    db.session.commit()

# ---- Entry Point ----
if __name__ == '__main__':
    with app.app_context():
        create_db_and_seed()
    app.run(debug=True)
