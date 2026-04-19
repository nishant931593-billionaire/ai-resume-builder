from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import os
import time
import hmac
import hashlib
import uuid
import json

from dotenv import load_dotenv
from openai import OpenAI
import razorpay

from jinja2 import Template
from weasyprint import HTML


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


# 🔹 Storage
resume_store = {}

# 🔹 Price ₹99
PRICE = 9900

# 🔹 Ensure folder
os.makedirs("generated", exist_ok=True)


# 🔹 Models
class ResumeRequest(BaseModel):
    resume: str
    job_description: str
    template: str = "modern"


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
        prompt = f"""
You are an expert resume writer.

Convert the resume into structured JSON.

RULES:
- Extract real information only
- Keep it concise
- Use bullet points for experience

RETURN ONLY VALID JSON:

{{
  "name": "",
  "email": "",
  "phone": "",
  "skills": [],
  "experience": [],
  "education": []
}}

RESUME:
{data.resume}

JOB DESCRIPTION:
{data.job_description}
"""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Expert resume parser"},
                {"role": "user", "content": prompt}
            ]
        )

        raw_output = response.choices[0].message.content

        try:
            parsed = json.loads(raw_output)
        except:
            raise HTTPException(status_code=500, detail="AI parsing failed")

        resume_id = str(len(resume_store) + 1)

        resume_store[resume_id] = {
            "data": parsed,
            "paid": False,
            "order_id": None,
            "template": data.template,
            "file": None,
            "created_at": time.time()
        }

        return {
            "success": True,
            "resume_id": resume_id,
            "data": parsed   # 👈 send structured data
        }

    except Exception as e:
        print("OPTIMIZE ERROR:", str(e))
        raise HTTPException(status_code=500, detail="Optimization failed")


# ---------------- CREATE ORDER ----------------
@app.post("/create-order")
def create_order(data: PaymentRequest):
    if data.resume_id not in resume_store:
        raise HTTPException(status_code=404, detail="Invalid resume_id")

    order = razorpay_client.order.create({
        "amount": PRICE,
        "currency": "INR",
        "payment_capture": 1
    })

    resume_store[data.resume_id]["order_id"] = order["id"]

    return order


# ---------------- VERIFY PAYMENT ----------------
@app.post("/verify-payment")
def verify_payment(payload: dict):
    resume_id = payload.get("resume_id")

    if resume_id not in resume_store:
        raise HTTPException(status_code=400, detail="Invalid resume")

    stored_order = resume_store[resume_id]["order_id"]

    generated_signature = hmac.new(
        RAZORPAY_KEY_SECRET.encode(),
        f"{payload['razorpay_order_id']}|{payload['razorpay_payment_id']}".encode(),
        hashlib.sha256
    ).hexdigest()

    if generated_signature != payload.get("razorpay_signature"):
        raise HTTPException(status_code=400, detail="Invalid signature")

    resume_store[resume_id]["paid"] = True

    return {
        "download_url": f"/download/{resume_id}"
    }


# ---------------- PDF GENERATION ----------------
def generate_pdf(resume_id: str):
    data = resume_store[resume_id]["data"]
    template_name = resume_store[resume_id]["template"]

    with open(f"templates/{template_name}.html", "r", encoding="utf-8") as f:
        template = Template(f.read())

    html = template.render(
        name=data.get("name", ""),
        email=data.get("email", ""),
        phone=data.get("phone", ""),
        skills=data.get("skills", []),
        experience=data.get("experience", []),
        education=data.get("education", [])
    )

    file_name = f"{uuid.uuid4().hex}.pdf"
    file_path = f"generated/{file_name}"

    HTML(string=html).write_pdf(file_path)

    resume_store[resume_id]["file"] = file_path

    return file_path


# ---------------- DOWNLOAD ----------------
@app.get("/download/{resume_id}")
def download_resume(resume_id: str):
    if resume_id not in resume_store:
        raise HTTPException(status_code=404, detail="Not found")

    if not resume_store[resume_id]["paid"]:
        raise HTTPException(status_code=403, detail="Payment required")

    if not resume_store[resume_id]["file"]:
        generate_pdf(resume_id)

    return FileResponse(
        resume_store[resume_id]["file"],
        media_type="application/pdf",
        filename="resume.pdf"
    )