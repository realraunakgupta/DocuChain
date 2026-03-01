from flask import Flask, render_template, request, flash, session, redirect, url_for, jsonify
from blockchain import Blockchain
import hashlib
import os
import json
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import pyqrcode
import io
import base64

import cloudinary
import cloudinary.uploader
import cloudinary.api

from db import users_collection, requests_collection

# Cloudinary automatically configures itself using the CLOUDINARY_URL from .env
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'docuchain_offline_demo_secret')
blockchain = Blockchain()

@app.template_filter('formatdatetime')
def format_datetime(value):
    if value is None:
        return ""
    # Formats to: February 28, 2026 - 06:30 PM
    return datetime.fromtimestamp(value).strftime('%B %d, %Y - %I:%M %p')

# Ensure uploads directory exists on cloud environment
os.makedirs(os.path.join(app.root_path, 'static', 'uploads'), exist_ok=True)

def calculate_file_hash(file_data):
    return hashlib.sha256(file_data).hexdigest()

@app.context_processor
def inject_user_data():
    if 'user' in session:
        try:
            user_data = users_collection.find_one({"_id": session['user']}) or {}
            return dict(current_user=user_data)
        except Exception:
            return dict(current_user=None)
    return dict(current_user=None)

@app.route('/health')
def health():
    return jsonify({"status": "ok"}), 200

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/issue', methods=['GET', 'POST'])
def issue():
    if 'user' not in session:
        flash("You must be logged in as an authorized representative to issue documents.", "warning")
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        if 'document' not in request.files or 'holder_photo' not in request.files:
            flash("You must upload both the official document and the holder's photograph.", "danger")
            return render_template('issue.html')
            
        file = request.files['document']
        photo = request.files['holder_photo']
        
        if file.filename == '' or photo.filename == '':
            flash("Files cannot be empty.", "danger")
            return render_template('issue.html')
            
        doc_type = request.form.get('document_type')
        student_name = request.form.get('student_name', 'Unknown')
        validity = request.form.get('validity', 'Lifetime')
        
        # Use logged in user as issuer, don't read from form
        issuer = session.get('user')
        
        if not doc_type:
            flash("Please provide document type.", "warning")
            return render_template('issue.html')
            
        # 1. Process and Hash Document
        file_data = file.read()
        doc_hash = calculate_file_hash(file_data)
        
        # Rewind file pointer for Cloudinary upload
        file.seek(0)
        
        # Upload the original issued document to Cloudinary
        upload_result = cloudinary.uploader.upload(
            file, 
            resource_type='auto',
            public_id=f"doc_{doc_hash}",
            folder="docuchain/documents"
        )
        doc_url = upload_result.get('secure_url')
        
        # 2. Process and Hash Photo (Immutable Photo Upload)
        photo_data = photo.read()
        photo_hash = calculate_file_hash(photo_data)
        
        photo.seek(0)
        # Save photo purely by its cryptographic identity
        photo_upload_result = cloudinary.uploader.upload(
            photo,
            folder="docuchain/photos",
            public_id=f"{photo_hash}"
        )
        photo_url = photo_upload_result.get('secure_url')
            
        # 3. Auto-generate unique Cert ID
        cert_id = hashlib.md5((student_name + str(doc_hash)).encode()).hexdigest()[:8].upper()
        
        # Ensure fresh load from file before adding
        blockchain.load_chain()
        # Note: We now store the photo URL instead of just the filename
        new_block = blockchain.add_block(doc_type, issuer, doc_hash, student_name, cert_id, validity, student_image=photo_url)
        
        # Format the timestamp directly for the frontend
        formatted_timestamp = datetime.fromtimestamp(new_block.timestamp).strftime('%B %d, %Y - %I:%M %p')
        
        flash("Document successfully issued and added to the blockchain.", "success")
        return render_template('issue.html', new_block=new_block.to_dict(), formatted_timestamp=formatted_timestamp)
        
    return render_template('issue.html')

