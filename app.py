import os
from datetime import datetime, timedelta, timezone

from bson import ObjectId

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from pymongo import ASCENDING, MongoClient

from utils import generate_otp, hash_otp, hash_password, send_otp_email, verify_otp, verify_password


load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret-key")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "quiz_question_manager")

mongo_client_kwargs = {}
if MONGO_URI.startswith("mongodb+srv://") or os.getenv("MONGO_TLS", "").lower() in {"1", "true", "yes", "on"}:
    import certifi

    mongo_client_kwargs["tlsCAFile"] = certifi.where()

mongo_client = MongoClient(MONGO_URI, **mongo_client_kwargs)
db = mongo_client[MONGO_DB_NAME]

questions_collection = db["questions"]
admins_collection = db["admins"]
otp_collection = db["otp_challenges"]

otp_collection.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)


def _json_error(message: str, status_code: int = 400):
    return jsonify({"success": False, "message": message}), status_code


def _current_admin_email():
    return session.get("admin_email")


def _admin_exists():
    return admins_collection.find_one({}, {"_id": 1}) is not None


def _auth_required():
    if not _current_admin_email():
        return _json_error("Authentication required.", 401)
    return None


def _serialize_question(question):
    return {
        "id": str(question["_id"]),
        "question_text": question.get("question_text", ""),
        "options": question.get("options", []),
        "correct_answer": question.get("correct_answer", ""),
        "category": question.get("category", ""),
    }


def _validate_question_payload(payload):
    question_text = (payload.get("question_text") or "").strip()
    options = payload.get("options") or []
    correct_answer = (payload.get("correct_answer") or "").strip()
    category = (payload.get("category") or "").strip()

    if not question_text:
        return None, _json_error("Question text is required.")

    if not isinstance(options, list) or len(options) != 4:
        return None, _json_error("Exactly 4 options are required.")

    normalized_options = []
    for option in options:
        text = str(option).strip()
        if not text:
            return None, _json_error("All options must be non-empty.")
        normalized_options.append(text)

    if not correct_answer:
        return None, _json_error("Correct answer is required.")

    if correct_answer not in normalized_options:
        return None, _json_error("Correct answer must match one of the options.")

    if not category:
        return None, _json_error("Category is required.")

    return {
        "question_text": question_text,
        "options": normalized_options,
        "correct_answer": correct_answer,
        "category": category,
    }, None


@app.route("/")
def index():
    if _current_admin_email():
        return redirect(url_for("dashboard"))
    if not _admin_exists():
        return redirect(url_for("register_page"))
    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    auth_error = _auth_required()
    if auth_error:
        return redirect(url_for("index"))
    return render_template("dashboard.html")


@app.route("/register")
def register_page():
    if _current_admin_email():
        return redirect(url_for("dashboard"))
    if _admin_exists():
        return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/api/auth/login", methods=["POST"])
def login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        return _json_error("Email and password are required.")

    if not _admin_exists():
        return _json_error("No admin is registered yet. Please register first.", 403)

    admin = admins_collection.find_one({"email": email})
    if not admin:
        return _json_error("Invalid credentials.", 401)

    stored_password_hash = admin.get("password_hash")
    if not stored_password_hash or not verify_password(password, stored_password_hash):
        return _json_error("Invalid credentials.", 401)

    otp = generate_otp()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    otp_collection.delete_many({"email": email, "purpose": "login"})
    otp_collection.insert_one(
        {
            "email": email,
            "purpose": "login",
            "otp_hash": hash_otp(otp),
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc),
        }
    )

    try:
        send_otp_email(email, otp)
    except Exception as exc:
        otp_collection.delete_many({"email": email, "purpose": "login"})
        return _json_error(f"Unable to send OTP email: {exc}", 502)

    session.clear()
    session["pending_admin_email"] = email

    return jsonify({"success": True, "message": "OTP sent to your email."}), 200


@app.route("/api/auth/verify-otp", methods=["POST"])
def verify_login_otp():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or session.get("pending_admin_email") or "").strip().lower()
    otp = (payload.get("otp") or "").strip()

    if not email or not otp:
        return _json_error("Email and OTP are required.")

    challenge = otp_collection.find_one({"email": email, "purpose": "login"})
    if not challenge:
        return _json_error("OTP is invalid or expired.", 401)

    if not verify_otp(otp, challenge["otp_hash"]):
        return _json_error("OTP is invalid or expired.", 401)

    otp_collection.delete_many({"email": email, "purpose": "login"})
    session.clear()
    session["admin_email"] = email
    session["authenticated_at"] = datetime.now(timezone.utc).isoformat()

    return jsonify({"success": True, "message": "Login successful."}), 200


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully."}), 200


