# Quiz Question Manager

Flask app for admin-authenticated quiz question CRUD with OTP login and a Tailwind CSS frontend.

## Stack

- Backend: Flask, PyMongo
- Frontend: Tailwind CSS via CDN (no Bootstrap, no npm)
- Auth: Password hash + OTP verification

## Prerequisites

- Python 3.10+
- MongoDB (local or Atlas)

## Setup

1. Install Python dependencies:

```bash
pip install -r requirements.txt
```

2. Set environment variables in `.env`:

```env
FLASK_SECRET_KEY=replace-with-a-strong-random-secret
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=quiz_question_manager

SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your-smtp-user
SMTP_PASSWORD=your-smtp-password
SMTP_FROM_EMAIL=no-reply@example.com
```

## Run

```bash
flask --app app run --debug
```

Open http://127.0.0.1:5000

## Notes

- All templates extend `templates/base.html`.
- Tailwind is loaded from CDN in `templates/base.html`.