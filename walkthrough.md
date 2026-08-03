# Genetic Purity AI - Production Web Application Conversion Walkthrough (Phase 1)

The Genetic Purity AI middleware has been restructured into a modular, production-ready web application with MongoDB Atlas user storage, bcrypt password security, Flask-Login session management, SMS OTP password recovery, dark-theme landing page, authenticated dashboard, and protected plant purity testing endpoints.

---

## 1. Folder Structure

```
genetic-purity-ai/
├── app.py                     # Main application factory & prediction endpoints
├── config.py                  # Configuration settings & environment variables
├── detect.py                  # [UNTOUCHED] Production MobileNet prediction engine
├── model.keras                # [UNTOUCHED] Production Keras model
├── gunicorn.conf.py           # Production server configuration
├── Procfile                   # Deployment process configuration
├── requirements.txt           # Python package dependencies
├── .env.example               # Environment variables template
├── .env                       # Local environment variables configuration
│
├── database/                  # Database connectivity module
│   └── db.py                  # MongoDB Atlas client & index manager
│
├── models/                    # Data models
│   └── user.py                # User model with Flask-Login & bcrypt hashing
│
├── auth/                      # Authentication blueprint
│   ├── __init__.py            # Blueprint declaration
│   └── routes.py              # Signup, Login, Logout, & OTP password reset routes
│
├── routes/                    # Main navigation blueprint
│   ├── __init__.py            # Blueprint declaration
│   └── main_routes.py         # Landing page, Dashboard, & Plant Testing views
│
├── services/                  # Business & external integration services
│   └── sms_service.py         # Twilio SMS OTP provider & dev console logger
│
├── utils/                     # Input validation & helper utilities
│   └── validators.py          # Email, mobile, & password strength validators
│
├── static/                    # Static UI assets
│   ├── css/
│   │   └── style.css          # Dark theme styles & glassmorphic UI tokens
│   └── js/
│       ├── auth.js            # Client-side form validation & strength meter
│       └── script.js          # Plant purity prediction & Chart.js renderer
│
├── templates/                 # Jinja2 HTML templates
│   ├── base.html              # Dark mode layout base with flash messages
│   ├── index.html             # Landing page (Hero, Features, How It Works, Pricing)
│   ├── dashboard.html         # Authenticated user dashboard
│   ├── test_purity.html       # Plant Genetic Purity Testing UI
│   └── auth/
│       ├── login.html         # Login page (Email / Mobile + Password)
│       ├── signup.html        # Registration page
│       ├── forgot_password.html # Enter mobile number for OTP
│       ├── verify_otp.html     # Enter received 6-digit OTP
│       └── reset_password.html # Set new password
│
└── uploads/                   # Temporary upload directory (auto-cleaned)
```

---

## 2. MongoDB Schema

### Collection: `users`
| Field | Type | Description / Constraint |
|---|---|---|
| `_id` | ObjectId | MongoDB unique primary key |
| `firstName` | String | User first name |
| `lastName` | String | User last name |
| `mobileNumber` | String | Cleaned E.164 / 10-15 digit mobile number (Unique Index) |
| `email` | String | Cleaned lowercase email address (Unique Index) |
| `passwordHash` | String | Encrypted password string hashed with `bcrypt` + salt |
| `createdAt` | UTC DateTime | Account creation timestamp |
| `updatedAt` | UTC DateTime | Last account update timestamp |
| `isVerified` | Boolean | Verification flag (`True` upon registration) |
| `role` | String | User access level (`user` or `admin`) |

### Collection: `otp_requests`
| Field | Type | Description / Constraint |
|---|---|---|
| `_id` | ObjectId | MongoDB unique key |
| `mobileNumber` | String | Target mobile number for reset OTP |
| `otp` | String | 6-digit random verification code |
| `createdAt` | UTC DateTime | Generation timestamp |
| `expiresAt` | UTC DateTime | TTL Expiration timestamp (10 minutes max) |

---

## 3. Authentication Flow

