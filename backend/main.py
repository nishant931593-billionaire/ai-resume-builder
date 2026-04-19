from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import os
import time
import hmac
import hashlib
from dotenv import load_dotenv
from openai import OpenAI
import razorpay

from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet


# 🔹 ENV
load_dotenv()

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, OPENAI_API_KEY]):
    raise Exception("Missing environment variables")


# 🔹 App
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 🔹 Clients
openai_client = OpenAI(api_key=OPENAI_API_KEY)

razorpay_client = razorpay.Client(auth=(
    RAZORPAY_KEY_ID,
    RAZORPAY_KEY_SECRET
))


# 🔹 In-memory storage (MVP only)
resume_store = {}

# 🔹 Fixed price (₹99 only)
PRICE = 9900


# 🔹 Models
class ResumeRequest(BaseModel):
    resume: str
    job_description: str


class PaymentRequest(BaseModel):
    resume_id: str


# ---------------- HOME ----------------
@app.get("/")
def home():
    return {"message": "AI Resume Builder Live 🚀"}


# ---------------- OPTIMIZE RESUME ----------------
@app.post("/optimize-resume")
def optimize_resume(data: ResumeRequest):
    try:
        if not data.resume or not data.job_description:
            raise HTTPException(status_code=400, detail="Missing input")

        prompt = f"""
You are an expert ATS resume writer.

TASK:
- Rewrite full resume professionally
- Add strong action verbs
- Add ATS keywords from job description
- Add measurable achievements
- Make it recruiter-ready

OUTPUT:
Only final optimized resume.

RESUME:
{data.resume}

JOB DESCRIPTION:
{data.job_description}
"""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Expert resume optimizer"},
                {"role": "user", "content": prompt}
            ]
        )

        result = response.choices[0].message.content

        resume_id = str(len(resume_store) + 1)

        resume_store[resume_id] = {
            "content": result,
            "paid": False,
            "order_id": None,
            "created_at": time.time()
        }

        return {
            "success": True,
            "resume_id": resume_id,
            "data": result
        }

    except Exception as e:
        print("OPTIMIZE ERROR:", str(e))
        raise HTTPException(status_code=500, detail="Optimization failed")


# ---------------- CREATE ORDER ----------------
@app.post("/create-order")
def create_order(data: PaymentRequest):
    try:
        if data.resume_id not in resume_store:
            raise HTTPException(status_code=404, detail="Invalid resume_id")

        order = razorpay_client.order.create({
            "amount": PRICE,
            "currency": "INR",
            "payment_capture": 1
        })

        resume_store[data.resume_id]["order_id"] = order["id"]

        return {
            "id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"]
        }

    except Exception as e:
        print("ORDER ERROR:", str(e))
        raise HTTPException(status_code=500, detail="Order failed")


# ---------------- VERIFY PAYMENT ----------------
@app.post("/verify-payment")
def verify_payment(payload: dict):
    try:
        resume_id = payload.get("resume_id")

        if not resume_id or resume_id not in resume_store:
            raise HTTPException(status_code=400, detail="Invalid resume")

        stored_order = resume_store[resume_id].get("order_id")
        if not stored_order or stored_order != payload.get("razorpay_order_id"):
            raise HTTPException(status_code=400, detail="Order mismatch")

        # 🔐 Signature verification (secure way)
        generated_signature = hmac.new(
            RAZORPAY_KEY_SECRET.encode(),
            f"{payload['razorpay_order_id']}|{payload['razorpay_payment_id']}".encode(),
            hashlib.sha256
        ).hexdigest()

        if generated_signature != payload.get("razorpay_signature"):
            raise HTTPException(status_code=400, detail="Invalid signature")

        resume_store[resume_id]["paid"] = True

        return {
            "status": "Payment successful",
            "download_url": f"/download/{resume_id}"
        }

    except Exception as e:
        print("VERIFY ERROR:", str(e))
        raise HTTPException(status_code=400, detail="Payment failed")


# ---------------- DOWNLOAD ----------------
@app.get("/download/{resume_id}")
def download_resume(resume_id: str):
    if resume_id not in resume_store:
        raise HTTPException(status_code=404, detail="Not found")

    if not resume_store[resume_id]["paid"]:
        raise HTTPException(status_code=403, detail="Payment required")

    file_path = f"{resume_id}.pdf"

    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()

    content = []
    text = resume_store[resume_id]["content"]

    for line in text.split("\n"):
        content.append(Paragraph(line, styles["Normal"]))

    doc.build(content)

    return FileResponse(
        file_path,
        media_type="application/pdf",
        filename="resume.pdf"
    )