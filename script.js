document.addEventListener("DOMContentLoaded", () => {
    // Login and container elements
    const loginForm = document.getElementById("login-form");
    const chatsContainer = document.getElementById("chats-container");
    const loginContainer = document.getElementById("login-container");

    // Hide OpenAI chat container
    const openaiChat = document.getElementById("openai-chat");
    if (openaiChat) {
        openaiChat.style.display = "none";
    }

    // Login form submit handler
    loginForm.addEventListener("submit", (e) => {
        e.preventDefault();
        // Simulate login success
        loginContainer.classList.add("hidden");
        chatsContainer.classList.remove("hidden");
    });

    // Cohere chat elements
    const cohereChatBody = document.getElementById("cohere-chat-body");
    const cohereUserInput = document.getElementById("cohere-user-input");
    const cohereSendBtn = document.getElementById("cohere-send-btn");
    const cohereClearBtn = document.getElementById("cohere-clear-btn");

    // Cohere API endpoint
    const cohereEndpoint = "https://ai-agents-1yi8.onrender.com/api/cohere-chat";

    // Event listeners for Cohere chat
    cohereSendBtn.addEventListener("click", async () => {
        await handleChat(cohereUserInput, cohereChatBody, cohereEndpoint);
    });

    cohereClearBtn.addEventListener("click", () => clearChat(cohereChatBody));

    cohereUserInput.addEventListener("keypress", (event) => {
        if (event.key === "Enter") {
            cohereSendBtn.click();
        }
    });

    /**
     * Handles sending messages to the chat endpoint.
     * @param {HTMLElement} inputField - The input field for user messages.
     * @param {HTMLElement} chatBody - The container for chat messages.
     * @param {string} endpoint - The API endpoint for chat processing.
     */
    async function handleChat(inputField, chatBody, endpoint) {
        const message = inputField.value.trim();

        if (!message) {
            addMessage(chatBody, "bot", "⚠️ Please enter a message.");
            return;
        }

        addMessage(chatBody, "user", message);
        inputField.value = "";

        try {
            const response = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message }),
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Server error: ${response.status} - ${errorText}`);
            }

            const data = await response.json();
            const botReply = data.reply || "⚠️ No response received.";
            addMessage(chatBody, "bot", botReply);
        } catch (error) {
            console.error("Error:", error.message);
            addMessage(chatBody, "bot", `⚠️ Error: ${error.message}`);
        }
    }

    /**
     * Adds a message to the chat body.
     * @param {HTMLElement} chatBody - The container for chat messages.
     * @param {string} sender - The sender of the message ("user" or "bot").
     * @param {string} text - The text content of the message.
     */
    function addMessage(chatBody, sender, text) {
        const messageDiv = document.createElement("div");
        messageDiv.classList.add("message", sender);
        messageDiv.textContent = text;
        chatBody.appendChild(messageDiv);
        chatBody.scrollTop = chatBody.scrollHeight; // Scroll to the bottom
    }

    /**
     * Clears all messages from the chat body.
     * @param {HTMLElement} chatBody - The container for chat messages.
     */
    function clearChat(chatBody) {
        chatBody.innerHTML = "";
        addMessage(chatBody, "bot", "Chat cleared. Start a new conversation!");
    }
});
