document.addEventListener("DOMContentLoaded", () => {
    // Login and Sign-in Buttons
    const loginBtn = document.getElementById("login-btn");
    const signInBtn = document.getElementById("sign-in-btn");

    // Containers
    const loginContainer = document.getElementById("login-container");
    const signInContainer = document.getElementById("sign-in-container");
    const chatsContainer = document.getElementById("chats-container");

    // Forms
    const loginForm = document.getElementById("login-form");
    const signInForm = document.getElementById("sign-in-form");

    // Chat Elements
    const cohereChatBody = document.getElementById("cohere-chat-body");
    const cohereUserInput = document.getElementById("cohere-user-input");
    const cohereSendBtn = document.getElementById("cohere-send-btn");

    // Feedback and Spinner Elements
    const feedback = document.getElementById("feedback");
    const loadingSpinner = document.getElementById("loading-spinner");

    let isAuthenticated = false; // Tracks authentication status
    let logoutTimer; // Timer for session timeout

    // Show/Hide Login and Sign-In Forms
    loginBtn.addEventListener("click", () => {
        toggleVisibility(loginContainer);
    });

    signInBtn.addEventListener("click", () => {
        toggleVisibility(signInContainer);
    });

    // Handle Sign-In
    signInForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = document.getElementById("sign-in-email").value;
        const password = document.getElementById("sign-in-password").value;

        // Validate inputs
        if (!isValidEmail(email)) {
            showFeedback("Please enter a valid email address.", true);
            return;
        }

        if (password.length < 8) {
            showFeedback("Password must be at least 8 characters long.", true);
            return;
        }

        showLoading(true);
        toggleButtonState(signInForm.querySelector("button"), true);

        try {
            const response = await fetch("/api/sign-in", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, password }),
            });

            const data = await response.json();
            if (response.ok) {
                showFeedback("Sign-in successful! Please log in.", false);
                signInContainer.classList.add("hidden");
            } else {
                showFeedback(data.error, true);
            }
        } catch (err) {
            console.error("Sign-in failed:", err);
            showFeedback("Sign-in failed. Please try again.", true);
        } finally {
            showLoading(false);
            toggleButtonState(signInForm.querySelector("button"), false);
        }
    });

    // Handle Login
    loginForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = document.getElementById("login-email").value;
        const password = document.getElementById("login-password").value;

        // Validate inputs
        if (!isValidEmail(email)) {
            showFeedback("Please enter a valid email address.", true);
            return;
        }

        if (password.length < 8) {
            showFeedback("Password must be at least 8 characters long.", true);
            return;
        }

        showLoading(true);
        toggleButtonState(loginForm.querySelector("button"), true);

        try {
            const response = await fetch("/api/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, password }),
            });

            const data = await response.json();
            if (response.ok) {
                const { token } = data; // Assuming the backend returns a token
                localStorage.setItem("authToken", token);
                isAuthenticated = true;
                showFeedback("Login successful!", false);
                loginContainer.classList.add("hidden");
                chatsContainer.classList.remove("hidden");
                resetLogoutTimer();
            } else {
                showFeedback(data.error, true);
            }
        } catch (err) {
            console.error("Login failed:", err);
            showFeedback("Login failed. Please try again.", true);
        } finally {
            showLoading(false);
            toggleButtonState(loginForm.querySelector("button"), false);
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
        if (placeholder) placeholder.remove(); // Remove the placeholder for the first message

        addMessage("user", message);
        cohereUserInput.value = "";

        showLoading(true);

        try {
            const authToken = localStorage.getItem("authToken"); // Retrieve the token
            const response = await fetch("/api/cohere-chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${authToken}`, // Send the token in the Authorization header
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
            console.error("Chat error:", err);
            addMessage("bot", "Error connecting to server.");
        } finally {
            showLoading(false);
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

    const showLoading = (show) => {
        if (show) {
            loadingSpinner.classList.remove("hidden");
        } else {
            loadingSpinner.classList.add("hidden");
        }
    };

    const toggleButtonState = (button, disable) => {
        button.disabled = disable;
    };

    const toggleVisibility = (element) => {
        element.classList.toggle("hidden");
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
            location.reload(); // Optionally reload the page
        }, 30 * 60 * 1000); // 30 minutes
    };

    const authToken = localStorage.getItem("authToken");
    if (authToken) {
        isAuthenticated = true;
        chatsContainer.classList.remove("hidden");
        resetLogoutTimer();
    }

    document.addEventListener("mousemove", resetLogoutTimer);
    document.addEventListener("keydown", resetLogoutTimer);
});
