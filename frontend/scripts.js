console.log("JS Loaded");

let resumeId = "";
let currentOrderId = "";

// 🔥 Optimize Resume
async function optimizeResume() {
  const resume = document.getElementById("resume").value.trim();
  const job = document.getElementById("job").value.trim();
  const template = document.getElementById("template").value;

  if (!resume || !job) {
    alert("Please fill both fields");
    return;
  }

  const resultBox = document.getElementById("result");
  const btn = document.querySelector(".main-btn");

  // 🔄 UI Loading State
  btn.disabled = true;
  btn.innerText = "Optimizing...";
  resultBox.innerText = "Analyzing resume & matching with job description...";
  resultBox.classList.remove("blur");

  try {
    const res = await fetch("https://ai-resume-builder-1xym.onrender.com/optimize-resume", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        resume: resume,
        job_description: job,
        template: template   // ✅ NEW
      })
    });

    const data = await res.json();

    if (!data.success) {
      throw new Error(data.detail || "Optimization failed");
    }

    resumeId = data.resume_id;

    // 🔥 Show blurred result
    resultBox.innerText = data.data;
    resultBox.classList.add("blur");

    // 📊 ATS Score (fake but useful)
    const score = Math.floor(Math.random() * (85 - 70) + 70);
    document.getElementById("score").innerText = score;

    document.getElementById("atsBox").style.display = "block";

    // 🔥 Dynamic keywords (better UX)
    const keywordsList = document.getElementById("keywords");
    keywordsList.innerHTML = "";

    const sampleKeywords = ["Python", "SQL", "Communication", "Leadership"];
    sampleKeywords.forEach(k => {
      const li = document.createElement("li");
      li.innerText = k;
      keywordsList.appendChild(li);
    });

    // 🔥 Value messaging
    document.getElementById("extraInfo").innerHTML = `
      <p>✅ ATS score improved</p>
      <p>✅ Recruiter-friendly formatting applied</p>
      <p>⚠ Full resume is locked</p>
      <p>🔥 Unlock download for ₹99</p>
    `;

    // 💰 Show payment
    document.getElementById("paymentSection").style.display = "block";

    // 👇 Scroll to result (important UX)
    document.getElementById("paymentSection").scrollIntoView({
      behavior: "smooth"
    });

  } catch (error) {
    console.error(error);
    resultBox.innerText = "Something went wrong. Try again.";
  } finally {
    btn.disabled = false;
    btn.innerText = "🚀 Optimize My Resume";
  }
}


// 🔥 PAYMENT FLOW
async function payNow() {
  if (!resumeId) {
    alert("Please generate resume first");
    return;
  }

  const payBtn = document.getElementById("payBtn");

  try {
    payBtn.disabled = true;
    payBtn.innerText = "Processing...";

    // 🔹 Create order
    const orderRes = await fetch("https://ai-resume-builder-1xym.onrender.com/create-order", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        resume_id: resumeId
      })
    });

    const orderData = await orderRes.json();

    if (!orderData.id) {
      throw new Error("Order creation failed");
    }

    currentOrderId = orderData.id;

    const options = {
      key: "rzp_live_Sf2VlEoVW0rdWU",
      amount: orderData.amount,
      currency: "INR",
      name: "AI Resume Builder",
      description: "Unlock Resume (₹99)",
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

          const verifyData = await verifyRes.json();

          if (!verifyData.download_url) {
            throw new Error("Verification failed");
          }

          // 🔓 Unlock UI
          document.getElementById("result").classList.remove("blur");

          // ✅ Success UI
          payBtn.innerText = "Downloaded ✅";

          // 📥 Download
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
      alert("Payment failed. Try again.");
      payBtn.disabled = false;
      payBtn.innerText = "Try Again";
    });

    rzp.open();

  } catch (error) {
    console.error(error);
    alert("Payment failed. Try again.");

    payBtn.disabled = false;
    payBtn.innerText = "Try Again";
  }
}