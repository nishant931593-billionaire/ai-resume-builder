from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import os
from openai import OpenAI
import razorpay
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

# Load env
load_dotenv()

app = FastAPI()

# Clients
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

razorpay_client = razorpay.Client(auth=(
    os.getenv("RAZORPAY_KEY_ID"),
    os.getenv("RAZORPAY_KEY_SECRET")
))

# Store resumes temporarily (use DB later)
resume_store = {}

# Models
class ResumeRequest(BaseModel):
    resume: str
    job_description: str

class PaymentRequest(BaseModel):
    amount: int
    resume_id:str


@app.get("/")
def home():
    return {"message": "Backend Running with Payments 🚀"}


# 🔹 1. Optimize Resume
@app.post("/optimize-resume")
def optimize_resume(data: ResumeRequest):
    try:
        print("Incoming request")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": f"Resume: {data.resume}\nJob: {data.job_description}"}
            ]
        )

        result = response.choices[0].message.content

        return {"success": True, "data": result}

    except Exception as e:
        print("ERROR:", str(e))  # 👈 shows in Render logs
        raise HTTPException(status_code=500, detail=str(e))

# 🔹 2. Create Razorpay Order
@app.post("/create-order")
def create_order(data: PaymentRequest):
    try:
        order = razorpay_client.order.create({
            "amount": data.amount * 100,  # paise
            "currency": "INR",
            "payment_capture": 1,
            "notes":{
                "resume_id": data.resume_id
            }
        })
        return order
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 🔹 3. Verify Payment
@app.post("/verify-payment")
def verify_payment(payload: dict):
    try:
        razorpay_client.utility.verify_payment_signature(payload)

        resume_id = payload.get("notes", {}).get("resume_id")

        if resume_id in resume_store:
            resume_store[resume_id]["paid"] = True

        return {"status": "Payment successful"}

    except Exception:
        raise HTTPException(status_code=400, detail="Payment verification failed")


# 🔹 4. Download PDF (LOCKED)
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

    return {"download_url": f"/{file_path}"}