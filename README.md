# DocuChain: Blockchain Certificate Verification System 🔗📄

DocuChain is a premium, secure, and modern web application built to issue and publicly verify digital documents and certificates using cryptographic blockchain principles. 

Designed with a stunning Apple-inspired minimalist aesthetic, DocuChain eliminates the possibility of document forgery by permanently anchoring document hashes on an immutable distributed ledger.

## ✨ Features

- **Immutable Proof of Existence:** Documents are cryptographically hashed (SHA-256) and stored in a transparent, tamper-proof blockchain.
- **Instant Verification:** Anyone can upload a document to mathematically verify if it perfectly matches the originally issued file.
- **Secure Issuing Dashboard:** Institutions can log in securely to grant roles, issue documents, and view issuance history.
- **Premium Apple-Inspired UI:** A completely responsive, glassmorphic design system using native SF Pro/Inter typography, deep soft-shadows, and elegant spacing.
- **Zero-Storage Architecture:** The system stores *cryptographic hashes* rather than the actual document files, ensuring maximum data privacy and low server costs.

## 🛠️ Technology Stack

- **Backend:** Python 3, Flask, Werkzeug Security (Scrypt password hashing)
- **Frontend:** HTML5, CSS3, Bootstrap 5 (Customized Apple-Aesthetic)
- **Blockchain:** Custom immutable ledger implementation using Python `hashlib` & ECDSA signatures
- **Deployment:** Render (Waitress/Gunicorn compatible)

## 🚀 Getting Started Locally

### Prerequisites
- Python 3.9+
- pip (Python package manager)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/DocuChain.git
   cd DocuChain
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python app.py
   ```

4. Open your browser and navigate to:
   `http://localhost:5000`

## 📁 Project Structure 

```
DocuChain/
├── app.py                   # Main Flask application and URL routing
├── blockchain.py            # Core cryptographic blockchain ledger logic
├── requirements.txt         # Python package dependencies
├── /templates               # HTML files 
│   ├── base.html            # Global layout & glassmorphic Navbar
│   ├── index.html           # Landing page
│   ├── issue.html           # Administrator issuance dashboard
│   └── verify.html          # Public verification portal
├── /static                  # CSS and assets
│   └── style.css            # Custom design tokens
├── /demo_files              # Sample PDF diplomas and photos for testing
└── *.json                   # Local data persistence (mock-database)
```

## 🔐 Security Considerations

- Passwords are securely hashed using `werkzeug.security` with `scrypt:32768:8:1` configurations.
- Accessing the `dashboard` or `issue` routes requires authenticated sessions.
- Documents are never uploaded to permanent storage during the `verify` phase; they are hashed in-memory, checked against the blockchain, and immediately discarded.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
