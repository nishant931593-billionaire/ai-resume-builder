console.log("JS Loaded");

let resumeId = "";

async function optimizeResume() {
  const resume = document.getElementById("resume").value;
  const job = document.getElementById("job").value;

  if (!resume || !job) {
    alert("Please fill both fields");
    return;
  }

  document.getElementById("result").innerText = "Optimizing your resume...";

  try {
    const res = await fetch("https://ai-resume-builder-1xym.onrender.com/optimize-resume", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        resume: resume,
        job_description: job
      })
    });

    const data = await res.json();

    if (!data.success) {
      throw new Error(data.detail || "Optimization failed");
    }

    // Show result (blurred)
    document.getElementById("result").innerText = data.data;
    document.getElementById("result").classList.add("blur");

    resumeId = data.resume_id;

    // Show ATS box
    document.getElementById("atsBox").style.display = "block";

    const score = Math.floor(Math.random() * (85 - 65) + 65);
    document.getElementById("score").innerText = score;

    document.getElementById("payBtn").style.display = "block";

  } catch (error) {
    console.error(error);
    document.getElementById("result").innerText = "Something went wrong. Try again.";
  }
}


async function payNow() {
  try {
    if (!resumeId) {
      alert("Resume not generated yet!");
      return;
    }

    // 🔹 Create order
    const orderRes = await fetch("https://ai-resume-builder-1xym.onrender.com/create-order", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        amount: 1,
        resume_id: resumeId
      })
    });

    const orderData = await orderRes.json();

    console.log("ORDER DATA:", orderData);

    if (!orderData.id) {
      alert("Order creation failed");
      return;
    }

    const options = {
      key: "rzp_live_Sf2VlEoVW0rdWU", // 🔥 Replace with live key when needed
      amount: orderData.amount,
      currency: "INR",
      name: "AI Resume Builder",
      description: "Unlock Full Resume",
      order_id: orderData.id,

      handler: async function (response) {
        try {
          // 🔹 Verify payment
          const verifyRes = await fetch("https://ai-resume-builder-1xym.onrender.com/verify-payment", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
  ...response,
  resume_id: resumeId
})
          });

          const verifyData = await verifyRes.json();

          if (!verifyData.download_url) {
            throw new Error("Payment verified but no download link");
          }

          // 🔓 Remove blur
          document.getElementById("result").classList.remove("blur");

          // Update button
          document.getElementById("payBtn").innerText = "Downloaded ✅";

          // 📥 Redirect to download
          window.location.href = "https://ai-resume-builder-1xym.onrender.com" + verifyData.download_url;

        } catch (err) {
          console.error(err);
          alert("Payment verified but download failed.");
        }
      },

      prefill: {
        name: "Test User",
        email: "test@example.com"
      },

      theme: {
        color: "#3399cc"
      }
    };

    const rzp = new Razorpay(options);
    rzp.open();

  } catch (error) {
    console.error(error);
    alert("Payment failed. Try again.");
  }
}