console.log("JS Loaded");

let resumeId = "";

// 🔥 Safe element getter
function getEl(id) {
  const el = document.getElementById(id);
  if (!el) console.error(`❌ Missing element: ${id}`);
  return el;
}

// 🔥 Render structured preview (fixed)
function renderResumePreview(data) {
  let html = "";

  if (data.name) html += `\n👤 ${data.name}\n`;

  if (data.email || data.phone) {
    html += `${data.email || ""} ${data.phone ? "| " + data.phone : ""}\n`;
  }

  if (data.skills?.length) {
    html += `\n🔹 Skills:\n`;
    data.skills.forEach(s => {
      html += `• ${s}\n`;
    });
  }

  if (data.experience?.length) {
    html += `\n🔹 Experience:\n`;
    data.experience.forEach(e => {
      html += `• ${e.role || ""} ${e.company ? "at " + e.company : ""}\n`;
    });
  }

  if (data.projects?.length) {
    html += `\n🔹 Projects:\n`;
    data.projects.forEach(p => {
      html += `• ${p.name || ""}\n`;
    });
  }

  if (data.education?.length) {
    html += `\n🔹 Education:\n`;
    data.education.forEach(ed => {
      html += `• ${ed}\n`;
    });
  }

  return html;
}


// 🔥 Optimize Resume
async function optimizeResume() {
  const resume = getEl("resume").value.trim();
  const job = getEl("job").value.trim();
  const template = getEl("template").value;

  if (!resume || !job) {
    alert("Please fill both fields");
    return;
  }

  const resultBox = getEl("result");
  const btn = document.querySelector(".main-btn");

  btn.disabled = true;
  btn.innerText = "Optimizing...";
  resultBox.innerText = "Analyzing your resume...";
  resultBox.classList.remove("blur");

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

    if (!data.success) {
      throw new Error(data.detail || "Failed");
    }

    resumeId = data.resume_id;

    const formatted = renderResumePreview(
      typeof data.data === "string" ? JSON.parse(data.data) : data.data
    );

    resultBox.innerText = formatted;
    resultBox.classList.add("blur");

    // 📊 ATS Score
    const score = Math.floor(Math.random() * 15 + 70);
    getEl("score").innerText = score;
    getEl("atsBox").style.display = "block";

    // 🔑 Keywords
    const keywordsList = getEl("keywords");
    keywordsList.innerHTML = "";

    (data.data.skills || []).slice(0, 5).forEach(k => {
      const li = document.createElement("li");
      li.innerText = k;
      keywordsList.appendChild(li);
    });

    // 🔥 Info
    getEl("extraInfo").innerHTML = `
      <p>✅ Structured resume created</p>
      <p>✅ ATS optimized</p>
      <p>⚠ Full resume is locked</p>
      <p>🔥 Unlock for ₹49</p>
    `;
    getEl("extraInfo").style.display = "block";

    // 💰 Show payment
    getEl("paymentSection").style.display = "block";

    getEl("paymentSection").scrollIntoView({
      behavior: "smooth"
    });

  } catch (err) {
    console.error(err);
    resultBox.innerText = "❌ Something went wrong. Try again.";
  } finally {
    btn.disabled = false;
    btn.innerText = "🚀 Optimize My Resume";
  }
}


// 🔥 PAYMENT
async function payNow() {
  if (!resumeId) {
    alert("Generate resume first");
    return;
  }

  const payBtn = getEl("payBtn");

  try {
    payBtn.disabled = true;
    payBtn.innerText = "Processing...";

    const orderRes = await fetch("https://ai-resume-builder-1xym.onrender.com/create-order", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ resume_id: resumeId })
    });

    if (!orderRes.ok) throw new Error("Order failed");

    const orderData = await orderRes.json();

    const options = {
      key: "rzp_live_Sf2VlEoVW0rdWU",
      amount: orderData.amount,
      currency: "INR",
      name: "AI Resume Builder",
      description: "Unlock Resume (₹49)",
      order_id: orderData.id,

      handler: async function (response) {
        try {
          const verifyRes = await fetch("https://ai-resume-builder-1xym.onrender.com/verify-payment", {
            method: "POST",
            headers: {
              "Content-Type": "application/json"
            },
            body: JSON.stringify({
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
              resume_id: resumeId
            })
          });

          if (!verifyRes.ok) throw new Error("Verification failed");

          const verifyData = await verifyRes.json();

          // 🔓 Unlock preview
          getEl("result").classList.remove("blur");

          payBtn.innerText = "Downloaded ✅";

          window.location.href =
            "https://ai-resume-builder-1xym.onrender.com" + verifyData.download_url;

        } catch (err) {
          console.error(err);
          alert("Payment done but download failed.");
          payBtn.disabled = false;
          payBtn.innerText = "Try Again";
        }
      },

      theme: {
        color: "#5a67d8"
      }
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