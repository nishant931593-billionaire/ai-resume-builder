from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import os, time, hmac, hashlib, uuid, json
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

# 🔹 APP
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔹 CLIENTS
openai_client = OpenAI(api_key=OPENAI_API_KEY)

razorpay_client = razorpay.Client(auth=(
    RAZORPAY_KEY_ID,
    RAZORPAY_KEY_SECRET
))

# 🔹 STORAGE
resume_store = {}
PRICE = 4900  # ✅ ₹49
os.makedirs("generated", exist_ok=True)

# 🔹 MODELS
class ResumeRequest(BaseModel):
    resume: str
    job_description: str
    template: str = "modern"

class PaymentRequest(BaseModel):
    resume_id: str

# ---------------- HOME ----------------
@app.get("/")
def home():
    return {"message": "AI Resume Builder 🚀"}

# ---------------- SAFE JSON PARSER ----------------
def safe_json_parse(text):
    try:
        return json.loads(text)
    except:
        print("JSON ERROR:", text)
        return {}

# ---------------- STEP 1 ----------------
def extract_resume_data(resume_text: str):
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"Extract structured JSON from resume:\n{resume_text}"
            }]
        )

        content = response.choices[0].message.content
        return safe_json_parse(content)

    except Exception as e:
        print("EXTRACT ERROR:", e)
        return {}

# ---------------- STEP 2 ----------------
def rewrite_resume(data: dict, job_description: str):
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"Rewrite resume for ATS:\nDATA:{json.dumps(data)}\nJOB:{job_description}"
            }]
        )

        content = response.choices[0].message.content
        return safe_json_parse(content)

    except Exception as e:
        print("REWRITE ERROR:", e)
        return data

# ---------------- OPTIMIZE ----------------
@app.post("/optimize-resume")
def optimize_resume(data: ResumeRequest):
    try:
        extracted = extract_resume_data(data.resume)

        if not extracted:
            raise Exception("Extraction failed")

        final_resume = rewrite_resume(extracted, data.job_description)

        resume_id = str(len(resume_store) + 1)

        resume_store[resume_id] = {
            "data": final_resume,
            "paid": False,
            "order_id": None,
            "template": data.template,
            "file": None,
            "created_at": time.time()
        }

        return {
            "success": True,
            "resume_id": resume_id,
            "data": json.dumps(final_resume, indent=2)  # ✅ prevent frontend crash
        }

    except Exception as e:
        print("OPTIMIZE ERROR:", e)
        raise HTTPException(status_code=500, detail="Processing failed")

# ---------------- CREATE ORDER ----------------
@app.post("/create-order")
def create_order(data: PaymentRequest):
    try:
        if data.resume_id not in resume_store:
            raise HTTPException(status_code=404, detail="Invalid resume_id")

        order = razorpay_client.order.create({
            "amount": PRICE,  # ✅ ₹49
            "currency": "INR",
            "payment_capture": 1
        })

        resume_store[data.resume_id]["order_id"] = order["id"]

        return order

    except Exception as e:
        print("ORDER ERROR:", e)
        raise HTTPException(status_code=500, detail="Order failed")

# ---------------- VERIFY ----------------
@app.post("/verify-payment")
def verify_payment(payload: dict):
    try:
        resume_id = payload.get("resume_id")

        if resume_id not in resume_store:
            raise HTTPException(status_code=400, detail="Invalid resume")

        generated_signature = hmac.new(
            RAZORPAY_KEY_SECRET.encode(),
            f"{payload['razorpay_order_id']}|{payload['razorpay_payment_id']}".encode(),
            hashlib.sha256
        ).hexdigest()

        if generated_signature != payload.get("razorpay_signature"):
            raise HTTPException(status_code=400, detail="Invalid signature")

        resume_store[resume_id]["paid"] = True

        return {"download_url": f"/download/{resume_id}"}

    except Exception as e:
        print("VERIFY ERROR:", e)
        raise HTTPException(status_code=500, detail="Verification failed")

# ---------------- PDF ----------------
def generate_pdf(resume_id: str):
    try:
        data = resume_store[resume_id]["data"]
        template_name = resume_store[resume_id]["template"]

        with open(f"templates/{template_name}.html", "r", encoding="utf-8") as f:
            template = Template(f.read())

        html = template.render(**data)

        file_path = f"generated/{uuid.uuid4().hex}.pdf"

        HTML(string=html).write_pdf(file_path)

        resume_store[resume_id]["file"] = file_path

        return file_path

    except Exception as e:
        print("PDF ERROR:", e)
        raise Exception("PDF generation failed")

# ---------------- DOWNLOAD ----------------
@app.get("/download/{resume_id}")
def download_resume(resume_id: str):
    try:
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

    except Exception as e:
        print("DOWNLOAD ERROR:", e)
        raise HTTPException(status_code=500, detail="Download failed")