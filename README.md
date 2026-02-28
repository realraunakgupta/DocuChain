# DocuChain: Blockchain Certificate Verification System 🔗📄

DocuChain is a secure, modern web application built to issue and publicly verify digital documents and certificates using cryptographic blockchain principles.

Designed with an Apple-inspired minimalist aesthetic, DocuChain eliminates the possibility of document forgery by permanently anchoring document hashes on an immutable distributed ledger.

🌐 **Live Demo:** [docuchain.onrender.com](https://docuchain.onrender.com)

## ✨ Features

- **Immutable Proof of Existence:** Documents are cryptographically hashed (SHA-256) and stored in a transparent, tamper-proof blockchain.
- **Instant Verification:** Anyone can upload a document to mathematically verify if it matches the originally issued file.
- **Role-Based Dashboards:** Issuers can approve/reject verification requests; Holders can track issued documents and request verification.
- **Cloudinary Integration:** Documents and profile photos are securely stored on Cloudinary with content-addressed naming.
- **QR Code Generation:** Each verified document gets a scannable QR code containing full metadata.
- **Immutable Profile Photos:** Users can set a profile photo that anchors to future verifications, with a 60-day cooldown between changes.
- **Premium Apple-Inspired UI:** Fully responsive glassmorphic design with SF Pro/Inter typography, soft shadows, and elegant spacing.
- **Native Dark Mode:** Intelligent dark mode that transitions seamlessly between light and dark themes based on system preference.
- **Privacy Protection:** Unauthenticated users see censored issuer names and timestamps on the public blockchain explorer.

## 🛠️ Technology Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3, Flask, Werkzeug Security (Scrypt password hashing) |
| **Database** | MongoDB Atlas (cloud-hosted NoSQL) |
| **File Storage** | Cloudinary (documents, photos, profile images) |
| **Frontend** | HTML5, CSS3, Bootstrap 5 (Customized Apple-Aesthetic) |
| **Blockchain** | Custom immutable ledger using Python `hashlib` (SHA-256) |
| **Deployment** | Render (Gunicorn WSGI server) |

## 🚀 Getting Started Locally

### Prerequisites
- Python 3.9+
- pip (Python package manager)
- A [MongoDB Atlas](https://www.mongodb.com/atlas) account (free tier works)
- A [Cloudinary](https://cloudinary.com/) account (free tier works)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/realraunakgupta/DocuChain.git
   cd DocuChain
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root (see [Environment Variables](#-environment-variables) below).

4. Run the application:
   ```bash
   python app.py
   ```

5. Open your browser and navigate to:
   `http://localhost:5000`

## 🔑 Environment Variables

Create a `.env` file in the project root with the following variables:

| Variable | Description | Where to find it |
|----------|-------------|-----------------|
| `MONGO_URI` | MongoDB Atlas connection string | MongoDB Atlas → Connect → Drivers |
| `CLOUDINARY_URL` | Cloudinary API environment variable | Cloudinary Dashboard → Account Details |
| `SECRET_KEY` | Flask session secret key (any strong random string) | Generate your own |

> **Note:** The `.env` file is included in `.gitignore` and will never be committed to the repository.

## 📁 Project Structure

```
DocuChain/
├── app.py                        # Main Flask application and URL routing
├── blockchain.py                 # Core cryptographic blockchain ledger logic
├── db.py                         # MongoDB connection and collection setup
├── requirements.txt              # Python package dependencies
├── Procfile                      # Render/Gunicorn deployment config
├── .env                          # Environment variables (not committed)
├── .gitignore                    # Git ignore rules
├── templates/                    # HTML interfaces (Jinja2)
│   ├── base.html                 # Global layout, navbar, footer, dark mode
│   ├── index.html                # Landing page
│   ├── dashboard.html            # Role-based dashboard (Issuer/Holder)
│   ├── issue.html                # Document issuance form
│   ├── verify.html               # Public verification portal
│   ├── chain.html                # Live blockchain explorer
│   ├── document.html             # Individual document detail + QR code
│   ├── request_verification.html # Holder verification request form
│   ├── profile.html              # User profile + immutable photo upload
│   ├── login.html                # Secure authentication
│   ├── register.html             # New user registration
│   ├── privacy.html              # Privacy policy
│   └── terms.html                # Terms of service
├── static/                       # CSS and assets
│   ├── style.css                 # Custom design tokens & dark mode
│   ├── favicon.svg               # Site favicon
│   └── bootstrap.min.css         # Bootstrap 5 stylesheet
└── demo_files/                   # Sample certificates & scripts for testing
```

## 🔐 Security Considerations

- Passwords are securely hashed using `werkzeug.security` with `scrypt:32768:8:1` configurations.
- Accessing the `dashboard`, `issue`, or `profile` routes requires authenticated sessions.
- Documents are never uploaded to permanent storage during the `verify` phase — they are hashed in-memory, checked against the blockchain, and immediately discarded.
- Environment secrets (database credentials, API keys) are loaded from `.env` and never committed to version control.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
