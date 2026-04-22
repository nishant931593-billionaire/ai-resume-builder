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
PRICE = 100

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
    except Exception as e:
        print("❌ JSON ERROR:", e)
        return {}

# ---------------- NORMALIZE (CRITICAL FIX) ----------------
def normalize(data):

    def safe_list(x):
        return x if isinstance(x, list) else []

    def safe_str(x):
        return str(x) if x else ""

    # -------- EXPERIENCE --------
    def fix_experience(exp_list):
        fixed = []
        for e in safe_list(exp_list):
            fixed.append({
                "role": safe_str(e.get("role") or e.get("title")),
                "company": safe_str(e.get("company")),
                "duration": safe_str(e.get("duration") or e.get("dates")),
                "points": safe_list(e.get("points") or e.get("responsibilities"))
            })
        return fixed

    # -------- PROJECTS --------
    def fix_projects(proj_list):
        fixed = []
        for p in safe_list(proj_list):
            fixed.append({
                "name": safe_str(p.get("name") or p.get("title")),
                "description": safe_str(p.get("description")),
                "points": safe_list(p.get("points"))
            })
        return fixed

    # -------- SKILLS FIX (IMPORTANT) --------
    def fix_skills(skills):
        fixed = []
        for s in safe_list(skills):
            if isinstance(s, str):
                fixed.append(s)
            elif isinstance(s, dict):
                name = s.get("name")
                details = s.get("details", [])
                if name:
                    if details:
                        fixed.append(f"{name}: {', '.join(details)}")
                    else:
                        fixed.append(name)
        return fixed

    # -------- EXTRA SECTIONS FIX --------
    def fix_extra(raw_extra):
        fixed = []
        for sec in safe_list(raw_extra):

            # already correct
            if isinstance(sec, dict) and "title" in sec and "items" in sec:
                fixed.append({
                    "title": safe_str(sec.get("title")),
                    "items": safe_list(sec.get("items"))
                })

            # convert wrong format
            elif isinstance(sec, dict):
                for key, value in sec.items():
                    fixed.append({
                        "title": safe_str(key).capitalize(),
                        "items": safe_list(value)
                    })

        return fixed

    return {
        "name": safe_str(data.get("name")),
        "email": safe_str(data.get("email")),
        "phone": safe_str(data.get("phone")),
        "title": safe_str(data.get("title")),
        "summary": safe_str(data.get("summary")),

        "skills": fix_skills(data.get("skills")),
        "experience": fix_experience(data.get("experience")),
        "projects": fix_projects(data.get("projects")),
        "education": safe_list(data.get("education")),
        "extra_sections": fix_extra(data.get("extra_sections")),
    }

# ---------------- AI ENGINE ----------------
def generate_resume(resume_text, job_description):

    prompt = f"""
You are a STRICT resume optimization engine.

RULES:
- NEVER invent fake experience
- ONLY enhance given data
- If missing experience → describe learning, not fake jobs
- If missing projects → create realistic practice projects
- Always return clean JSON

STRUCTURE:
experience = role, company, duration, points[]
projects = name, description, points[]
extra_sections = title, items[]

OUTPUT:
{{
  "name": "",
  "email": "",
  "phone": "",
  "title": "",
  "summary": "",
  "skills": [],
  "experience": [],
  "projects": [],
  "education": [],
  "extra_sections": []
}}

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

        print("🔥 FINAL DATA:", result)

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
        print("❌ ERROR:", e)
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

    try:
        print("📄 PDF DATA:", data)

        template_path = f"templates/{template_name}.html"

        if not os.path.exists(template_path):
            raise HTTPException(status_code=500, detail="Template not found")

        with open(template_path, "r", encoding="utf-8") as f:
            template = Template(f.read())

        html = template.render(**data)

        file_path = f"generated/{uuid.uuid4().hex}.pdf"
        HTML(string=html).write_pdf(file_path)

        resume_store[resume_id]["file"] = file_path

        return file_path

    except Exception as e:
        print("❌ PDF ERROR:", e)
        raise HTTPException(status_code=500, detail="PDF generation failed")

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