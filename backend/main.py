from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

import os
from dotenv import load_dotenv
from openai import OpenAI
import razorpay
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

# Load environment variables
load_dotenv()

# Initialize FastAPI
app = FastAPI()

# Enable CORS (important for frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OpenAI
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")
)

# Initialize Razorpay
razorpay_client = razorpay.Client(auth=(
    os.environ.get("RAZORPAY_KEY_ID"),
    os.environ.get("RAZORPAY_KEY_SECRET")
))

# Temporary storage (use DB later)
resume_store = {}

# Models
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

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert ATS resume writer."},
                {"role": "user", "content": f"Resume:\n{data.resume}\n\nJob:\n{data.job_description}"}
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
        print("ERROR:", str(e))   # 👈 shows in Render logs
        return {"success": False, "detail": str(e)}  # 👈 shows in frontend

# 🔹 Create Razorpay Order
@app.post("/create-order")
def create_order(data: PaymentRequest):
    try:
        order = razorpay_client.order.create({
            "amount": data.amount * 100,
            "currency": "INR",
            "payment_capture": 1,
            "notes": {
                "resume_id": data.resume_id
            }
        })
        return order

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 🔹 Verify Payment
@app.post("/verify-payment")
def verify_payment(payload: dict):
    try:
        razorpay_client.utility.verify_payment_signature(payload)

        # NOTE: Razorpay does not send notes back here reliably
        # So we trust frontend resume_id (simple MVP approach)
        return {"status": "Payment successful"}

    except Exception:
        raise HTTPException(status_code=400, detail="Payment verification failed")


# 🔹 Download Resume (Locked)
@app.get("/download/{resume_id}")
def download_resume(resume_id: str):
    if resume_id not in resume_store:
        raise HTTPException(status_code=404, detail="Resume not found")

    # For MVP, allow download (you can enforce payment later)
    # if not resume_store[resume_id]["paid"]:
    #     raise HTTPException(status_code=403, detail="Payment required")

    file_path = f"{resume_id}.pdf"

    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()

    content = []
    text = resume_store[resume_id]["content"]

    for line in text.split("\n"):
        content.append(Paragraph(line, styles["Normal"]))

    doc.build(content)

    return {"download_url": f"/{file_path}"}