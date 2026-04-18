console.log("JS Loaded");

let resumeId = "";

async function optimizeResume() {
  const resume = document.getElementById("resume").value;
  const job = document.getElementById("job").value;

  if (!resume || !job) {
    alert("Please fill both fields");
    return;
  }

  // 🔄 Loading state
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

    // Show result (blurred initially)
    document.getElementById("result").innerText = data.data;
    document.getElementById("result").classList.add("blur");

    resumeId = data.resume_id;

    // 🔥 Show ATS box
    document.getElementById("atsBox").style.display = "block";

    // (Fake dynamic score for now)
    const score = Math.floor(Math.random() * (85 - 65) + 65);
    document.getElementById("score").innerText = score;

    // 🔥 Show pay button
    document.getElementById("payBtn").style.display = "block";

  } catch (error) {
    console.error(error);
    document.getElementById("result").innerText = "Something went wrong. Try again.";
  }
}


async function payNow() {

  try {
    // Create order
    const orderRes = await fetch("https://ai-resume-builder-1xym.onrender.com/create-order", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        amount: 99,
        resume_id: resumeId
      })
    });

    const orderData = await orderRes.json();
    console.log("ORDER DATA:", orderData);
    console.log("ORDER ID:", orderData.id);
    console.log("AMOUNT:", orderData.amount);
    console.log("KEY USED:", "rzp_test_Sexsv6JxTPLkar")

    const options = {
      key: "rzp_test_Sexsv6JxTPLkar",
      amount: orderData.amount,
      currency: "INR",
      name: "AI Resume Builder",
      description: "Unlock Full Resume",
      order_id: orderData.id,

      handler: async function (response) {

        // ✅ VERIFY PAYMENT (FIXED URL)
        await fetch("https://ai-resume-builder-1xym.onrender.com/verify-payment", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(response)
        });

        // 🔓 Remove blur after payment
        document.getElementById("result").classList.remove("blur");

        // Optional: change button text
        document.getElementById("payBtn").innerText = "Downloaded ✅";

        // 📥 Download file
        window.location.href = `https://ai-resume-builder-1xym.onrender.com/download/${resumeId}`;
      }
    };

    const rzp = new Razorpay(options);
    rzp.open();

  } catch (error) {
    console.error(error);
    alert("Payment failed. Try again.");
  }
}