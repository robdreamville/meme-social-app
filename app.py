from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///emoji_social.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Add your Giphy API key here
GIPHY_API_KEY = os.getenv('GIPHY_API_KEY')  # Replace with your actual key

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gif_url = db.Column(db.String(500))   # For Giphy URLs
    emoji_text = db.Column(db.String(500))  # For emoji combinations
    upvotes = db.Column(db.Integer, default=0)
    downvotes = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    value = db.Column(db.Integer, nullable=False)  # 1 for upvote, -1 for downvote
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='uix_user_post'),)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create tables
with app.app_context():
    db.create_all()

@app.route('/')
def home():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    user_votes = {}
    if current_user.is_authenticated:
        votes = Vote.query.filter(Vote.user_id == current_user.id).all()
        user_votes = {vote.post_id: vote.value for vote in votes}
    return render_template('index.html', posts=posts, user_votes=user_votes)

@app.route('/post', methods=['GET', 'POST'])
@login_required
def create_post():
    if request.method == 'POST':
        emoji_text = request.form.get('emoji_text', '').strip()
        selected_gif = request.form.get('selected_gif', '').strip()
        
        # Must have either emoji text or gif
        if not emoji_text and not selected_gif:
            flash('Please add some emojis or select a GIF!', 'error')
            return render_template('create_post.html')
        
        # Create new post
        new_post = Post(
            emoji_text=emoji_text if emoji_text else None,
            gif_url=selected_gif if selected_gif else None
        )
        
        db.session.add(new_post)
        db.session.commit()
        
        flash('Post created successfully!', 'success')
        return redirect(url_for('home'))
    
    return render_template('create_post.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '').strip()
        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('signup.html')
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'error')
            return render_template('signup.html')
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Welcome aboard! 🎉', 'success')
        return redirect(url_for('home'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '').strip()
        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            flash('Invalid credentials.', 'error')
            return render_template('login.html')
        login_user(user)
        flash('Logged in successfully.', 'success')
        next_url = request.args.get('next')
        return redirect(next_url or url_for('home'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.', 'success')
    return redirect(url_for('home'))

@app.route('/api/search-gifs')
def search_gifs():
    query = request.args.get('q', '')
    if not query:
        return jsonify({'data': []})
    
    try:
        print(f"Searching Giphy for: {query}")
        if GIPHY_API_KEY:
            print(f"Using API key: {GIPHY_API_KEY[:10]}...")  # Only show first 10 chars for security
        
        response = requests.get(
            'https://api.giphy.com/v1/gifs/search',
            params={
                'api_key': GIPHY_API_KEY,
                'q': query,
                'limit': 20,
                'rating': 'pg-13'  # Keep it clean
            }
        )
        
        print(f"Giphy API status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Found {len(data.get('data', []))} GIFs")
            return jsonify(data)
        else:
            print(f"Giphy API error: {response.status_code} - {response.text}")
            return jsonify({'data': []})
            
    except Exception as e:
        print(f"Giphy API error: {e}")
        return jsonify({'data': []})

@app.route('/vote/<int:post_id>/<vote_type>')
@login_required
def vote(post_id, vote_type):
    post = Post.query.get_or_404(post_id)
    vote = Vote.query.filter_by(user_id=current_user.id, post_id=post_id).first()

    if vote_type not in ('up', 'down'):
        flash('Invalid vote action.', 'error')
        return redirect(url_for('home'))

    new_value = 1 if vote_type == 'up' else -1

    if vote is None:
        # First time voting on this post
        vote = Vote(user_id=current_user.id, post_id=post_id, value=new_value)
        if new_value == 1:
            post.upvotes += 1
        else:
            post.downvotes += 1
        db.session.add(vote)
    else:
        if vote.value == new_value:
            # Same vote clicked again -> remove vote
            if vote.value == 1:
                post.upvotes = max(0, post.upvotes - 1)
            else:
                post.downvotes = max(0, post.downvotes - 1)
            db.session.delete(vote)
        else:
            # Switch vote
            if new_value == 1:
                post.upvotes += 1
                post.downvotes = max(0, post.downvotes - 1)
            else:
                post.downvotes += 1
                post.upvotes = max(0, post.upvotes - 1)
            vote.value = new_value

    db.session.commit()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)