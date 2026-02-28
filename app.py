from flask import Flask, render_template, request, flash, session, redirect, url_for
import hashlib
from blockchain import Blockchain
import os
import json
from werkzeug.security import generate_password_hash, check_password_hash
import pyqrcode
import io
import base64

app = Flask(__name__)
app.secret_key = 'docuchain_offline_demo_secret'  # Flash requires a secret key
blockchain = Blockchain()

# Ensure uploads directory exists on cloud environment
os.makedirs(os.path.join(app.root_path, 'static', 'uploads'), exist_ok=True)

USERS_FILE = 'users.json'

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

REQUESTS_FILE = 'requests.json'

def load_requests():
    if not os.path.exists(REQUESTS_FILE):
        return {}
    try:
        with open(REQUESTS_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_requests(requests_data):
    with open(REQUESTS_FILE, 'w') as f:
        json.dump(requests_data, f, indent=4)

def calculate_file_hash(file_data):
    return hashlib.sha256(file_data).hexdigest()

@app.context_processor
def inject_user_data():
    if 'user' in session:
        users = load_users()
        user_data = users.get(session['user'], {})
        return dict(current_user=user_data)
    return dict(current_user=None)

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
        
        # Save the original issued document to uploads
        _, ext = os.path.splitext(file.filename)
        if not ext:
            ext = '.pdf'
        doc_filename = f"doc_{doc_hash}{ext}"
        doc_path = os.path.join(app.root_path, 'static', 'uploads', doc_filename)
        os.makedirs(os.path.dirname(doc_path), exist_ok=True)
        with open(doc_path, 'wb') as f:
            f.write(file_data)
        
        # 2. Process and Hash Photo (Immutable Photo Upload)
        photo_data = photo.read()
        photo_hash = calculate_file_hash(photo_data)
        
        # Save photo purely by its cryptographic identity
        photo_ext = '.jpg' if 'jpeg' in photo.content_type or 'jpg' in photo.filename.lower() else '.png'
        photo_filename = f"{photo_hash}{photo_ext}"
        photo_path = os.path.join(app.root_path, 'static', 'uploads', photo_filename)
        with open(photo_path, 'wb') as f:
            f.write(photo_data)
            
        # 3. Auto-generate unique Cert ID
        cert_id = hashlib.md5((student_name + str(doc_hash)).encode()).hexdigest()[:8].upper()
        
        # Ensure fresh load from file before adding
        blockchain.load_chain()
        new_block = blockchain.add_block(doc_type, issuer, doc_hash, student_name, cert_id, validity, student_image=photo_filename)
        
        flash("Document successfully issued and added to the blockchain.", "success")
        return render_template('issue.html', new_block=new_block.to_dict())
        
    return render_template('issue.html')

@app.route('/request_verification', methods=['GET', 'POST'])
def request_verification():
    if 'user' not in session or session.get('role') != 'Holder':
        flash("You must be logged in as a Holder to request verification.", "warning")
        return redirect(url_for('login'))
        
    users = load_users()
    issuers = [u for u, data in users.items() if data.get('role') == 'Issuer']
        
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
        
        # Save file to uploads folder using standard hash prefix
        _, ext = os.path.splitext(file.filename)
        if not ext:
            ext = '.pdf'
        safe_filename = f"doc_{doc_hash}{ext}"
        filepath = os.path.join('static', 'uploads', safe_filename)
        
        with open(filepath, 'wb') as f:
            f.write(file_data)
            
        requests_data = load_requests()
        req_id = f"REQ-{doc_hash[:8].upper()}"
        
        import time
        requests_data[req_id] = {
            "holder": session.get('user'),
            "target_issuer": target_issuer,
            "document_type": doc_type,
            "file_path": safe_filename,
            "status": "Pending",
            "timestamp": time.time()
        }
        
        save_requests(requests_data)
        flash("Verification request submitted successfully. Waiting for ISSUER approval.", "success")
        return redirect(url_for('dashboard'))
        
    return render_template('request_verification.html', issuers=issuers)

@app.route('/approve_request/<req_id>', methods=['POST'])
def approve_request(req_id):
    if 'user' not in session or session.get('role') != 'Issuer':
        flash("Unauthorized.", "danger")
        return redirect(url_for('login'))
        
    requests_data = load_requests()
    if req_id not in requests_data:
        flash("Request not found.", "danger")
        return redirect(url_for('dashboard'))
        
    req = requests_data[req_id]
    if req.get('target_issuer') != session.get('user'):
        flash("You are not authorized to approve this request.", "danger")
        return redirect(url_for('dashboard'))
        
    # Read the file and hash it
    filepath = os.path.join('static', 'uploads', req['file_path'])
    if not os.path.exists(filepath):
        flash("Document file missing from server.", "danger")
        return redirect(url_for('dashboard'))
        
    with open(filepath, 'rb') as f:
        file_data = f.read()
        
    doc_hash = calculate_file_hash(file_data)
        
    # Add to blockchain
    blockchain.load_chain()
    
    # Check if already issued
    existing = blockchain.find_document_hash(doc_hash)
    if existing:
        flash("This document is already verified on the blockchain.", "warning")
        req['status'] = 'Approved'
        save_requests(requests_data)
        return redirect(url_for('dashboard'))
    
    import time
    cert_id = f"VERIFIED-{int(time.time())}"
    
    users = load_users()
    holder_data = users.get(req['holder'], {})
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
    
    req['status'] = 'Approved'
    save_requests(requests_data)
    
    flash(f"Successfully verified and anchored {req['holder']}'s document to the blockchain.", "success")
    return redirect(url_for('dashboard'))

@app.route('/reject_request/<req_id>', methods=['POST'])
def reject_request(req_id):
    if 'user' not in session or session.get('role') != 'Issuer':
        flash("Unauthorized.", "danger")
        return redirect(url_for('login'))
        
    requests_data = load_requests()
    if req_id not in requests_data:
        flash("Request not found.", "danger")
        return redirect(url_for('dashboard'))
        
    req = requests_data[req_id]
    if req.get('target_issuer') != session.get('user'):
        flash("You are not authorized to reject this request.", "danger")
        return redirect(url_for('dashboard'))
        
    req['status'] = 'Rejected'
    save_requests(requests_data)
    
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
            from datetime import datetime
            formatted_date = datetime.fromtimestamp(matching_block.timestamp).strftime('%B %d, %Y')
            
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
    from datetime import datetime
    is_logged_in = 'user' in session
    
    for b in blockchain.chain:
        b_dict = b.to_dict()
        formatted_date = datetime.fromtimestamp(b.timestamp).strftime('%B %d, %Y - %I:%M %p')
        
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
        
        users = load_users()
        # Ensure user exists and the password matches the stored hash
        if username in users and check_password_hash(users[username].get('password', ''), password):
            session['user'] = username
            session['role'] = users[username].get('role', 'Holder')
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
            
        users = load_users()
        if username in users:
            flash("Username already registered.", "danger")
            return redirect(url_for('register'))
            
        users[username] = {
            'password': generate_password_hash(password),
            'role': role
        }
        save_users(users)
        
        flash("Registration successful! You can now log in.", "success")
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user' not in session:
        flash("You must be logged in to view this page.", "warning")
        return redirect(url_for('login'))
        
    users = load_users()
    current_username = session['user']
    user_data = users.get(current_username, {})
    
    if request.method == 'POST':
        if 'avatar' not in request.files:
            flash("No file selected.", "danger")
            return redirect(url_for('profile'))
            
        file = request.files['avatar']
        if file.filename == '':
            flash("No file selected.", "danger")
            return redirect(url_for('profile'))
            
        import time
        # Check cooldown (60 days)
        last_update = user_data.get('last_photo_update', 0)
        cooldown = 60 * 24 * 3600
        if time.time() - last_update < cooldown and last_update != 0:
            days_left = int((cooldown - (time.time() - last_update)) / 86400)
            flash(f"Security Policy: You can only update your immutable profile photo once every 60 days. Please wait {days_left + 1} more days.", "warning")
            return redirect(url_for('profile'))
            
        file_data = file.read()
        photo_hash = calculate_file_hash(file_data)
        
        _, ext = os.path.splitext(file.filename)
        if not ext:
            ext = '.jpg'
        safe_filename = f"{photo_hash}{ext}"
        filepath = os.path.join('static', 'uploads', safe_filename)
        
        with open(filepath, 'wb') as f:
            f.write(file_data)
            
        user_data['avatar'] = safe_filename
        user_data['last_photo_update'] = time.time()
        users[current_username] = user_data
        save_users(users)
        
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
    
    requests_data = load_requests()
    my_requests = []
    
    my_documents = []
    if role == 'Holder':
        # Find all documents issued to this student/holder
        for block in blockchain.chain:
            if block.student_name == username:
                my_documents.append(block)
                
        # Find all verification requests made by this holder
        for req_id, req in requests_data.items():
            if req.get('holder') == username and req.get('status') != 'Approved':
                req['id'] = req_id
                my_requests.append(req)
                
    elif role == 'Issuer':
        # Find all documents issued BY this organization
        for block in blockchain.chain:
            if block.issuer == username:
                my_documents.append(block)
                
        # Find all pending verification requests targeted at this issuer
        for req_id, req in requests_data.items():
            if req.get('target_issuer') == username and req.get('status') == 'Pending':
                req['id'] = req_id
                my_requests.append(req)
                
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
    from datetime import datetime
    formatted_date = datetime.fromtimestamp(matching_block.timestamp).strftime('%B %d, %Y')

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
        
    uploads_dir = os.path.join(app.root_path, 'static', 'uploads')
    if not os.path.exists(uploads_dir):
        flash("Server storage unavailable.", "danger")
        return redirect(url_for('dashboard'))
        
    for filename in os.listdir(uploads_dir):
        if filename.startswith(f"doc_{doc_hash}") or filename.startswith(f"req_{doc_hash[:16]}"):
            from flask import send_from_directory
            return send_from_directory(uploads_dir, filename, as_attachment=True)
            
    flash("Original document file not found on the server.", "warning")
    return redirect(url_for('dashboard'))

@app.route('/view_file/<doc_hash>')
def view_file_route(doc_hash):
    if 'user' not in session:
        return redirect(url_for('login'))
        
    uploads_dir = os.path.join(app.root_path, 'static', 'uploads')
    if not os.path.exists(uploads_dir):
        flash("Server storage unavailable.", "danger")
        return redirect(url_for('dashboard'))
        
    for filename in os.listdir(uploads_dir):
        if filename.startswith(f"doc_{doc_hash}") or filename.startswith(f"req_{doc_hash[:16]}"):
            from flask import send_from_directory
            return send_from_directory(uploads_dir, filename)
            
    flash("Original document file not found on the server.", "warning")
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
