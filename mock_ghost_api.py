#!/usr/bin/env python3
"""
Mock Ghost API server for testing the Reddit Ghost Publisher pipeline
"""
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify
import threading
import time

app = Flask(__name__)

# In-memory storage for mock data
mock_posts = {}
mock_tags = {}
mock_images = {}

@app.route('/ghost/api/v5/admin/site/', methods=['GET'])
def get_site():
    """Mock site info endpoint"""
    return jsonify({
        "site": {
            "title": "Mock Ghost Site",
            "description": "Test site for Reddit Ghost Publisher",
            "url": "http://localhost:3001",
            "version": "5.0.0"
        }
    })

@app.route('/ghost/api/v5/admin/posts/', methods=['GET', 'POST'])
def handle_posts():
    """Mock posts endpoint"""
    if request.method == 'GET':
        # Return list of posts
        posts_list = list(mock_posts.values())
        return jsonify({"posts": posts_list})
    
    elif request.method == 'POST':
        # Create new post
        data = request.get_json()
        if not data or 'posts' not in data or not data['posts']:
            return jsonify({"errors": [{"message": "Invalid post data"}]}), 422
        
        post_data = data['posts'][0]
        post_id = str(uuid.uuid4())
        
        # Create mock post
        mock_post = {
            "id": post_id,
            "uuid": str(uuid.uuid4()),
            "title": post_data.get("title", "Untitled"),
            "slug": post_data.get("title", "untitled").lower().replace(" ", "-"),
            "html": post_data.get("html", ""),
            "status": post_data.get("status", "draft"),
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "published_at": datetime.utcnow().isoformat() + "Z" if post_data.get("status") == "published" else None,
            "url": f"http://localhost:3001/mock-post-{post_id}/",
            "excerpt": post_data.get("excerpt", ""),
            "feature_image": post_data.get("feature_image"),
            "tags": post_data.get("tags", [])
        }
        
        mock_posts[post_id] = mock_post
        
        print(f"📝 Mock Ghost: Created post '{mock_post['title']}' (ID: {post_id})")
        
        return jsonify({"posts": [mock_post]}), 201

@app.route('/ghost/api/v5/admin/posts/<post_id>/', methods=['GET', 'PUT', 'DELETE'])
def handle_post(post_id):
    """Mock individual post endpoint"""
    if request.method == 'GET':
        if post_id not in mock_posts:
            return jsonify({"errors": [{"message": "Post not found"}]}), 404
        return jsonify({"posts": [mock_posts[post_id]]})
    
    elif request.method == 'PUT':
        if post_id not in mock_posts:
            return jsonify({"errors": [{"message": "Post not found"}]}), 404
        
        data = request.get_json()
        if not data or 'posts' not in data:
            return jsonify({"errors": [{"message": "Invalid post data"}]}), 422
        
        post_data = data['posts'][0]
        mock_post = mock_posts[post_id]
        
        # Update post
        mock_post.update({
            "title": post_data.get("title", mock_post["title"]),
            "html": post_data.get("html", mock_post["html"]),
            "status": post_data.get("status", mock_post["status"]),
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "tags": post_data.get("tags", mock_post["tags"])
        })
        
        if post_data.get("status") == "published" and not mock_post["published_at"]:
            mock_post["published_at"] = datetime.utcnow().isoformat() + "Z"
        
        print(f"📝 Mock Ghost: Updated post '{mock_post['title']}' (ID: {post_id})")
        
        return jsonify({"posts": [mock_post]})
    
    elif request.method == 'DELETE':
        if post_id not in mock_posts:
            return jsonify({"errors": [{"message": "Post not found"}]}), 404
        
        deleted_post = mock_posts.pop(post_id)
        print(f"🗑️ Mock Ghost: Deleted post '{deleted_post['title']}' (ID: {post_id})")
        
        return '', 204

@app.route('/ghost/api/v5/admin/posts/slug/<slug>/', methods=['GET'])
def get_post_by_slug(slug):
    """Mock get post by slug endpoint"""
    for post in mock_posts.values():
        if post['slug'] == slug:
            return jsonify({"posts": [post]})
    return jsonify({"errors": [{"message": "Post not found"}]}), 404

@app.route('/ghost/api/v5/admin/images/upload/', methods=['POST'])
def upload_image():
    """Mock image upload endpoint"""
    if 'file' not in request.files:
        return jsonify({"errors": [{"message": "No file provided"}]}), 422
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"errors": [{"message": "No file selected"}]}), 422
    
    # Mock image upload
    image_id = str(uuid.uuid4())
    image_url = f"http://localhost:3001/content/images/{image_id}/{file.filename}"
    
    mock_image = {
        "id": image_id,
        "url": image_url,
        "filename": file.filename,
        "uploaded_at": datetime.utcnow().isoformat() + "Z"
    }
    
    mock_images[image_id] = mock_image
    
    print(f"🖼️ Mock Ghost: Uploaded image '{file.filename}' -> {image_url}")
    
    return jsonify({"images": [mock_image]})

@app.route('/ghost/api/v5/admin/tags/', methods=['GET', 'POST'])
def handle_tags():
    """Mock tags endpoint"""
    if request.method == 'GET':
        tags_list = list(mock_tags.values())
        return jsonify({"tags": tags_list})
    
    elif request.method == 'POST':
        data = request.get_json()
        if not data or 'tags' not in data:
            return jsonify({"errors": [{"message": "Invalid tag data"}]}), 422
        
        tag_data = data['tags'][0]
        tag_id = str(uuid.uuid4())
        
        mock_tag = {
            "id": tag_id,
            "name": tag_data.get("name", ""),
            "slug": tag_data.get("name", "").lower().replace(" ", "-"),
            "description": tag_data.get("description", ""),
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }
        
        mock_tags[tag_id] = mock_tag
        
        print(f"🏷️ Mock Ghost: Created tag '{mock_tag['name']}' (ID: {tag_id})")
        
        return jsonify({"tags": [mock_tag]})

@app.route('/content/images/<path:filename>')
def serve_mock_image(filename):
    """Serve mock images"""
    return f"Mock image: {filename}", 200, {'Content-Type': 'text/plain'}

def run_mock_server():
    """Run the mock Ghost API server"""
    print("🚀 Starting Mock Ghost API server on http://localhost:3001")
    print("📋 Available endpoints:")
    print("   - GET  /ghost/api/v5/admin/site/")
    print("   - GET  /ghost/api/v5/admin/posts/")
    print("   - POST /ghost/api/v5/admin/posts/")
    print("   - GET  /ghost/api/v5/admin/posts/<id>/")
    print("   - PUT  /ghost/api/v5/admin/posts/<id>/")
    print("   - DELETE /ghost/api/v5/admin/posts/<id>/")
    print("   - POST /ghost/api/v5/admin/images/upload/")
    print("   - GET  /ghost/api/v5/admin/tags/")
    print("   - POST /ghost/api/v5/admin/tags/")
    print()
    
    app.run(host='0.0.0.0', port=3001, debug=False)

if __name__ == '__main__':
    run_mock_server()