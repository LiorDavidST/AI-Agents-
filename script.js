document.addEventListener("DOMContentLoaded", () => {
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

    const closeAllPopups = () => {
        signInPopup.classList.add("hidden");
        forgotPasswordPopup.classList.add("hidden");
    };

    closeButtons.forEach((button) => {
        button.addEventListener("click", () => {
            button.closest(".popup").classList.add("hidden");
        });
    });

    signInLink.addEventListener("click", (e) => {
        e.preventDefault();
        closeAllPopups();
        signInPopup.classList.remove("hidden");
    });

    cohereUserInput.addEventListener("input", function () {
        this.style.height = "auto";
        this.style.height = `${this.scrollHeight}px`;
    });

    forgotPasswordLink.addEventListener("click", (e) => {
        e.preventDefault();
        closeAllPopups();
        forgotPasswordPopup.classList.remove("hidden");
    });

    signInForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = document.getElementById("sign-in-email").value;
        const password = document.getElementById("sign-in-password").value;
        // המשך קוד...
    });

    forgotPasswordForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = document.getElementById("forgot-password-email").value;
        // המשך קוד...
    });

    loginForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = document.getElementById("login-email").value;
        const password = document.getElementById("login-password").value;
        // המשך קוד...
    });

    cohereSendBtn.addEventListener("click", async () => {
        if (!isAuthenticated) {
            showFeedback("You must log in to use the service!", true);
            return;
        }

        const authToken = localStorage.getItem("authToken");

        if (radioCohereChat.checked) {
            const message = cohereUserInput.value.trim();
            if (!message) {
                showFeedback("Message cannot be empty!", true);
                return;
            }

            addMessage("user", message);
            cohereUserInput.value = "";
            cohereUserInput.style.height = "auto";

            try {
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
                addMessage("bot", "Error connecting to server. Please try again later.");
            }
        }
    });

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
