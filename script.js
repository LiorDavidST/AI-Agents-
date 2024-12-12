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
    const lawSelectionContainer = document.createElement("div");
    
    let isAuthenticated = false;
    let logoutTimer;

    // Predefined laws fetched dynamically from the backend
    let laws = {};

    async function fetchLaws() {
        try {
            const response = await fetch('/api/predefined-laws');
            const data = await response.json();
            if (response.ok && data.laws) {
                laws = data.laws;
            } else {
                console.error("Failed to fetch laws", data);
            }
        } catch (error) {
            console.error("Error fetching laws:", error);
        }
    }

    async function populateLawOptions() {
        await fetchLaws();
        lawSelectionContainer.innerHTML = "<h3>Select Laws to Check:</h3>";
        Object.keys(laws).forEach((lawId) => {
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.id = `law-${lawId}`;
            checkbox.value = lawId;
            const label = document.createElement("label");
            label.htmlFor = `law-${lawId}`;
            label.textContent = laws[lawId];
            lawSelectionContainer.appendChild(checkbox);
            lawSelectionContainer.appendChild(label);
            lawSelectionContainer.appendChild(document.createElement("br"));
        });
        fileInput.parentElement.appendChild(lawSelectionContainer);
    }

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

    // Handle Contract Compliance Submission
    cohereSendBtn.addEventListener("click", async () => {
        if (!isAuthenticated) {
            showFeedback("You must log in to use the service!", true);
            return;
        }

        const authToken = localStorage.getItem("authToken");

        if (radioContractCompliance.checked) {
            const file = fileInput.files[0];
            if (!file) {
                showFeedback("Please upload a file for analysis.", true);
                return;
            }

            const selectedLaws = Array.from(
                lawSelectionContainer.querySelectorAll("input[type=checkbox]:checked")
            ).map((checkbox) => checkbox.value);

            if (!selectedLaws.length) {
                showFeedback("Please select at least one law for analysis.", true);
                return;
            }

            const formData = new FormData();
            formData.append("file", file);
            selectedLaws.forEach((law) => formData.append("selected_laws", law));

            try {
                const response = await fetch("/api/contract-compliance", {
                    method: "POST",
                    headers: {
                        Authorization: `Bearer ${authToken}`,
                    },
                    body: formData,
                });

                const data = await response.json();
                console.log("Server Response:", data);
                if (response.ok) {
                    if (Array.isArray(data.result)) {
                        data.result.forEach((res) => {
                            addMessage(
                                "bot",
                                `Law: ${laws[res.law_id]} - Status: ${res.status} - ${res.details || "No details"}`
                            );
                        });
                    } else {
                        addMessage("bot", `Unexpected response format: ${JSON.stringify(data.result)}`);
                    }
                } else {
                    addMessage("bot", data.error || "Error connecting to server.");
                }
            } catch (err) {
                addMessage("bot", "Error connecting to server.");
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

    // Initialize UI with laws on load
    populateLawOptions();
});
