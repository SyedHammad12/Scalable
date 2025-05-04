from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from flask_login import (
    LoginManager, UserMixin,
    login_user, logout_user,
    login_required, current_user
)
from bson.objectid import ObjectId
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

app.config["MONGO_URI"] = (
    "mongodb+srv://hadishah786000:hadishah123@cluster0.6c07b.mongodb.net/video_app?retryWrites=true&w=majority&appName=Cluster0"
)
mongo = PyMongo(app)

bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, user_doc):
        self.id = str(user_doc['_id'])
        self.username = user_doc['username']
        self.role = user_doc['role']

@login_manager.user_loader
def load_user(user_id):
    user_doc = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    return User(user_doc) if user_doc else None

@app.route('/')
def index():
    return redirect(url_for('consumer_dashboard')) if current_user.is_authenticated else render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        if mongo.db.users.find_one({'username': username}):
            return "Username already exists"
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        role = request.form['role']
        mongo.db.users.insert_one({
            'username': username,
            'password': password,
            'role': role,
            'following': [],
            'followers': []
        })
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_doc = mongo.db.users.find_one({'username': username})
        if user_doc and bcrypt.check_password_hash(user_doc['password'], password):
            login_user(User(user_doc))
            return redirect(url_for('creator_dashboard' if user_doc['role'] == 'creator' else 'consumer_dashboard'))
        return "Invalid credentials"
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/creator', methods=['GET', 'POST'])
@login_required
def creator_dashboard():
    if current_user.role != 'creator':
        return "Access denied"
    if request.method == 'POST':
        title = request.form['title']
        caption = request.form['caption']
        location = request.form['location']
        people = request.form['people']
        file = request.files['file']
        if file and file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
            filename = file.filename
            filepath = os.path.join('static/uploads', filename)
            file.save(filepath)
            mongo.db.posts.insert_one({
                'title': title,
                'caption': caption,
                'location': location,
                'people': people,
                'filename': filename,
                'creator': current_user.username,
                'likes': 0
            })
        else:
            return "Only image files are allowed."
    raw = list(mongo.db.posts.find({'creator': current_user.username}))
    return render_template('creator.html', posts=raw)

@app.route('/consumer')
@login_required
def consumer_dashboard():
    if current_user.role != 'consumer':
        return "Access denied"
    raw_posts = list(mongo.db.posts.find())
    posts = []
    for post in raw_posts:
        post['comments_count'] = mongo.db.comments.count_documents({'post_id': str(post['_id'])})
        post['likes'] = post.get('likes', 0)
        posts.append(post)
    user_doc = mongo.db.users.find_one({'_id': ObjectId(current_user.id)})
    following_docs = mongo.db.users.find({'_id': {'$in': [ObjectId(f) for f in user_doc.get('following', [])]}})
    followers_docs = mongo.db.users.find({'_id': {'$in': [ObjectId(f) for f in user_doc.get('followers', [])]}})
    return render_template('consumer.html', posts=posts, following=list(following_docs), followers=list(followers_docs))

@app.route('/post/<post_id>', methods=['GET', 'POST'])
@login_required
def view_post(post_id):
    post = mongo.db.posts.find_one({'_id': ObjectId(post_id)})
    if request.method == 'POST':
        comment = request.form['comment']
        mongo.db.comments.insert_one({
            'post_id': post_id,
            'user': current_user.username,
            'comment': comment
        })
        return redirect(url_for('view_post', post_id=post_id))
    comments = list(mongo.db.comments.find({'post_id': post_id}))
    return render_template('view_post.html', post=post, comments=comments)

@app.route('/like/<post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    mongo.db.posts.update_one({'_id': ObjectId(post_id)}, {'$inc': {'likes': 1}})
    return redirect(url_for('consumer_dashboard'))

@app.route('/follow/<user_id>', methods=['POST'])
@login_required
def follow(user_id):
    me = ObjectId(current_user.id)
    them = ObjectId(user_id)
    mongo.db.users.update_one({'_id': me}, {'$addToSet': {'following': str(them)}})
    mongo.db.users.update_one({'_id': them}, {'$addToSet': {'followers': str(me)}})
    return jsonify({'status': 'success'})

@app.route('/search', methods=['GET'])
@login_required
def search():
    if current_user.role != 'consumer':
        return "Access denied"
    query = request.args.get('query', '').strip()
    if not query:
        return redirect(url_for('consumer_dashboard'))
    search_filter = {
        '$or': [
            {'title': {'$regex': query, '$options': 'i'}},
            {'caption': {'$regex': query, '$options': 'i'}},
            {'location': {'$regex': query, '$options': 'i'}}
        ]
    }
    raw_posts = list(mongo.db.posts.find(search_filter))
    posts = []
    for post in raw_posts:
        post['comments_count'] = mongo.db.comments.count_documents({'post_id': str(post['_id'])})
        post['likes'] = post.get('likes', 0)
        posts.append(post)
    return render_template('search_results.html', posts=posts, query=query)

if __name__ == '__main__':
    os.makedirs('static/uploads', exist_ok=True)
    port = int(os.environ.get('PORT', 8000))  # Use PORT env var or default to 8000
    app.run(host='0.0.0.0', port=port, debug=True)
