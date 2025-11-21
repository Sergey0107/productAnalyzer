document.getElementById('analyzeForm').addEventListener('submit', async function(e) {
    e.preventDefault();

    const loadingDiv = document.getElementById('loading');
    const resultsDiv = document.getElementById('results');
    const submitBtn = this.querySelector('button[type="submit"]');

    loadingDiv.classList.remove('hidden');
    resultsDiv.classList.add('hidden');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Анализируем...';

    try {
        const formData = new FormData();
        formData.append('tz_file', document.getElementById('tzFile').files[0]);
        formData.append('passport_file', document.getElementById('passportFile').files[0]);

        const response = await fetch('/api/analyze', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Ошибка при анализе');
        }

        const result = await response.json();
        displayResults(result);

    } catch (error) {
        showError(error.message);
    } finally {
        loadingDiv.classList.add('hidden');
        submitBtn.disabled = false;
        submitBtn.textContent = 'Анализировать';
    }
});

function displayResults(result) {
    const resultsDiv = document.getElementById('results');
    const summaryDiv = document.getElementById('summary');
    const detailsDiv = document.getElementById('details');

    console.log(result)
const rawContent = result.comparison.choices[0].message.content;
const comparison = parseLLMJson(rawContent);

if (!comparison) return;

let summaryHtml = "";

if (comparison.matched === true) {
    summaryHtml = `
        <div style="font-weight: bold; color: green;">
             Изделие соответствует ожидаемым характеристикам
        </div>
        <div style="margin-top: 0.5rem;">
            <strong>Соответствующие критерии:</strong>
            <ul>
                ${(comparison.criteria_success || []).map(c => `<li>${c}</li>`).join("")}
            </ul>
        </div>
    `;
} else {
    summaryHtml = `
        <div style="font-weight: bold; color: red;">
             Изделие НЕ соответствует ожидаемым характеристикам
        </div>

        <div style="margin-top: 0.5rem;">
            <strong>Не соответствуют:</strong>
            <ul>
                ${(comparison.criteria_error || []).map(c => `<li>${c}</li>`).join("")}
            </ul>
        </div>

        <div style="margin-top: 0.5rem;">
            <strong>Соответствуют:</strong>
            <ul>
                ${(comparison.criteria_success || []).map(c => `<li>${c}</li>`).join("")}
            </ul>
        </div>
    `;
}

summaryDiv.innerHTML = summaryHtml;


    let detailsHTML = '<h3>Детали сравнения:</h3>';

for (const [specName, specData] of Object.entries(comparison.details)) {

    let statusClass = "";
    if (specData.status === "matched") statusClass = "matched";
    else if (specData.status === "mismatched") statusClass = "mismatched";
    else if (specData.status === "missing") statusClass = "missing";

    detailsHTML += `
        <div class="spec-item ${statusClass}">
            <div class="spec-name">${specName}</div>
            <div class="spec-message">
                <div><strong>Ожидаемое:</strong> ${specData.expected}</div>
                <div><strong>Фактическое:</strong> ${specData.actual ?? "—"}</div>
                <div><strong>Комментарий:</strong> ${specData.message}</div>
            </div>
        </div>
    `;
}

detailsDiv.innerHTML = detailsHTML;
resultsDiv.classList.remove("hidden");

resultsDiv.scrollIntoView({ behavior: "smooth", block: "nearest" });

}

function showError(message) {
    const resultsDiv = document.getElementById('results');
    const summaryDiv = document.getElementById('summary');
    const detailsDiv = document.getElementById('details');

    summaryDiv.className = 'summary error';
    summaryDiv.textContent = `Ошибка: ${message}`;

    detailsDiv.innerHTML = '';
    resultsDiv.classList.remove('hidden');
    resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function parseLLMJson(content) {
    try {

        return JSON.parse(content);
    } catch (e) {
        console.error("Ошибка разбора JSON:", e, content);
        alert("Ошибка: не удалось распарсить ответ модели");
        return null;
    }
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('загружено');

});
