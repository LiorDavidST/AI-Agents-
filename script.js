document.addEventListener("DOMContentLoaded", () => {
    // Elements
    const signInLink = document.getElementById("sign-in-link");
    const forgotPasswordLink = document.getElementById("forgot-password-link");
    const signInPopup = document.getElementById("sign-in-popup");
    const forgotPasswordPopup = document.getElementById("forgot-password-popup");
    const closeButtons = document.querySelectorAll(".popup-close");
    const signInForm = document.getElementById("sign-in-form");
    const forgotPasswordForm = document.getElementById("forgot-password-form");
    const loginForm = document.getElementById("login-form");
    const feedback = document.getElementById("feedback");
    const chatsContainer = document.getElementById("chats-container");
    const cohereChatBody = document.getElementById("cohere-chat-body");
    const cohereUserInput = document.getElementById("cohere-user-input");
    const cohereSendBtn = document.getElementById("cohere-send-btn");
    const fileInput = document.getElementById("file-input");
    const radioCohereChat = document.getElementById("radio-cohere-chat");
    const radioContractCompliance = document.getElementById("radio-contract-compliance");

    let isAuthenticated = false;
    let logoutTimer;

    // Helper to close all open popups
    const closeAllPopups = () => {
        signInPopup.classList.add("hidden");
        forgotPasswordPopup.classList.add("hidden");
    };

    // Close Popup
    closeButtons.forEach((button) => {
        button.addEventListener("click", () => {
            button.closest(".popup").classList.add("hidden");
        });
    });

    // Show Sign-In Popup
    signInLink.addEventListener("click", (e) => {
        e.preventDefault();
        closeAllPopups();
        signInPopup.classList.remove("hidden");
    });

    // Show Forgot Password Popup
    forgotPasswordLink.addEventListener("click", (e) => {
        e.preventDefault();
        closeAllPopups();
        forgotPasswordPopup.classList.remove("hidden");
    });

    // Handle Sign-In Form Submission
    signInForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = document.getElementById("sign-in-email").value;
        const password = document.getElementById("sign-in-password").value;

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

    // Handle Forgot Password Form Submission
    forgotPasswordForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = document.getElementById("forgot-password-email").value;

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
                loginForm.reset();
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

    // Add behavior for Contract Compliance
    radioContractCompliance.addEventListener("change", () => {
        addMessage("bot", "Please upload a contract or sales agreement.");
        fileInput.classList.remove("hidden");
    });

    fileInput.addEventListener("change", () => {
        addMessage(
            "bot",
            "Select one or more laws for compliance check:\n1. Sales Law 1973\n2. Sales Law Investment Assurance 1974"
        );
    });

    cohereSendBtn.addEventListener("click", async () => {
        if (!isAuthenticated) {
            showFeedback("You must log in to use the service!", true);
            return;
        }

        const authToken = localStorage.getItem("authToken");
        if (radioContractCompliance.checked) {
            // Handle Contract Compliance
            const file = fileInput.files[0];
            if (!file) {
                showFeedback("Please upload a file for analysis.", true);
                return;
            }

            const selectedLaws = [];
            if (document.getElementById("law-1").checked) selectedLaws.push(1);
            if (document.getElementById("law-2").checked) selectedLaws.push(2);

            if (selectedLaws.length === 0) {
                addMessage("bot", "Please select at least one law for compliance check.");
                return;
            }

            const formData = new FormData();
            formData.append("file", file);
            formData.append("laws", JSON.stringify(selectedLaws));

            try {
                const response = await fetch("/api/contract-compliance", {
                    method: "POST",
                    headers: { Authorization: `Bearer ${authToken}` },
                    body: formData,
                });
                const data = await response.json();
                if (response.ok) {
                    addMessage("bot", `Compliance Result:\n${data.results.map(r => `${r.law}: ${r.status}`).join("\n")}`);
                } else {
                    addMessage("bot", `Error: ${data.error}`);
                }
            } catch (error) {
                addMessage("bot", "Error while checking contract compliance.");
            }
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
