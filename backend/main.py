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


# ---------------- ENV ----------------
load_dotenv()

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, OPENAI_API_KEY]):
    raise Exception("Missing environment variables")


# ---------------- APP ----------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------- CLIENTS ----------------
openai_client = OpenAI(api_key=OPENAI_API_KEY)
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


# ---------------- STORAGE ----------------
resume_store = {}
PRICE = 100  # ₹49
os.makedirs("generated", exist_ok=True)


# ---------------- MODELS ----------------
class ResumeRequest(BaseModel):
    resume: str
    job_description: str
    template: str = "modern"


class PaymentRequest(BaseModel):
    resume_id: str


# ---------------- JSON CLEANER ----------------
def clean_json(text: str):
    try:
        text = text.strip()

        if "```" in text:
            text = text.split("```")[1]

        return json.loads(text)
    except:
        return {}


# ---------------- OPTIMIZE RESUME ----------------
@app.post("/optimize-resume")
def optimize_resume(data: ResumeRequest):
    try:
        prompt = f"""
You are a professional ATS resume writer.

GOAL:
Create a FULL, DETAILED, PROFESSIONAL resume.

IMPORTANT:
- Do NOT invent fake companies or projects
- Do NOT add unrealistic achievements
- BUT expand existing information strongly

RULES:

1. SUMMARY:
- Write a 2–3 line professional summary based on resume + job description

2. SKILLS:
- Expand to 8–12 relevant skills (only from resume + job description)

3. EXPERIENCE:
- Each role must have 3–5 bullet points
- Expand short lines into detailed sentences (12–20 words)

4. PROJECTS:
- Each project must have 2–4 bullet points

5. CONTENT EXPANSION:
- If content is small → expand using logical responsibilities
- Use job description for context (NO fake roles)

FORMAT (JSON ONLY):

{{
  "name": "",
  "email": "",
  "phone": "",
  "summary": "",
  "skills": [],
  "experience": [
    {{
      "role": "",
      "company": "",
      "duration": "",
      "points": []
    }}
  ],
  "projects": [
    {{
      "name": "",
      "points": []
    }}
  ],
  "education": []
}}

RESUME:
{data.resume}

JOB DESCRIPTION:
{data.job_description}
"""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.choices[0].message.content
        parsed = clean_json(content)

        if not parsed:
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
            "data": parsed
        }

    except Exception as e:
        print("OPTIMIZE ERROR:", e)
        raise HTTPException(status_code=500, detail="Processing failed")


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

    generated_signature = hmac.new(
        RAZORPAY_KEY_SECRET.encode(),
        f"{payload['razorpay_order_id']}|{payload['razorpay_payment_id']}".encode(),
        hashlib.sha256
    ).hexdigest()

    if generated_signature != payload.get("razorpay_signature"):
        raise HTTPException(status_code=400, detail="Invalid signature")

    resume_store[resume_id]["paid"] = True

    return {"download_url": f"/download/{resume_id}"}


# ---------------- PDF ----------------
def generate_pdf(resume_id: str):
    data = resume_store[resume_id]["data"]
    template_name = resume_store[resume_id]["template"]

    with open(f"templates/{template_name}.html", "r", encoding="utf-8") as f:
        template = Template(f.read())

    html = template.render(**data)

    file_path = f"generated/{uuid.uuid4().hex}.pdf"
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