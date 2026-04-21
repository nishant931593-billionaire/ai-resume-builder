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

# ---------------- SAFE JSON ----------------
def safe_json(text: str):
    try:
        text = text.strip()
        if "```" in text:
            text = text.split("```")[1]

        start = text.find("{")
        end = text.rfind("}")
        return json.loads(text[start:end+1])
    except:
        return {}

# ---------------- ENRICH (PREMIUM FIX) ----------------
def enrich(data):
    data.setdefault("name", "")
    data.setdefault("email", "")
    data.setdefault("phone", "")
    data.setdefault("title", "Professional")
    data.setdefault("summary", "")
    data.setdefault("skills", [])
    data.setdefault("experience", [])
    data.setdefault("projects", [])
    data.setdefault("education", [])

    # 🔥 Strong summary
    if not data["summary"]:
        data["summary"] = (
            "Results-driven professional with strong analytical and problem-solving skills. "
            "Experienced in delivering high-quality work, collaborating with teams, and "
            "adapting quickly to new challenges while maintaining efficiency and accuracy."
        )

    # 🔥 Ensure enough skills
    if len(data["skills"]) < 6:
        data["skills"] = list(set(data["skills"] + [
            "Communication", "Problem Solving", "Teamwork",
            "Time Management", "Adaptability", "Attention to Detail"
        ]))

    # 🔥 Expand experience
    for exp in data["experience"]:
        exp.setdefault("points", [])
        while len(exp["points"]) < 4:
            exp["points"].append(
                "Collaborated with cross-functional teams to complete tasks efficiently while maintaining quality standards."
            )

    # 🔥 Expand projects
    for proj in data["projects"]:
        proj.setdefault("points", [])
        while len(proj["points"]) < 3:
            proj["points"].append(
                "Designed and developed features aligned with project requirements, ensuring performance and usability."
            )

    return data

# ---------------- AI GENERATION ----------------
def generate_resume(resume_text, job_description):
    prompt = f"""
Rewrite this resume into a PREMIUM ATS-optimized format.

STRICT:
- No fake experience
- No fake projects
- No fake metrics

GOAL:
- Make it LOOK full, strong, and professional
- Expand wording naturally

REQUIRE:
- Add title
- Add strong summary (4 lines)
- Experience: 3-5 bullet points each
- Projects: 2-3 bullet points each

OUTPUT JSON:

{{
  "name": "",
  "email": "",
  "phone": "",
  "title": "",
  "summary": "",
  "skills": [],
  "experience": [],
  "projects": [],
  "education": []
}}

RESUME:
{resume_text}

JOB:
{job_description}
"""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}]
    )

    return safe_json(response.choices[0].message.content)

# ---------------- OPTIMIZE ----------------
@app.post("/optimize-resume")
def optimize_resume(data: ResumeRequest):
    try:
        if data.template not in ["modern", "creative", "minimal"]:
            data.template = "modern"

        raw = generate_resume(data.resume, data.job_description)
        result = enrich(raw)

        resume_id = str(uuid.uuid4())

        resume_store[resume_id] = {
            "data": result,
            "paid": False,
            "template": data.template,
            "file": None,
            "created_at": time.time()
        }

        return {
            "success": True,
            "resume_id": resume_id,
            "data": result
        }

    except Exception as e:
        print("ERROR:", e)
        raise HTTPException(status_code=500, detail="Processing failed")

# ---------------- ORDER ----------------
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

# ---------------- VERIFY ----------------
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