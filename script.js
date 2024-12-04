document.addEventListener("DOMContentLoaded", () => {
    // Elements
    const signInLink = document.getElementById("sign-in-link");
    const forgotPasswordLink = document.getElementById("forgot-password-link");
    const signInPopup = document.getElementById("sign-in-popup");
    const forgotPasswordPopup = document.getElementById("forgot-password-popup");
    const closeButtons = document.querySelectorAll(".popup-close"); // Select all close buttons
    const signInForm = document.getElementById("sign-in-form");
    const forgotPasswordForm = document.getElementById("forgot-password-form");
    const loginForm = document.getElementById("login-form");
    const feedback = document.getElementById("feedback");
    const chatsContainer = document.getElementById("chats-container");
    const cohereChatBody = document.getElementById("cohere-chat-body");
    const cohereUserInput = document.getElementById("cohere-user-input");
    const cohereSendBtn = document.getElementById("cohere-send-btn");

    let isAuthenticated = false;
    let logoutTimer;

    // Close Popup
    closeButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const popup = button.closest(".popup"); // Find the parent popup
            popup.classList.add("hidden"); // Hide the popup
        });
    });

    // Show Sign-In Popup
    signInLink.addEventListener("click", (e) => {
        e.preventDefault();
        signInPopup.classList.remove("hidden");
    });

    // Handle Sign-In Form Submission
    signInForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = document.getElementById("sign-in-email").value;
        const password = document.getElementById("sign-in-password").value;

        // Simulate sign-in logic
        try {
            const response = await fetch("/api/sign-in", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, password }),
            });
            const data = await response.json();
            if (response.ok) {
                showFeedback("Sign-up successful! Please log in.", false);
                signInPopup.classList.add("hidden");
            } else {
                showFeedback(data.error || "Sign-up failed.", true);
            }
        } catch (err) {
            showFeedback("An error occurred. Please try again.", true);
        }
    });

    // Show Forgot Password Popup
    forgotPasswordLink.addEventListener("click", (e) => {
        e.preventDefault();
        forgotPasswordPopup.classList.remove("hidden");
    });

    // Handle Forgot Password Form Submission
    forgotPasswordForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = document.getElementById("forgot-password-email").value;

        // Simulate forgot password logic
        try {
            const response = await fetch("/api/forgot-password", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email }),
            });
            const data = await response.json();
            if (response.ok) {
                showFeedback("Password sent to your email.", false);
                forgotPasswordPopup.classList.add("hidden");
            } else {
                showFeedback(data.error || "Error sending password.", true);
            }
        } catch (err) {
            showFeedback("An error occurred. Please try again.", true);
        }
    });

    // Handle Login Form Submission
    loginForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = document.getElementById("login-email").value;
        const password = document.getElementById("login-password").value;

        if (!isValidEmail(email)) {
            showFeedback("Please enter a valid email address.", true);
            return;
        }

        if (password.length < 8) {
            showFeedback("Password must be at least 8 characters long.", true);
            return;
        }

        try {
            const response = await fetch("/api/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, password }),
            });

            const data = await response.json();
            if (response.ok) {
                const { token } = data;
                localStorage.setItem("authToken", token);
                isAuthenticated = true;
                showFeedback("Login successful!", false);
                chatsContainer.classList.remove("hidden");
                loginForm.parentElement.classList.add("hidden");
                resetLogoutTimer();
            } else {
                showFeedback(data.error || "Login failed.", true);
            }
        } catch (err) {
            showFeedback("Login failed. Please try again.", true);
        }
    });

    // Handle Chat Messages
    cohereSendBtn.addEventListener("click", async () => {
        if (!isAuthenticated) {
            showFeedback("You must log in to use the chat!", true);
            return;
        }

        const message = cohereUserInput.value.trim();
        if (!message) return;

        const placeholder = document.querySelector(".placeholder");
        if (placeholder) placeholder.remove();

        addMessage("user", message);
        cohereUserInput.value = "";

        try {
            const authToken = localStorage.getItem("authToken");
            const response = await fetch("/api/cohere-chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${authToken}`,
                },
                body: JSON.stringify({ message }),
            });

            const data = await response.json();
            if (response.ok) {
                addMessage("bot", data.reply || "No response.");
            } else {
                addMessage("bot", data.error || "Error connecting to server.");
            }
        } catch (err) {
            addMessage("bot", "Error connecting to server.");
        }
    });

    // Helper Functions
    const addMessage = (sender, message) => {
        const messageDiv = document.createElement("div");
        messageDiv.classList.add("message", sender);
        messageDiv.textContent = message;
        cohereChatBody.appendChild(messageDiv);
        cohereChatBody.scrollTop = cohereChatBody.scrollHeight;
    };

    const showFeedback = (message, isError = false) => {
        feedback.textContent = message;
        feedback.style.background = isError ? "var(--error-color)" : "var(--success-color)";
        feedback.classList.remove("hidden");

        setTimeout(() => {
            feedback.classList.add("hidden");
        }, 3000);
    };

    const isValidEmail = (email) => {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    };

    const resetLogoutTimer = () => {
        clearTimeout(logoutTimer);
        logoutTimer = setTimeout(() => {
            isAuthenticated = false;
            localStorage.removeItem("authToken");
            showFeedback("Session expired. Please log in again.", true);
            location.reload();
        }, 30 * 60 * 1000);
    };
});
