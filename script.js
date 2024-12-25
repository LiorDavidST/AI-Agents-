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
    const lawSelectionContainer = document.getElementById("law-selection");
    const resultsTableBody = document.getElementById("results-table-body");
    const complianceResultsContainer = document.getElementById("compliance-results");
    const contractComplianceSection = document.getElementById("contract-compliance-section");

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

    // Fetch predefined laws dynamically
const fetchLaws = async () => {
    try {
        const response = await fetch("/api/predefined-laws");
        const data = await response.json();
        const laws = data.laws; // Ensure it matches the backend structure

        lawSelectionContainer.innerHTML = ""; // Clear existing content

        if (laws && typeof laws === "object") {
            Object.entries(laws).forEach(([lawId, lawTitle]) => {
                // Ensure lawTitle is a string
                if (typeof lawTitle === "string") {
                    const checkbox = document.createElement("input");
                    checkbox.type = "checkbox";
                    checkbox.id = `law-${lawId}`;
                    checkbox.value = lawId;

                    const label = document.createElement("label");
                    label.setAttribute("for", `law-${lawId}`);
                    label.textContent = lawTitle;

                    const container = document.createElement("div");
                    container.className = "law-item";
                    container.appendChild(checkbox);
                    container.appendChild(label);

                    lawSelectionContainer.appendChild(container);
                } else {
                    console.error(`Invalid law title for ID ${lawId}:`, lawTitle);
                }
            });
        } else {
            console.error("Laws data is not valid:", laws);
            lawSelectionContainer.innerHTML = "<p>No laws available.</p>";
        }
    } catch (error) {
        console.error("Error fetching laws:", error);
        lawSelectionContainer.innerHTML = "<p>Error loading laws. Please try again later.</p>";
    }
};

// Ensure the function is invoked
fetchLaws();



    // Toggle Contract Compliance Section
    radioCohereChat.addEventListener("change", () => {
        contractComplianceSection.classList.add("hidden");
    });

    radioContractCompliance.addEventListener("change", () => {
        contractComplianceSection.classList.remove("hidden");
        fetchLaws(); // Fetch laws when this section is made visible
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

    // Update Compliance Results
    const updateComplianceResults = (results) => {
        resultsTableBody.innerHTML = ""; // Clear existing rows

        results.forEach((result) => {
            const row = document.createElement("tr");
            row.innerHTML = `
                <td>${result.law_id}</td>
                <td>${result.law_title || "Unknown Law"}</td>
                <td>${result.status}</td>
                <td>${result.details}</td>
            `;
            resultsTableBody.appendChild(row);
        });

        complianceResultsContainer.classList.remove("hidden");
    };

    // Handle Contract Compliance
    cohereSendBtn.addEventListener("click", async () => {
        if (!isAuthenticated) {
            showFeedback("You must log in to use the service!", true);
            return;
        }

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
                        Authorization: `Bearer ${localStorage.getItem("authToken")}`,
                    },
                    body: formData,
                });

                const data = await response.json();
                if (response.ok && Array.isArray(data.result)) {
                    updateComplianceResults(data.result);
                } else {
                    showFeedback(data.error || "Unexpected server error.", true);
                }
            } catch (error) {
                showFeedback("Error connecting to server.", true);
            }
        }
    });

    // Show Feedback
    const showFeedback = (message, isError = false) => {
        feedback.textContent = message;
        feedback.style.background = isError ? "var(--error-color)" : "var(--success-color)";
        feedback.classList.remove("hidden");

        setTimeout(() => {
            feedback.classList.add("hidden");
        }, 3000);
    };

    // Reset Logout Timer
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