@app.route("/api/auth/status", methods=["GET"])
def auth_status():
    return jsonify(
        {
            "success": True,
            "authenticated": _current_admin_email() is not None,
            "email": _current_admin_email(),
        }
    )


@app.route("/api/auth/register", methods=["POST"])
def register_admin():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        return _json_error("Email and password are required.")

    if _admin_exists():
        return _json_error("Registration is closed because an admin account already exists.", 403)

    otp = generate_otp()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    otp_collection.delete_many({"email": email, "purpose": "register"})
    otp_collection.insert_one(
        {
            "email": email,
            "purpose": "register",
            "otp_hash": hash_otp(otp),
            "password_hash": hash_password(password),
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc),
        }
    )

    try:
        send_otp_email(email, otp)
    except Exception as exc:
        otp_collection.delete_many({"email": email, "purpose": "register"})
        return _json_error(f"Unable to send OTP email: {exc}", 502)

    session["pending_register_email"] = email

    return jsonify({"success": True, "message": "Registration OTP sent to your email."}), 200


@app.route("/api/auth/register/verify-otp", methods=["POST"])
def verify_register_otp():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or session.get("pending_register_email") or "").strip().lower()
    otp = (payload.get("otp") or "").strip()

    if not email or not otp:
        return _json_error("Email and OTP are required.")

    if _admin_exists():
        return _json_error("Registration is closed because an admin account already exists.", 403)

    challenge = otp_collection.find_one({"email": email, "purpose": "register"})
    if not challenge:
        return _json_error("OTP is invalid or expired.", 401)

    if not verify_otp(otp, challenge["otp_hash"]):
        return _json_error("OTP is invalid or expired.", 401)

    admins_collection.insert_one(
        {
            "email": email,
            "password_hash": challenge["password_hash"],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )

    otp_collection.delete_many({"email": email, "purpose": "register"})
    session.pop("pending_register_email", None)

    return jsonify({"success": True, "message": "Admin registered successfully. You can now log in."}), 201


@app.route("/api/questions", methods=["GET"])
def list_questions():
    auth_error = _auth_required()
    if auth_error:
        return auth_error

    questions = [_serialize_question(question) for question in questions_collection.find().sort("category", 1)]
    return jsonify({"success": True, "questions": questions}), 200


@app.route("/api/questions", methods=["POST"])
def create_question():
    auth_error = _auth_required()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    question_data, error_response = _validate_question_payload(payload)
    if error_response:
        return error_response

    result = questions_collection.insert_one(
        {
            **question_data,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )

    created_question = questions_collection.find_one({"_id": result.inserted_id})
    return jsonify({"success": True, "message": "Question created.", "question": _serialize_question(created_question)}), 201


@app.route("/api/questions/<question_id>", methods=["PUT"])
def update_question(question_id):
    auth_error = _auth_required()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    question_data, error_response = _validate_question_payload(payload)
    if error_response:
        return error_response

    try:
        object_id = ObjectId(question_id)
    except Exception:
        return _json_error("Invalid question id.", 400)

    update_result = questions_collection.update_one(
        {"_id": object_id},
        {"$set": {**question_data, "updated_at": datetime.now(timezone.utc)}},
    )

    if update_result.matched_count == 0:
        return _json_error("Question not found.", 404)

    updated_question = questions_collection.find_one({"_id": object_id})
    return jsonify({"success": True, "message": "Question updated.", "question": _serialize_question(updated_question)}), 200


@app.route("/api/questions/<question_id>", methods=["DELETE"])
def delete_question(question_id):
    auth_error = _auth_required()
    if auth_error:
        return auth_error

    try:
        object_id = ObjectId(question_id)
    except Exception:
        return _json_error("Invalid question id.", 400)

    delete_result = questions_collection.delete_one({"_id": object_id})
    if delete_result.deleted_count == 0:
        return _json_error("Question not found.", 404)

    return jsonify({"success": True, "message": "Question deleted.", "question_id": question_id}), 200


@app.route("/api/auth/seed-admin", methods=["POST"])
def seed_admin():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        return _json_error("Email and password are required.")

    admins_collection.update_one(
        {"email": email},
        {"$set": {"email": email, "password_hash": hash_password(password), "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )

    return jsonify({"success": True, "message": "Admin account saved."}), 200


@app.route("/api/auth/bootstrap", methods=["GET"])
def bootstrap():
    default_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    default_password = os.getenv("ADMIN_PASSWORD", "")

    if default_email and default_password:
        admins_collection.update_one(
            {"email": default_email},
            {"$set": {"email": default_email, "password_hash": hash_password(default_password), "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )

        return jsonify({"success": True, "message": "Bootstrap admin account ready."}), 200

    return _json_error("ADMIN_EMAIL and ADMIN_PASSWORD are not set.", 400)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"success": True, "status": "ok"})


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "true").lower() in {"1", "true", "yes", "on"})