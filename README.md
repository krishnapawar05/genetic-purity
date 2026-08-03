# Genetic Purity AI - Production Web Application

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-emerald.svg)](https://www.python.org/)
[![Flask 3.1](https://img.shields.io/badge/framework-Flask_3.1-blue.svg)](https://flask.palletsprojects.com/)
[![MongoDB Atlas](https://img.shields.io/badge/database-MongoDB_Atlas-green.svg)](https://www.mongodb.com/cloud/atlas)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An enterprise-grade production web application converting crop specimen imagery into real-time plant genetic purity diagnostics. Powered by a high-performance **MobileNet deep transfer learning architecture**, **MongoDB Atlas**, **Flask-Login**, **Razorpay Payment Gateway**, and **Twilio SMS OTP**.

---

## 1. System Architecture Diagram

```mermaid
graph TD
    Client[Web Browser / User]
    Proxy[Gunicorn / Reverse Proxy]
    Flask[Flask Application Core]
    
    subgraph Security Layer
        CSRF[CSRFProtect / Flask-WTF]
        Limiter[Flask-Limiter Rate Limiter]
        Auth[Flask-Login Session Auth]
    end
    
    subgraph Data & Storage
        Mongo[(MongoDB Atlas Cluster)]
        LocalUploads[Temp Disk Uploads / Autoclean]
    end
    
    subgraph Payment & SMS Services
        Razorpay[Razorpay Payment API]
        Twilio[Twilio SMS Gateway]
    end
    
    subgraph Neural Inference Core - Untouched
        MobileNet[MobileNet Keras Model Engine]
        Detect[detect.py Prediction Pipeline]
    end

    Client -->|HTTPS Request| Proxy
    Proxy -->|WSGI| Flask
    Flask --> CSRF
    CSRF --> Limiter
    Limiter --> Auth
    
    Auth -->|User Query| Mongo
    Auth -->|OTP Reset| Twilio
    
    Flask -->|Order / HMAC Check| Razorpay
    Razorpay -->|Payment Verified| Detect
    
    Detect -->|Load Weights| MobileNet
    Detect -->|Save Metrics| Mongo
    Flask -->|Generated PDF / HTML| Client
```

---

## 2. Database Entity Diagram (MongoDB Collections)

```mermaid
erDiagram
    USERS {
        ObjectId _id PK
        string firstName
        string lastName
        string mobileNumber UK
        string email UK
        string passwordHash
        boolean isVerified
        string role
        datetime createdAt
        datetime updatedAt
    }

    OTP_REQUESTS {
        ObjectId _id PK
        string mobileNumber
        string otp
        datetime createdAt
        datetime expiresAt
    }

    PREDICTIONS {
        ObjectId _id PK
        string userId FK
        string filename
        string prediction
        string purity
        string confidence
        object probabilities
        string reason
        string predictionTime
        string status
        datetime createdAt
    }

    PAYMENTS {
        ObjectId _id PK
        string userId FK
        string orderId UK
        string paymentId
        string signature
        number amount
        string currency
        string status
        string tempToken
        string predictionId FK
        datetime createdAt
    }

    USERS ||--o{ PREDICTIONS : "executes"
    USERS ||--o{ PAYMENTS : "initiates"
    USERS ||--o{ OTP_REQUESTS : "requests"
    PAYMENTS ||--o| PREDICTIONS : "gates & unlocks"
```

---

## 3. Authentication Flow

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant App as Flask Web App
    participant DB as MongoDB Atlas
    participant SMS as Twilio SMS

    alt Registration
        User->>App: POST /auth/signup (First/Last Name, Email, Mobile, Password)
        App->>DB: Check Duplicate Email & Mobile
        App->>DB: Insert User with bcrypt Password Hash
        App-->>User: Auto-login & Redirect to /dashboard
    else Login
        User->>App: POST /auth/login (Email/Mobile + Password)
        App->>DB: Query User by Email or Mobile
        App->>App: Verify bcrypt.checkpw(password, hash)
        App-->>User: Start Flask-Login Session Cookie
    else SMS OTP Password Reset
        User->>App: POST /auth/forgot-password (Mobile Number)
        App->>SMS: Dispatch 6-Digit OTP via SMS (or Dev Log)
        User->>App: POST /auth/verify-otp (6-Digit OTP)
        User->>App: POST /auth/reset-password (New Password)
        App->>DB: Update passwordHash
        App-->>User: Password Reset Confirmed
    end
```

---

## 4. Payment Flow (Razorpay Standard Checkout)

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant App as Flask Application
    participant RZP as Razorpay Payment API
    participant DB as MongoDB Atlas
    participant Core as detect.py & Model Engine

    User->>App: POST /create-order (Specimen File)
    App->>App: Save Temp Image File on Disk
    App->>RZP: Create Order (₹99 = 9900 Paise)
    App->>DB: Insert Payment Record (status: 'created')
    App-->>User: Return Order ID, Amount, Temp Token

    User->>RZP: Open Razorpay Modal & Complete Payment
    RZP-->>User: Return payment_id, order_id, signature

    User->>App: POST /verify-payment (signature, payment_id, temp_token)
    App->>App: HMAC SHA256 Signature Verification

    alt Signature Verification Failed (Fake Callback)
        App->>DB: Update Payment Record (status: 'failed')
        App->>App: Delete Temp Image File
        App-->>User: HTTP 400 Error (NO PREDICTION RUN)
    else Signature Verification Succeeded
        App->>DB: Update Payment Record (status: 'paid')
        App->>Core: Run detect.predict_image(temp_path, model)
        Core-->>App: Return Class, Purity %, Confidence
        App->>DB: Insert Prediction Record
        App->>App: Delete Temp Image File
        App-->>User: Return Prediction JSON / Render Result Page
    end
```

---

## 5. Prediction Flow

```mermaid
flowchart TD
    A[Upload Specimen Image] --> B{Valid Format & Size <= 50MB?}
    B -- No --> C[Return Error 400]
    B -- Yes --> D[Pre-Payment Gatekeeper]
    D --> E{Razorpay Signature Verified?}
    E -- No --> F[Block Execution & Cleanup Temp Files]
    E -- Yes --> G[In-Place Image Downscaling <= 1280px]
    G --> H{Format is HEIC or DNG?}
    H -- Yes --> I[Convert to Standard RGB JPEG via rawpy/Pillow]
    H -- No --> J[Direct Tensor Preprocessing]
    I --> J
    J --> K[Acquire Thread Lock model_lock]
    K --> L[Run MobileNet inference in detect.py]
    L --> M[Release Thread Lock]
    M --> N[Save Record to MongoDB predictions]
    N --> O[Render Modern Result Page & Generate PDF Report]
```

---

## 6. Railway Deployment Guide

### Option A: Deploying to Railway.app

1. **Push Code to GitHub**:
   ```bash
   git add .
   git commit -m "Deploy production Genetic Purity AI web app"
   git push origin main
   ```

2. **Connect GitHub Repo in Railway**:
   - Log in to [Railway.app](https://railway.app/).
   - Click **New Project** $\rightarrow$ **Deploy from GitHub repo**.
   - Select your repository.

3. **Configure Environment Variables in Railway**:
   Navigate to **Variables** tab and set:
   ```env
   SECRET_KEY=your_production_secret_key_here
   MONGO_URI=mongodb+srv://<username>:<password>@cluster0.xxx.mongodb.net/?retryWrites=true&w=majority
   DB_NAME=genetic_purity_db
   RAZORPAY_KEY_ID=rzp_live_XXXXXXXXXXXXXX
   RAZORPAY_KEY_SECRET=XXXXXXXXXXXXXXXXXXXX
   ANALYSIS_PRICE_INR=99
   FLASK_ENV=production
   ```

4. **Verify Deployment**:
   Railway automatically detects `Procfile` and runs:
   ```bash
   gunicorn -c gunicorn.conf.py app:app
   ```

---

## 7. Environment Variables Reference

| Variable Name | Description | Default / Example |
|---|---|---|
| `SECRET_KEY` | Flask session & CSRF signing key | `dev-genetic-purity-secret-key-2026` |
| `MONGO_URI` | MongoDB Atlas connection string | `mongodb+srv://<username>:<password>@cluster0.xxx.mongodb.net/?retryWrites=true&w=majority` |
| `DB_NAME` | Target database name | `genetic_purity_db` |
| `TWILIO_ACCOUNT_SID` | Twilio SMS Account SID | `AC...` (Console log fallback if blank) |
| `TWILIO_AUTH_TOKEN` | Twilio SMS Auth Token | `auth_token_string` |
| `TWILIO_PHONE_NUMBER` | Twilio Sender Phone Number | `+1234567890` |
| `RAZORPAY_KEY_ID` | Razorpay API Key ID | `rzp_test_sampleKeyId` |
| `RAZORPAY_KEY_SECRET` | Razorpay API Key Secret | `sampleKeySecret` |
| `ANALYSIS_PRICE_INR` | Price charged per test (INR) | `99` |

---

## 8. Local Setup & Execution

### Step 1: Clone Repository & Create Virtual Environment
```bash
git clone https://github.com/your-org/genetic-purity-ai.git
cd genetic-purity-ai
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables
Copy `.env.example` to `.env` and configure your database URI:
```bash
cp .env.example .env
```

### Step 4: Launch Web Server
```bash
python app.py
```

Access the application in your browser at `http://127.0.0.1:5000/`.
