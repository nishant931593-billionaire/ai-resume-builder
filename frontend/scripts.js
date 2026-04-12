let resumeId = "";

async function optimizeResume() {
  const resume = document.getElementById("resume").value;
  const job = document.getElementById("job").value;

  const res = await fetch("http://127.0.0.1:8000/optimize-resume", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      resume: resume,
      job_description: job
    })
  });

  const data = await res.json();

  document.getElementById("result").innerText = data.data;
  resumeId = data.resume_id;

  document.getElementById("payBtn").style.display = "block";
}


async function payNow() {

  // Create order
  const orderRes = await fetch("http://127.0.0.1:8000/create-order", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({amount: 99, resume_id:resumeId})
  });

  const orderData = await orderRes.json();

  const options = {
    key: "rzp_test_ScVNoMEJMY4U5q",
    amount: orderData.amount,
    currency: "INR",
    name: "AI Resume Builder",
    description: "Download Resume",
    order_id: orderData.id,

    handler: async function (response) {

      // verify payment
      await fetch("http://127.0.0.1:8000/verify-payment", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(response)
      });

      // download
      window.location.href = `http://127.0.0.1:8000/download/${resumeId}`;
    }
  };

  const rzp = new Razorpay(options);
  rzp.open();
}