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
import uvicorn

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


# ---------------- SAFE JSON ----------------
def safe_json(text: str):
    try:
        text = text.strip()

        if "```" in text:
            text = text.split("```")[1]

        start = text.find("{")
        end = text.rfind("}")

        return json.loads(text[start:end + 1])
    except:
        return {}


# ---------------- NORMALIZE ----------------
def normalize(data):
    return {
        "name": data.get("name", ""),
        "email": data.get("email", ""),
        "phone": data.get("phone", ""),
        "title": data.get("title", ""),
        "summary": data.get("summary", ""),
        "skills": data.get("skills", []),
        "experience": data.get("experience", []),
        "projects": data.get("projects", []),
        "education": data.get("education", []),
        "extra_sections": data.get("extra_sections", [])
    }


# ---------------- AI ENGINE ----------------
def generate_resume(resume_text, job_description):

    prompt = f"""
You are a STRICT resume optimization engine.

========================
ABSOLUTE RULES
========================
- NEVER invent any information
- NEVER add fake skills, projects, jobs
- ONLY use data present in resume
- You may rewrite and improve wording ONLY

========================
SUMMARY RULE (MANDATORY)
========================
- ALWAYS generate a professional summary (3–4 lines)
- Use ONLY existing data
- Focus on skills, role, strengths

========================
EXPERIENCE RULE
========================
- Expand each job into 3–5 bullet points
- Do NOT add new roles or companies

========================
PROJECT RULE
========================
- Expand each project into 2–3 bullet points
- Do NOT create new projects

========================
EXTRA SECTIONS RULE (CRITICAL)
========================
Scan resume for ANY sections not in:
skills, experience, projects, education

Examples:
- hobbies
- certifications
- achievements
- extracurricular
- languages

IF FOUND:
- Extract EXACTLY
- DO NOT modify meaning
- DO NOT drop them

Return format:
"extra_sections": [
  {{
    "title": "Section Name",
    "items": ["point1", "point2"]
  }}
]

If none → return []

========================
OUTPUT FORMAT (STRICT JSON)
========================
{{
  "name": "",
  "email": "",
  "phone": "",
  "title": "",
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
      "description": "",
      "points": []
    }}
  ],
  "education": [
    {{
      "degree": "",
      "institution": "",
      "year": ""
    }}
  ],
  "extra_sections": []
}}

========================
RESUME:
{resume_text}

JOB DESCRIPTION:
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
        result = normalize(raw)

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
def create_order(payload: dict):

    resume_id = payload.get("resume_id")

    if resume_id not in resume_store:
        raise HTTPException(status_code=404, detail="Invalid resume_id")

    order = razorpay_client.order.create({
        "amount": PRICE,
        "currency": "INR",
        "payment_capture": 1
    })

    resume_store[resume_id]["order_id"] = order["id"]

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


# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)