@app.route('/request_verification', methods=['GET', 'POST'])
def request_verification():
    if 'user' not in session or session.get('role') != 'Holder':
        flash("You must be logged in as a Holder to request verification.", "warning")
        return redirect(url_for('login'))
        
    issuers = [{"username": u["_id"], "data": u} for u in users_collection.find({"role": "Issuer"})]
        
    if request.method == 'POST':
        if 'document' not in request.files:
            flash("You must upload the document to be verified.", "danger")
            return redirect(request.url)
            
        file = request.files['document']
        if file.filename == '':
            flash("No file selected.", "danger")
            return redirect(request.url)
            
        doc_type = request.form.get('document_type')
        target_issuer = request.form.get('target_issuer')
        
        if not doc_type or not target_issuer:
            flash("Document type and target issuer are required.", "danger")
            return redirect(request.url)
            
        file_data = file.read()
        doc_hash = calculate_file_hash(file_data)
        
        # Duplicate check: prevent requesting verification if already anchored
        blockchain.load_chain()
        if blockchain.find_document_hash(doc_hash):
            flash("This exact document has already been authenticated on the blockchain.", "warning")
            return redirect(request.url)
        
        # Upload file to Cloudinary
        file.seek(0)
        upload_result = cloudinary.uploader.upload(
            file,
            resource_type='auto',
            public_id=f"req_{doc_hash[:16]}",
            folder="docuchain/requests"
        )
        file_url = upload_result.get('secure_url')
            
        req_id = f"REQ-{doc_hash[:8].upper()}"
        

        requests_collection.insert_one({
            "_id": req_id,
            "holder": session.get('user'),
            "target_issuer": target_issuer,
            "document_type": doc_type,
            "file_path": file_url,  # Now storing Cloudinary URL
            "status": "Pending",
            "timestamp": time.time()
        })
        
        flash("Verification request submitted successfully. Waiting for ISSUER approval.", "success")
        return redirect(url_for('dashboard'))
        
    return render_template('request_verification.html', issuers=issuers)

@app.route('/approve_request/<req_id>', methods=['POST'])
def approve_request(req_id):
    if 'user' not in session or session.get('role') != 'Issuer':
        flash("Unauthorized.", "danger")
        return redirect(url_for('login'))
        
    req = requests_collection.find_one({"_id": req_id})
    if not req:
        flash("Request not found.", "danger")
        return redirect(url_for('dashboard'))
        
    if req.get('target_issuer') != session.get('user'):
        flash("You are not authorized to approve this request.", "danger")
        return redirect(url_for('dashboard'))
        
    # Read the file and hash it from Cloudinary instead of local disk
    file_url = req['file_path']
    try:
        with urllib.request.urlopen(file_url) as response:
            file_data = response.read()
    except Exception as e:
        flash("Document file missing from cloud storage.", "danger")
        return redirect(url_for('dashboard'))
        
    doc_hash = calculate_file_hash(file_data)
        
    # Add to blockchain
    blockchain.load_chain()
    
    # Check if already issued
    existing = blockchain.find_document_hash(doc_hash)
    if existing:
        flash("This document is already verified on the blockchain.", "warning")
        requests_collection.update_one({"_id": req_id}, {"$set": {"status": "Approved"}})
        return redirect(url_for('dashboard'))
    

    cert_id = f"VERIFIED-{int(time.time())}"
    
    holder_data = users_collection.find_one({"_id": req['holder']}) or {}
    student_image = holder_data.get('avatar', 'placeholder_avatar.svg')
    
    blockchain.add_block(
        document_type=req['document_type'],
        issuer=session.get('user'),
        document_hash=doc_hash,
        student_name=req['holder'],
        cert_id=cert_id,
        validity="Lifetime",
        student_image=student_image
    )
    
    requests_collection.update_one({"_id": req_id}, {"$set": {"status": "Approved"}})
    
    flash(f"Successfully verified and anchored {req['holder']}'s document to the blockchain.", "success")
    return redirect(url_for('dashboard'))

@app.route('/reject_request/<req_id>', methods=['POST'])
def reject_request(req_id):
    if 'user' not in session or session.get('role') != 'Issuer':
        flash("Unauthorized.", "danger")
        return redirect(url_for('login'))
        
    req = requests_collection.find_one({"_id": req_id})
    if not req:
        flash("Request not found.", "danger")
        return redirect(url_for('dashboard'))
        
    if req.get('target_issuer') != session.get('user'):
        flash("You are not authorized to reject this request.", "danger")
        return redirect(url_for('dashboard'))
        
    requests_collection.update_one({"_id": req_id}, {"$set": {"status": "Rejected"}})
    
    flash("Verification request rejected.", "info")
    return redirect(url_for('dashboard'))

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if request.method == 'POST':
        if 'document' not in request.files:
            flash("No file uploaded. Please select a document to verify.", "danger")
            return render_template('verify.html')
            
        file = request.files['document']
        if file.filename == '':
            flash("No file selected.", "danger")
            return render_template('verify.html')
            
        file_data = file.read()
        calculated_hash = calculate_file_hash(file_data)
        
        # Reload chain to ensure we have latest records
        blockchain.load_chain()
        matching_block = blockchain.find_document_hash(calculated_hash)
        
        qr_base64 = None
        formatted_date = None
        if matching_block:
            ist = timezone(timedelta(hours=5, minutes=30))
            formatted_date = datetime.fromtimestamp(matching_block.timestamp, ist).strftime('%B %d, %Y')
            
            # Generate QR Code containing metadata
            qr_data = (f"DocuChain Verified\n"
                       f"Holder: {matching_block.student_name}\n"
                       f"ID: {matching_block.cert_id}\n"
                       f"Issuer: {matching_block.issuer}\n"
                       f"Issued: {formatted_date}\n"
                       f"Validity: {matching_block.validity}\n"
                       f"Hash: {matching_block.document_hash[:16]}...")
            
            qr = pyqrcode.create(qr_data)
            buffer = io.BytesIO()
            qr.svg(buffer, scale=4, background="white", module_color="#1E3A8A")
            qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return render_template('verify.html', 
                               calculated_hash=calculated_hash, 
                               matching_block=matching_block,
                               qr_base64=qr_base64,
                               issued_date=formatted_date)
        
    return render_template('verify.html')

