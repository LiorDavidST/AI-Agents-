document.addEventListener("DOMContentLoaded", () => {
    // Elements
    const lawSelectionContainer = document.getElementById("law-selection");
    const fileInput = document.getElementById("file-input");
    const resultsTableBody = document.getElementById("results-table-body");
    const complianceResultsContainer = document.getElementById("compliance-results");
    const fetchLawTextEndpoint = "/api/fetch-law-text";

    // Fetch predefined laws dynamically
    const fetchLaws = async () => {
        try {
            const response = await fetch("/api/predefined-laws");
            const data = await response.json();
            const laws = data.laws || {};

            lawSelectionContainer.innerHTML = ""; // Clear existing content

            if (Object.keys(laws).length === 0) {
                lawSelectionContainer.innerHTML = "<p>No laws available.</p>";
                return;
            }

            Object.entries(laws).forEach(([lawId, lawTitle]) => {
                const button = document.createElement("button");
                button.textContent = lawTitle;
                button.dataset.lawId = lawId;
                button.className = "law-title-button";
                button.addEventListener("click", () => handleLawSelection(lawId, lawTitle));
                lawSelectionContainer.appendChild(button);
            });
        } catch (error) {
            console.error("Error fetching laws:", error);
            lawSelectionContainer.innerHTML = "<p>Error loading laws. Please try again later.</p>";
        }
    };

    // Handle law selection and fetch law text
    const handleLawSelection = async (lawId, lawTitle) => {
        try {
            const response = await fetch(fetchLawTextEndpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ law_id: lawId }),
            });

            const data = await response.json();
            if (!response.ok) {
                console.error("Error fetching law text:", data.error);
                alert(`Failed to fetch the selected law: ${lawTitle}`);
                return;
            }

            const lawText = data.law_text;
            compareWithUploadedFile(lawText, lawTitle);
        } catch (error) {
            console.error("Error fetching law text:", error);
            alert("Error fetching the law text. Please try again.");
        }
    };

    // Compare uploaded file with law text
    const compareWithUploadedFile = async (lawText, lawTitle) => {
        const file = fileInput.files[0];
        if (!file) {
            alert("Please upload a file first.");
            return;
        }

        const formData = new FormData();
        formData.append("file", file);
        formData.append("law_text", lawText);

        try {
            const response = await fetch("/api/contract-compliance", {
                method: "POST",
                body: formData,
            });

            const data = await response.json();
            if (response.ok) {
                displayComparisonResults(data.result, lawTitle);
            } else {
                alert(data.error || "Error during compliance check.");
            }
        } catch (error) {
            console.error("Error during compliance check:", error);
            alert("Error during compliance check. Please try again.");
        }
    };

    // Display comparison results
    const displayComparisonResults = (results, lawTitle) => {
        resultsTableBody.innerHTML = ""; // Clear existing rows

        results.forEach((result) => {
            const row = document.createElement("tr");
            row.innerHTML = `
                <td>${result.section}</td>
                <td>${result.compliance ? "Compliant" : "Non-Compliant"}</td>
            `;
            resultsTableBody.appendChild(row);
        });

        complianceResultsContainer.querySelector("h2").textContent = `Compliance Results for ${lawTitle}`;
        complianceResultsContainer.classList.remove("hidden");
    };

    // Fetch laws on page load
    fetchLaws();
});
