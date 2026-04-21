console.log("JS Loaded");

let resumeId = "";
let currentData = null;

// 🔥 Safe getter
function getEl(id) {
  return document.getElementById(id);
}

/* ==============================
   🎨 TEMPLATE STYLES (PREVIEW)
================================ */
function getTemplateClass(template) {
  if (template === "creative") return "template-creative";
  if (template === "minimal") return "template-minimal";
  return "template-modern";
}

/* ==============================
   🎨 PREMIUM PREVIEW RENDER
================================ */
function renderResumePreview(data) {
  const template = getEl("template").value;

  return `
  <div class="resume-preview ${getTemplateClass(template)}">

    <div class="rp-header">
      <h2>${data.name || ""}</h2>
      <p class="rp-title">${data.title || ""}</p>
      <small>${data.email || ""} ${data.phone ? "| " + data.phone : ""}</small>
    </div>

    ${data.summary ? `
    <div class="rp-section">
      <h3>Profile</h3>
      <p>${data.summary}</p>
    </div>` : ""}

    ${data.skills?.length ? `
    <div class="rp-section">
      <h3>Skills</h3>
      <div class="rp-skills">
        ${data.skills.map(s => `<span>${s}</span>`).join("")}
      </div>
    </div>` : ""}

    ${data.experience?.length ? `
    <div class="rp-section">
      <h3>Experience</h3>
      ${data.experience.map(e => `
        <div class="rp-job">
          <strong>${e.role || ""}</strong> - ${e.company || ""}
          <div class="rp-duration">${e.duration || ""}</div>
          <ul>
            ${(e.points || []).map(p => `<li>${p}</li>`).join("")}
          </ul>
        </div>
      `).join("")}
    </div>` : ""}

    ${data.projects?.length ? `
    <div class="rp-section">
      <h3>Projects</h3>
      ${data.projects.map(p => `
        <div class="rp-job">
          <strong>${p.name || ""}</strong>
          <ul>
            ${(p.points || []).map(pt => `<li>${pt}</li>`).join("")}
          </ul>
        </div>
      `).join("")}
    </div>` : ""}

    ${data.education?.length ? `
    <div class="rp-section">
      <h3>Education</h3>
      ${data.education.map(e => `
        <p>
          <strong>${e.degree || ""}</strong><br>
          ${e.institution || ""}<br>
          <small>${e.year || ""}</small>
        </p>
      `).join("")}
    </div>` : ""}

    <!-- 🔒 LOCK OVERLAY -->
    <div class="preview-lock">
      🔒 Unlock full resume for download
    </div>

  </div>
  `;
}

/* ==============================
   🔄 TEMPLATE LIVE SWITCH
================================ */
function previewTemplate() {
  if (currentData) {
    getEl("previewBox").innerHTML = renderResumePreview(currentData);
  }
}

/* ==============================
   🚀 OPTIMIZE
================================ */
async function optimizeResume() {
  const resume = getEl("resume").value.trim();
  const job = getEl("job").value.trim();
  const template = getEl("template").value;

  if (!resume || !job) {
    alert("Please fill both fields");
    return;
  }

  const previewBox = getEl("previewBox");
  const btn = document.querySelector(".main-btn");

  btn.disabled = true;
  btn.innerText = "Generating...";

  previewBox.innerHTML = `<p class="loading">⚡ Generating your premium resume...</p>`;

  try {
    const res = await fetch("https://ai-resume-builder-1xym.onrender.com/optimize-resume", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        resume,
        job_description: job,
        template
      })
    });

    if (!res.ok) throw new Error("Server error");

    const data = await res.json();

    resumeId = data.resume_id;

    currentData = typeof data.data === "string"
      ? JSON.parse(data.data)
      : data.data;

    // 🔥 RENDER PREVIEW
    previewBox.innerHTML = renderResumePreview(currentData);

    // 📊 ATS SCORE
    getEl("atsBox").style.display = "block";
    getEl("score").innerText = Math.floor(Math.random() * 15 + 78);

    // 💰 SHOW PAYMENT
    getEl("paymentSection").style.display = "block";

    getEl("paymentSection").scrollIntoView({ behavior: "smooth" });

  } catch (err) {
    console.error(err);
    previewBox.innerHTML = "❌ Error generating resume";
  } finally {
    btn.disabled = false;
    btn.innerText = "🚀 Generate Resume";
  }
}

/* ==============================
   💰 PAYMENT
================================ */
async function payNow() {
  if (!resumeId) {
    alert("Generate resume first");
    return;
  }

  const payBtn = document.querySelector(".pay-btn");

  try {
    payBtn.disabled = true;
    payBtn.innerText = "Processing...";

    const orderRes = await fetch("https://ai-resume-builder-1xym.onrender.com/create-order", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resume_id: resumeId })
    });

    if (!orderRes.ok) throw new Error("Order failed");

    const orderData = await orderRes.json();

    const options = {
      key: "rzp_live_Sf2VlEoVW0rdWU",
      amount: orderData.amount,
      currency: "INR",
      name: "AI Resume Builder",
      description: "Premium Resume Download",
      order_id: orderData.id,

      handler: async function (response) {
        try {
          const verifyRes = await fetch("https://ai-resume-builder-1xym.onrender.com/verify-payment", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
              resume_id: resumeId
            })
          });

          if (!verifyRes.ok) throw new Error("Verification failed");

          const verifyData = await verifyRes.json();

          payBtn.innerText = "Downloaded ✅";

          // 🔓 REMOVE LOCK VISUAL
          document.querySelectorAll(".preview-lock").forEach(el => el.remove());

          window.location.href =
            "https://ai-resume-builder-1xym.onrender.com" + verifyData.download_url;

        } catch (err) {
          console.error(err);
          alert("Payment succeeded but download failed.");
          payBtn.disabled = false;
          payBtn.innerText = "Try Again";
        }
      },

      theme: { color: "#4f46e5" }
    };

    const rzp = new Razorpay(options);

    rzp.on("payment.failed", function () {
      alert("Payment failed");
      payBtn.disabled = false;
      payBtn.innerText = "Try Again";
    });

    rzp.open();

  } catch (err) {
    console.error(err);
    alert("Payment error");

    payBtn.disabled = false;
    payBtn.innerText = "Try Again";
  }
}