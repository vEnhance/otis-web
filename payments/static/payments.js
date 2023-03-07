fetch("/payments/config/")
  .then((result) => {
    return result.json();
  })
  .then((data) => {
    // Initialize Stripe.js
    const stripe = Stripe(data.publicKey);

    // new
    // Event handler
    document.querySelector("#payButton").addEventListener("click", () => {
      async () => {
        // Get Checkout Session ID
        let result = await fetch(
          `/payments/checkout/${$("invoice_id").val()}/${Math.round(
            $("#amount").val()
          )}/`
        );

        let data = await result.json();
        console.log(data);

        let res = await stripe.redirectToCheckout({
          sessionId: data.sessionId,
        });
        console.log(res);
      };
    })();
  });

document.querySelector("#amount").addEventListener("keypress", function (e) {
  if (e.key === "Enter") {
    document.querySelector("#payButton").click();
  }
});
