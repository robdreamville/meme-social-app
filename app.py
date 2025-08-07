from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///emoji_social.db'

# Add your Giphy API key here
GIPHY_API_KEY = os.getenv('GIPHY_API_KEY')  # Replace with your actual key

db = SQLAlchemy(app)

# Database Models
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gif_url = db.Column(db.String(500))   # For Giphy URLs
    emoji_text = db.Column(db.String(500))  # For emoji combinations
    upvotes = db.Column(db.Integer, default=0)
    downvotes = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Create tables
with app.app_context():
    db.create_all()

@app.route('/')
def home():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template('index.html', posts=posts)

@app.route('/post', methods=['GET', 'POST'])
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

@app.route('/api/search-gifs')
def search_gifs():
    query = request.args.get('q', '')
    if not query:
        return jsonify({'data': []})
    
    try:
        print(f"Searching Giphy for: {query}")
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
def vote(post_id, vote_type):
    post = Post.query.get_or_404(post_id)
    if vote_type == 'up':
        post.upvotes += 1
    elif vote_type == 'down':
        post.downvotes += 1
    
    db.session.commit()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)