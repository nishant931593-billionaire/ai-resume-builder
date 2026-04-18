from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import os
from dotenv import load_dotenv
from openai import OpenAI
import razorpay

from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

# 🔹 Load ENV
load_dotenv()

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
    raise Exception("Razorpay keys missing")

if not OPENAI_API_KEY:
    raise Exception("OpenAI API key missing")

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

# 🔹 Temp storage (replace with DB later)
resume_store = {}

# 🔹 Models
class ResumeRequest(BaseModel):
    resume: str
    job_description: str

class PaymentRequest(BaseModel):
    amount: int
    resume_id: str


@app.get("/")
def home():
    return {"message": "AI Resume Builder Live 🚀"}


# 🔹 Optimize Resume
@app.post("/optimize-resume")
def optimize_resume(data: ResumeRequest):
    try:
        if not data.resume or not data.job_description:
            raise HTTPException(status_code=400, detail="Missing input")

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert ATS resume writer."},
                {
                    "role": "user",
                    "content": f"Improve this resume based on job description.\n\nResume:\n{data.resume}\n\nJob:\n{data.job_description}"
                }
            ]
        )

        result = response.choices[0].message.content

        resume_id = str(len(resume_store) + 1)
        resume_store[resume_id] = {
            "content": result,
            "paid": False
        }

        return {
            "success": True,
            "resume_id": resume_id,
            "data": result
        }

    except Exception as e:
        print("OPTIMIZE ERROR:", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# 🔹 Create Order
@app.post("/create-order")
def create_order(data: PaymentRequest):
    try:
        if data.resume_id not in resume_store:
            raise HTTPException(status_code=404, detail="Invalid resume_id")

        order = razorpay_client.order.create({
            "amount": data.amount * 100,
            "currency": "INR",
            "payment_capture": 1
        })

        return {
            "id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"]
        }

    except Exception as e:
        print("RAZORPAY ERROR:", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# 🔹 Verify Payment
@app.post("/verify-payment")
def verify_payment(payload: dict):
    try:
        razorpay_client.utility.verify_payment_signature(payload)

        resume_id = payload.get("resume_id")

        if resume_id and resume_id in resume_store:
            resume_store[resume_id]["paid"] = True

        return {
            "status": "Payment successful",
            "download_url": f"/download/{resume_id}"
        }

    except Exception as e:
        print("VERIFY ERROR:", str(e))
        raise HTTPException(status_code=400, detail="Payment verification failed")


# 🔹 Download Resume
@app.get("/download/{resume_id}")
def download_resume(resume_id: str):
    if resume_id not in resume_store:
        raise HTTPException(status_code=404, detail="Resume not found")

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