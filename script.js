document.addEventListener("DOMContentLoaded", () => {
    // DOM elements for OpenAI and Cohere chats
    const openaiChatBody = document.getElementById("openai-chat-body");
    const cohereChatBody = document.getElementById("cohere-chat-body");

    const openaiUserInput = document.getElementById("openai-user-input");
    const cohereUserInput = document.getElementById("cohere-user-input");

    const openaiSendBtn = document.getElementById("openai-send-btn");
    const cohereSendBtn = document.getElementById("cohere-send-btn");

    const openaiClearBtn = document.getElementById("openai-clear-btn");
    const cohereClearBtn = document.getElementById("cohere-clear-btn");

    // Update the API endpoint URLs to match your Render deployment
    const openaiEndpoint = "https://ai-agents-1yi8.onrender.com/api/openai-chat"; 
    const cohereEndpoint = "https://ai-agents-1yi8.onrender.com/api/cohere-chat"; 

    // Event listeners for send buttons
    openaiSendBtn.addEventListener("click", async () => {
        await handleChat(openaiUserInput, openaiChatBody, openaiEndpoint);
    });

    cohereSendBtn.addEventListener("click", async () => {
        await handleChat(cohereUserInput, cohereChatBody, cohereEndpoint);
    });

    // Event listeners for clear buttons
    openaiClearBtn.addEventListener("click", () => clearChat(openaiChatBody));
    cohereClearBtn.addEventListener("click", () => clearChat(cohereChatBody));

    // Listen for Enter keypress in input fields to send messages
    openaiUserInput.addEventListener("keypress", (event) => {
        if (event.key === "Enter") {
            openaiSendBtn.click();
        }
    });

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
