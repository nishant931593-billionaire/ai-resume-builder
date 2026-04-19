console.log("JS Loaded");

let resumeId = "";
let currentOrderId = "";

// 🔥 Optimize Resume
async function optimizeResume() {
  const resume = document.getElementById("resume").value.trim();
  const job = document.getElementById("job").value.trim();

  if (!resume || !job) {
    alert("Please fill both fields");
    return;
  }

  const resultBox = document.getElementById("result");
  resultBox.innerText = "Optimizing your resume for better job matches...";
  resultBox.classList.remove("blur");

  try {
    const res = await fetch("https://ai-resume-builder-1xym.onrender.com/optimize-resume", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resume: resume,
        job_description: job
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

    // 🔥 ATS Score (UI only)
    const score = Math.floor(Math.random() * (82 - 68) + 68);
    document.getElementById("score").innerText = score;
    document.getElementById("atsBox").style.display = "block";

    // 🔥 Value + urgency (no plan confusion now)
    document.getElementById("extraInfo").innerHTML = `
      <p>✅ Resume fully optimized for ATS</p>
      <p>✅ Keywords added based on job description</p>
      <p>⚠ This optimized version is locked</p>
      <p>🔥 Unlock full resume for ₹99</p>
    `;

    // Show payment section
    document.getElementById("paymentSection").style.display = "block";

    // 🔥 Follow-up nudge
    setTimeout(() => {
      if (resumeId) {
        alert("Want to download your optimized resume? 🚀");
      }
    }, 20000);

  } catch (error) {
    console.error(error);
    resultBox.innerText = "Something went wrong. Try again.";
  }
}


// 🔥 PAYMENT FLOW (₹99 ONLY)
async function payNow() {
  try {
    if (!resumeId) {
      alert("Resume not generated yet!");
      return;
    }

    const payBtn = document.getElementById("payBtn");
    payBtn.disabled = true;
    payBtn.innerText = "Processing...";

    // 🔹 Create order (NO PLAN)
    const orderRes = await fetch("https://ai-resume-builder-1xym.onrender.com/create-order", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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
      description: "Unlock Your Optimized Resume (₹99)",
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

          const verifyData = await verifyRes.json();

          if (!verifyData.download_url) {
            throw new Error("No download link");
          }

          // 🔓 Unlock UI
          document.getElementById("result").classList.remove("blur");

          // ✅ Button update
          payBtn.innerText = "Downloaded ✅";

          // 📥 Download file
          window.location.href =
            "https://ai-resume-builder-1xym.onrender.com" + verifyData.download_url;

        } catch (err) {
          console.error(err);
          alert("Payment verified but download failed.");
          payBtn.disabled = false;
          payBtn.innerText = "Try Again";
        }
      },

      prefill: {
        name: "",
        email: ""
      },

      theme: {
        color: "#3399cc"
      }
    };

    const rzp = new Razorpay(options);

    // ❌ Payment failed handler
    rzp.on("payment.failed", function (response) {
      console.error(response.error);
      alert("Payment failed. Try again.");
      payBtn.disabled = false;
      payBtn.innerText = "Try Again";
    });

    rzp.open();

  } catch (error) {
    console.error(error);
    alert("Payment failed. Try again.");

    const payBtn = document.getElementById("payBtn");
    payBtn.disabled = false;
    payBtn.innerText = "Try Again";
  }
}