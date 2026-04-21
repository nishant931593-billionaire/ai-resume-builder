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

# ---------------- ENRICH ----------------
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

    # 🔥 Summary
    if not data["summary"]:
        data["summary"] = (
            "Detail-oriented professional with strong analytical and problem-solving skills. "
            "Experienced in collaborating with teams, analyzing data, and delivering "
            "high-quality results in fast-paced environments."
        )

    # 🔥 Skills (min 6)
    if len(data["skills"]) < 6:
        extras = [
            "Communication", "Problem Solving", "Teamwork",
            "Time Management", "Adaptability", "Attention to Detail"
        ]
        for s in extras:
            if s not in data["skills"]:
                data["skills"].append(s)
            if len(data["skills"]) >= 6:
                break

    # 🔥 Experience (NO repetition)
    DEFAULT_EXP_POINTS = [
        "Analyzed data to identify trends and support business decisions",
        "Prepared reports and dashboards to present insights clearly",
        "Collaborated with cross-functional teams to deliver tasks efficiently",
        "Cleaned and structured data to improve accuracy and usability"
    ]

    for exp in data["experience"]:
        exp.setdefault("role", "")
        exp.setdefault("company", "")
        exp.setdefault("duration", "")
        exp.setdefault("points", [])

        i = 0
        while len(exp["points"]) < 4 and i < len(DEFAULT_EXP_POINTS):
            if DEFAULT_EXP_POINTS[i] not in exp["points"]:
                exp["points"].append(DEFAULT_EXP_POINTS[i])
            i += 1

    # 🔥 Projects
    DEFAULT_PROJECT_POINTS = [
        "Designed and developed features aligned with project requirements",
        "Implemented structured solutions ensuring performance and usability",
        "Tested and refined functionality to improve overall experience"
    ]

    for proj in data["projects"]:
        proj.setdefault("name", "")
        proj.setdefault("description", "")
        proj.setdefault("points", [])

        i = 0
        while len(proj["points"]) < 3 and i < len(DEFAULT_PROJECT_POINTS):
            if DEFAULT_PROJECT_POINTS[i] not in proj["points"]:
                proj["points"].append(DEFAULT_PROJECT_POINTS[i])
            i += 1

    return data

# ---------------- AI ----------------
def generate_resume(resume_text, job_description):
    prompt = f"""
You are a professional resume writer.

STRICT:
- Do NOT add fake experience or projects
- Only improve existing content

GOAL:
Make the resume PREMIUM and HUMAN-WRITTEN

RULES:
- Add title
- Add 3–4 line summary
- Experience → 3–5 UNIQUE bullet points
- Projects → 2–3 bullet points
- Avoid repetition

OUTPUT JSON:

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
  ]
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