```
[ Unauthenticated Visitor ]
           │
           ├───────────────► [/] Landing Page
           │
           ├───────────────► [/auth/signup] Fill Form ──► Bcrypt Hash ──► Create User in MongoDB ──► Auto-login
           │
           └───────────────► [/auth/login] Enter Email OR Mobile + Password ──► Flask-Login Session

[ Protected Route Access Attempt ]
           │
           ├──► [/dashboard, /test, /predict]
           │         │
           │         ├──► Is User Authenticated?
           │         │          ├── YES: Access Granted
           │         │          └── NO : Redirect to [/auth/login] (or HTTP 401 for /predict)

[ Forgot Password SMS OTP Workflow ]
           │
           ├──► [/auth/forgot-password] Enter Mobile Number
           │         │
           │         ▼
           ├──► Generate 6-Digit OTP ──► Send via Twilio SMS (or log in dev console)
           │         │
           │         ▼
           ├──► [/auth/verify-otp] Enter 6-Digit OTP
           │         │
           │         ▼
           └──► [/auth/reset-password] Enter New Password ──► Update MongoDB ──► Redirect to Login
```

---

## 4. Application Routes

| Route Path | Method(s) | Auth Required | Blueprint / File | Purpose |
|---|---|---|---|---|
| `/` | GET | No | `main.index` | Public Landing Page with Hero, Features, How It Works, Pricing |
| `/dashboard` | GET | **Yes** | `main.dashboard` | Authenticated User Workspace |
| `/test`, `/upload` | GET | **Yes** | `main.test_purity` | Plant Genetic Purity Testing Upload UI |
| `/predict` | POST | **Yes** | `app.predict` | Executes `detect.py` prediction pipeline & returns JSON |
| `/convert-preview` | POST | **Yes** | `app.convert_preview` | Converts HEIC/DNG to base64 preview |
| `/health` | GET | No | `app.health` | Healthcheck endpoint (`200 OK`) |
| `/auth/signup` | GET, POST | No | `auth.signup` | User Registration |
| `/auth/login` | GET, POST | No | `auth.login` | User Login with Email or Mobile |
| `/auth/logout` | GET | **Yes** | `auth.logout` | Terminate session & log out |
| `/auth/forgot-password` | GET, POST | No | `auth.forgot_password` | Request SMS OTP for password reset |
| `/auth/verify-otp` | GET, POST | No | `auth.verify_otp` | Verify 6-digit SMS OTP |
| `/auth/reset-password` | GET, POST | No | `auth.reset_password` | Set new password after verification |

---

## 5. Environment Variables Required

Create a `.env` file in the root directory:

```env
# Flask Secret Key for session cookie signing
SECRET_KEY=your_random_secret_key_here

# MongoDB Atlas Connection String
# Example for Atlas: mongodb+srv://<username>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority
MONGO_URI=mongodb+srv://<username>:<password>@cluster0.xxx.mongodb.net/?retryWrites=true&w=majority
DB_NAME=genetic_purity_db

# Twilio SMS API Credentials (Optional - Dev mode fallback prints OTP to console if blank)
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
```

---

## 6. Setup & Execution Instructions

### Prerequisites
- Python 3.10+
- MongoDB instance (local or MongoDB Atlas cluster)

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables
Copy `.env.example` to `.env` and set your MongoDB Atlas URI:
```bash
cp .env.example .env
```

### Step 3: Run the Application
```bash
python app.py
```

Open your browser to `http://127.0.0.1:5000/`.

---

## Verification Results

1. **Python Compilation**: All 8 backend Python modules (`app.py`, `config.py`, `database/db.py`, `models/user.py`, `services/sms_service.py`, `utils/validators.py`, `auth/routes.py`, `routes/main_routes.py`) compiled cleanly.
2. **Unit Tests**: Ran bcrypt password hashing and field validators test suite (`test_auth_logic.py`). All tests passed.
3. **Protection**: `/predict`, `/dashboard`, and `/test` routes require active Flask-Login session authentication.
4. **Preserved Core**: `detect.py`, `model.keras`, preprocessing, and classification thresholds remain 100% untouched.