@app.route('/chain')
def chain():
    blockchain.load_chain()
    is_valid = blockchain.verify_chain()
    
    chain_data = []
    ist = timezone(timedelta(hours=5, minutes=30))
    is_logged_in = 'user' in session
    
    for b in blockchain.chain:
        b_dict = b.to_dict()
        formatted_date = datetime.fromtimestamp(b.timestamp, ist).strftime('%B %d, %Y - %I:%M %p')
        
        # Privacy Censorship for unauthenticated users
        if not is_logged_in and b.index != 0:
            # Censor Issuer Name (Keep first & last letter of each word)
            censored_words = []
            for word in b.issuer.split():
                if len(word) > 2:
                    censored_words.append(word[0] + '*' * (len(word) - 2) + word[-1])
                elif len(word) == 2:
                    censored_words.append(word[0] + '*')
                else:
                    censored_words.append(word)
            b_dict['issuer'] = ' '.join(censored_words)
                
            # Censor Timestamp
            b_dict['formatted_timestamp'] = '*** ** **** - **:** **'
        else:
            b_dict['formatted_timestamp'] = formatted_date
            
        chain_data.append(b_dict)
        
    return render_template('chain.html', chain=chain_data, is_valid=is_valid)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = users_collection.find_one({"_id": username})
        # Ensure user exists and the password matches the stored hash
        if user and check_password_hash(user.get('password', ''), password):
            session['user'] = username
            session['role'] = user.get('role', 'Holder')
            flash(f"Welcome back, {username}!", 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('login'))
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role', 'Holder')
        
        if not username or not password:
            flash("Username and password are required.", "warning")
            return redirect(url_for('register'))
            
        if users_collection.find_one({"_id": username}):
            flash("Username already registered.", "danger")
            return redirect(url_for('register'))
            
        users_collection.insert_one({
            '_id': username,
            'password': generate_password_hash(password),
            'role': role
        })
        
        flash("Registration successful! You can now log in.", "success")
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user' not in session:
        flash("You must be logged in to view this page.", "warning")
        return redirect(url_for('login'))
        
    current_username = session['user']
    user_data = users_collection.find_one({"_id": current_username}) or {}
    
    if request.method == 'POST':
        if 'avatar' not in request.files:
            flash("No file selected.", "danger")
            return redirect(url_for('profile'))
            
        file = request.files['avatar']
        if file.filename == '':
            flash("No file selected.", "danger")
            return redirect(url_for('profile'))
            

        # Check cooldown (60 days)
        last_update = user_data.get('last_photo_update', 0)
        cooldown = 60 * 24 * 3600
        if time.time() - last_update < cooldown and last_update != 0:
            days_left = int((cooldown - (time.time() - last_update)) / 86400)
            flash(f"Security Policy: You can only update your immutable profile photo once every 60 days. Please wait {days_left + 1} more days.", "warning")
            return redirect(url_for('profile'))
            
        file_data = file.read()
        photo_hash = calculate_file_hash(file_data)
        
        # Upload to Cloudinary
        file.seek(0)
        upload_result = cloudinary.uploader.upload(
            file,
            folder="docuchain/photos",
            public_id=f"{photo_hash}"
        )
        photo_url = upload_result.get('secure_url')
            
        user_data['avatar'] = photo_url
        user_data['last_photo_update'] = time.time()
        users_collection.update_one({"_id": current_username}, {"$set": user_data})
        
        flash("Immutable Profile Photo updated successfully! Future verifications will anchor this photo.", "success")
        return redirect(url_for('profile'))
        
    return render_template('profile.html', user_data=user_data)

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    role = session.get('role', 'Holder')
    username = session.get('user')
    
    # Reload blockchain to be safe
    blockchain.load_chain()
    
    my_requests = []
    
    my_documents = []
    if role == 'Holder':
        # Find all documents issued to this student/holder
        for block in blockchain.chain:
            if block.student_name == username:
                my_documents.append(block)
                
        # Find all verification requests made by this holder
        my_requests = list(requests_collection.find({"holder": username, "status": {"$ne": "Approved"}}))
        for r in my_requests:
            r['id'] = r['_id']
                
    elif role == 'Issuer':
        # Find all documents issued BY this organization
        for block in blockchain.chain:
            if block.issuer == username:
                my_documents.append(block)
                
        # Find all pending verification requests targeted at this issuer
        my_requests = list(requests_collection.find({"target_issuer": username, "status": "Pending"}))
        for r in my_requests:
            r['id'] = r['_id']
                
    return render_template('dashboard.html', role=role, username=username, my_documents=my_documents, my_requests=my_requests)

