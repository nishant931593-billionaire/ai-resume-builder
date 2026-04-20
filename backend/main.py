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

# ---------------- SAFE JSON PARSER ----------------
def safe_json(text: str):
    try:
        text = text.strip()

        # remove markdown
        if "```" in text:
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text

        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1:
            return {}

        return json.loads(text[start:end+1])

    except Exception as e:
        print("JSON ERROR:", e)
        return {}

# ---------------- OPTIMIZE RESUME ----------------
@app.post("/optimize-resume")
def optimize_resume(data: ResumeRequest):
    try:
        prompt = f"""
You are a professional ATS resume optimizer.

Your task is to IMPROVE and REWRITE the resume to be ATS-friendly and tailored to the job description — WITHOUT adding or inventing ANY new information.

CORE RULE:
- You MUST ONLY use information explicitly present in the resume.
- DO NOT fabricate, assume, or create any new experience, projects, achievements, or metrics.
- If something is not mentioned, DO NOT add it.

ALLOWED ACTIONS:
- Rephrase and improve wording
- Make bullet points more professional and impactful
- Add relevant ATS keywords from the job description (ONLY if they match existing experience/skills)
- Improve clarity, grammar, and structure
- Expand descriptions ONLY using existing facts

STRICT RESTRICTIONS:

1. NO FAKE CONTENT:
   - Do NOT create new companies, roles, projects, or achievements
   - Do NOT add numbers, metrics, or results unless already mentioned
   - Do NOT assume responsibilities

2. EXPERIENCE:
   - Keep all roles strictly based on input
   - You may rewrite bullet points for clarity and impact
   - Do NOT exceed what is logically supported by the original resume

3. PROJECTS:
   - Only include projects that are explicitly mentioned
   - Do NOT create new projects under any condition

4. SKILLS:
   - Extract and reorganize existing skills
   - You may reorder and group them
   - Do NOT add new skills

5. EDUCATION:
   - Keep factual and unchanged except formatting

6. KEYWORD OPTIMIZATION:
   - Integrate relevant keywords from the job description ONLY if they align with existing content
   - Do NOT insert keywords that are not supported by the resume

7. IF DATA IS MISSING:
   - Leave section empty OR keep minimal
   - DO NOT fill with assumptions

OUTPUT FORMAT:
Return ONLY valid JSON:

{{
  "name": "",
  "email": "",
  "phone": "",
  "skills": [],
  "experience": [],
  "projects": [],
  "education": []
}}

INPUT RESUME:
{data.resume}

JOB DESCRIPTION:
{data.job_description}
"""
   

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},  # 🔥 IMPORTANT FIX
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.choices[0].message.content
        parsed = safe_json(content)

        # 🔥 NEVER CRASH
        if not parsed:
            parsed = {
                "name": "",
                "email": "",
                "phone": "",
                "summary": "",
                "skills": [],
                "experience": [],
                "projects": [],
                "education": []
            }

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