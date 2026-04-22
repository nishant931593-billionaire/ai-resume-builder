console.log("JS Loaded 🚀");

// ==============================
// STATE
// ==============================
let resumeId = null;
let currentData = null;
let isLocked = true;

// ==============================
// SAFE DOM HELPER
// ==============================
const $ = (id) => document.getElementById(id);

// ==============================
// TEMPLATE CLASS
// ==============================
function getTemplateClass(template) {
  switch (template) {
    case "creative": return "template-creative";
    case "minimal": return "template-minimal";
    default: return "template-modern";
  }
}

// ==============================
// PREVIEW RENDERER
// ==============================
function renderResume(data) {
  const template = $("template").value;

  return `
  <div class="resume-preview ${getTemplateClass(template)}">

    <div class="rp-header">
      <h2>${data.name || ""}</h2>
      <p>${data.title || ""}</p>
      <small>${data.email || ""} ${data.phone ? "| " + data.phone : ""}</small>
    </div>

    ${section("Profile", data.summary)}

    ${skills(data.skills)}

    ${experience(data.experience)}

    ${projects(data.projects)}

    ${education(data.education)}

    ${extraSections(data.extra_sections)}

    ${isLocked ? `<div class="preview-lock">🔒 Unlock to download</div>` : ""}

  </div>
  `;
}

// ==============================
// SECTION HELPERS
// ==============================
function section(title, content) {
  if (!content) return "";
  return `
    <div class="rp-section">
      <h3>${title}</h3>
      <p>${content}</p>
    </div>
  `;
}

function skills(skills) {
  if (!skills?.length) return "";
  return `
    <div class="rp-section">
      <h3>Skills</h3>
      <div class="rp-skills">
        ${skills.map(s => `<span>${s}</span>`).join("")}
      </div>
    </div>
  `;
}

function experience(exp) {
  if (!exp?.length) return "";

  return `
    <div class="rp-section">
      <h3>Experience</h3>
      ${exp.map(e => `
        <div class="rp-job">
          <strong>${e.role || ""}</strong> - ${e.company || ""}
          <div class="rp-duration">${e.duration || ""}</div>
          <ul>
            ${(e.points || []).map(p => `<li>${p}</li>`).join("")}
          </ul>
        </div>
      `).join("")}
    </div>
  `;
}

function projects(projects) {
  if (!projects?.length) return "";

  return `
    <div class="rp-section">
      <h3>Projects</h3>
      ${projects.map(p => `
        <div class="rp-job">
          <strong>${p.name || ""}</strong>
          <ul>
            ${(p.points || []).map(pt => `<li>${pt}</li>`).join("")}
          </ul>
        </div>
      `).join("")}
    </div>
  `;
}

function education(edu) {
  if (!edu?.length) return "";

  return `
    <div class="rp-section">
      <h3>Education</h3>
      ${edu.map(e => `
        <p>
          <strong>${e.degree || ""}</strong><br>
          ${e.institution || ""}<br>
          <small>${e.year || ""}</small>
        </p>
      `).join("")}
    </div>
  `;
}

function extraSections(extra) {
  if (!extra?.length) return "";

  return extra.map(sec => `
    <div class="rp-section">
      <h3>${sec.title}</h3>
      <ul>
        ${(sec.items || []).map(i => `<li>${i}</li>`).join("")}
      </ul>
    </div>
  `).join("");
}

// ==============================
// TEMPLATE SWITCH
// ==============================
function previewTemplate() {
  if (!currentData) return;

  $("previewBox").innerHTML = renderResume(currentData);
}

// ==============================
// OPTIMIZE RESUME
// ==============================
async function optimizeResume() {
  const resume = $("resume").value.trim();
  const job = $("job").value.trim();
  const template = $("template").value;

  if (!resume || !job) {
    alert("Please fill both fields");
    return;
  }

  const btn = document.querySelector(".main-btn");

  btn.disabled = true;
  btn.innerText = "Generating...";

  $("previewBox").innerHTML =
    `<p class="loading">⚡ AI is optimizing your resume...</p>`;

  try {
    const res = await fetch(
      "https://ai-resume-builder-1xym.onrender.com/optimize-resume",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resume, job_description: job, template })
      }
    );

    if (!res.ok) throw new Error("Server error");

    const data = await res.json();

    resumeId = data.resume_id;
    currentData = data.data;

    isLocked = true;

    // PREVIEW
    $("previewBox").innerHTML = renderResume(currentData);

    // ATS SCORE (REAL LOGIC LATER)
    const score = calculateATSScore(currentData, job);

    $("atsBox").style.display = "block";
    $("score").innerText = score;

    $("paymentSection").style.display = "block";

    $("paymentSection").scrollIntoView({ behavior: "smooth" });

  } catch (err) {
    console.error(err);
    $("previewBox").innerHTML = "❌ Failed to generate resume";
  } finally {
    btn.disabled = false;
    btn.innerText = "🚀 Generate Resume";
  }
}

// ==============================
// ATS SCORE (BASIC REAL LOGIC)
// ==============================
function calculateATSScore(data, job) {
  const text = JSON.stringify(data).toLowerCase();
  const keywords = job.toLowerCase().split(/\s+/);

  let match = 0;

  keywords.forEach(k => {
    if (text.includes(k)) match++;
  });

  const score = Math.min(100, Math.floor((match / keywords.length) * 100));

  return score || Math.floor(Math.random() * 15 + 75);
}

// ==============================
// PAYMENT
// ==============================
async function payNow() {
  if (!resumeId) {
    alert("Generate resume first");
    return;
  }

  const btn = document.querySelector(".pay-btn");

  try {
    btn.disabled = true;
    btn.innerText = "Processing...";

    const orderRes = await fetch(
      "https://ai-resume-builder-1xym.onrender.com/create-order",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resume_id: resumeId })
      }
    );

    if (!orderRes.ok) throw new Error("Order failed");

    const order = await orderRes.json();

    const rzp = new Razorpay({
      key: "rzp_live_Sf2VlEoVW0rdWU",
      amount: order.amount,
      currency: "INR",
      order_id: order.id,
      name: "AI Resume Builder",
      description: "Premium Resume Download",

      handler: async function (response) {
        try {
          const verify = await fetch(
            "https://ai-resume-builder-1xym.onrender.com/verify-payment",
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                ...response,
                resume_id: resumeId
              })
            }
          );

          if (!verify.ok) throw new Error("Verification failed");

          const data = await verify.json();

          isLocked = false;

          $("previewBox").innerHTML = renderResume(currentData);

          btn.innerText = "Downloaded ✅";

          window.location.href =
            "https://ai-resume-builder-1xym.onrender.com" +
            data.download_url;

        } catch (err) {
          console.error(err);
          alert("Payment succeeded but download failed");
          btn.disabled = false;
          btn.innerText = "Try Again";
        }
      },

      theme: { color: "#4f46e5" }
    });

    rzp.open();

  } catch (err) {
    console.error(err);
    alert("Payment error");

    btn.disabled = false;
    btn.innerText = "Try Again";
  }
}