fetch("/payments/config/")
.then((result) => { return result.json(); })
.then((data) => {
  // Initialize Stripe.js
  const stripe = Stripe(data.publicKey);

  // new
  // Event handler
  document.querySelector("#payButton").addEventListener("click", () => {
    // Get Checkout Session ID
    fetch("/payments/checkout/" + $("#invoice_id").val() + "/" + Math.round($("#amount").val()) + "/")
    .then((result) => { return result.json(); })
    .then((data) => {
      console.log(data);
      // Redirect to Stripe Checkout
      return stripe.redirectToCheckout({sessionId: data.sessionId})
    })
    .then((res) => {
      console.log(res);
    });
  });
});

document.querySelector("#amount").addEventListener("keypress", function(e) {
  if (e.key === "Enter") {
    document.querySelector("#payButton").click();
  }
});