@app.route('/document/<doc_hash>')
def view_document(doc_hash):
    blockchain.load_chain()
    matching_block = blockchain.find_document_hash(doc_hash)
    
    if not matching_block:
        flash("Document not found in the blockchain.", "danger")
        if 'user' in session:
            return redirect(url_for('dashboard'))
        return redirect(url_for('index'))
        
    # Format the timestamp for nice UI display
    ist = timezone(timedelta(hours=5, minutes=30))
    formatted_date = datetime.fromtimestamp(matching_block.timestamp, ist).strftime('%B %d, %Y')

    qr_base64 = None
    # Generate QR Code containing metadata
    qr_data = (f"DocuChain Verified\n"
               f"Holder: {matching_block.student_name}\n"
               f"ID: {matching_block.cert_id}\n"
               f"Issuer: {matching_block.issuer}\n"
               f"Issued: {formatted_date}\n"
               f"Validity: {matching_block.validity}\n"
               f"Hash: {matching_block.document_hash[:16]}...")
    
    qr = pyqrcode.create(qr_data)
    buffer = io.BytesIO()
    qr.svg(buffer, scale=4, background="white", module_color="#1E3A8A")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return render_template('document.html', matching_block=matching_block, qr_base64=qr_base64, issued_date=formatted_date)

@app.route('/download_file/<doc_hash>')
def download_file(doc_hash):
    if 'user' not in session:
        return redirect(url_for('login'))
        
    # Query Cloudinary to find the file by its tag/hash
    try:
        # Search for document by public ID
        resource = cloudinary.api.resource(f"docuchain/documents/doc_{doc_hash}")
        url = resource.get('secure_url')
        if url:
            # We redirect them to the cloudinary URL but prompt a download
            # Cloudinary provides an attachment flag: 'fl_attachment'
            download_url = url.replace('/upload/', '/upload/fl_attachment/')
            return redirect(download_url)
    except cloudinary.exceptions.NotFound:
        # Check if it was a verification request draft
        try:
            resource = cloudinary.api.resource(f"docuchain/requests/req_{doc_hash[:16]}")
            url = resource.get('secure_url')
            if url:
                download_url = url.replace('/upload/', '/upload/fl_attachment/')
                return redirect(download_url)
        except cloudinary.exceptions.NotFound:
            pass
            
    flash("Original document file not found on the cloud server.", "warning")
    return redirect(url_for('dashboard'))

@app.route('/view_file/<doc_hash>')
def view_file_route(doc_hash):
    if 'user' not in session:
        return redirect(url_for('login'))
        
    # Redirect to the direct Cloudinary URL
    try:
        resource = cloudinary.api.resource(f"docuchain/documents/doc_{doc_hash}")
        url = resource.get('secure_url')
        if url:
            return redirect(url)
    except cloudinary.exceptions.NotFound:
        try:
            resource = cloudinary.api.resource(f"docuchain/requests/req_{doc_hash[:16]}")
            url = resource.get('secure_url')
            if url:
                return redirect(url)
        except cloudinary.exceptions.NotFound:
            pass
            
    flash("Original document file not found on the cloud server.", "warning")
    return redirect(url_for('dashboard'))

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been securely logged out.", "info")
    return redirect(url_for('index'))

# Custom error handlers for stable demo without tracebacks
@app.errorhandler(500)
def internal_error(error):
    return "<h1>500 Internal Server Error</h1><p>Something went wrong, but the demo must go on. Please restart the Flask server.</p>", 500

@app.errorhandler(404)
def not_found_error(error):
    return "<h1>404 Not Found</h1><p>The page you are looking for does not exist in DocuChain.</p><a href='/'>Go Home</a>", 404

if __name__ == '__main__':
    # Run dynamically on the port assigned by the cloud provider (default 5000)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
