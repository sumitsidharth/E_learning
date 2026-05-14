/** Eduverse Stripe Checkout Module */

const EduverseStripe = (function() {
    let stripeInstance = null;

    /**
     * Initialize Stripe instance if available.
     * Requires the Stripe.js script to be loaded.
     */
    function initStripe() {
        if (typeof Stripe !== 'undefined') {
            // Public key would normally be passed here if required, though
            // redirect-to-checkout doesn't always need it if the URL is provided.
            stripeInstance = true;
        }
    }

    /**
     * Start the checkout redirect flow.
     * @param {string} checkoutUrl - The URL of the Stripe Checkout Session.
     * @param {string} noteId - The ID of the note being purchased.
     * @param {string} csrfToken - The CSRF token for the request.
     */
    function checkout(checkoutUrl, noteId, csrfToken) {
        fetch(checkoutUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': csrfToken
            },
            body: `note_id=${noteId}`
        })
        .then(response => response.json())
        .then(session => {
            if (session.url) {
                window.location.href = session.url;
            } else {
                alert(session.error || 'Checkout initialization failed.');
            }
        })
        .catch(error => {
            console.error('Stripe Checkout Error:', error);
            alert('A network error occurred. Please try again.');
        });
    }

    return {
        init: initStripe,
        checkout: checkout
    };
})();

// Auto-initialize on load
document.addEventListener('DOMContentLoaded', function() {
    EduverseStripe.init();

    // Delegate click events for checkout buttons
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('.js-stripe-checkout');
        if (btn) {
            e.preventDefault();
            const url = btn.getAttribute('data-url');
            const noteId = btn.getAttribute('data-note-id');
            const csrf = btn.getAttribute('data-csrf');
            
            if (url && noteId && csrf) {
                EduverseStripe.checkout(url, noteId, csrf);
            }
        }
    });
});
