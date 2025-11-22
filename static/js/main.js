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
        formData.append('comparison_mode', document.getElementById('comparisonMode').value);

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

    console.log(result);

    if (!result.comparison) {
        showError('Отсутствуют данные сравнения');
        return;
    }

    if (!result.comparison.choices || !result.comparison.choices[0]) {
        showError('Некорректная структура данных сравнения');
        return;
    }

    const rawContent = result.comparison.choices[0].message.content;
    const comparison = parseLLMJson(rawContent);

    if (!comparison) return;

let summaryHtml = "";

if (comparison.matched === true) {
    summaryHtml = `<div class="summary-status matched">✓ Изделие соответствует ожидаемым характеристикам</div>`;
} else {
    summaryHtml = `<div class="summary-status mismatched">✗ Изделие НЕ соответствует ожидаемым характеристикам</div>`;
}

summaryDiv.innerHTML = summaryHtml;

let detailsHTML = `
    <table class="comparison-table">
        <thead>
            <tr>
                <th>Характеристика</th>
                <th>Ожидаемое (ТЗ)</th>
                <th>Фактическое (Паспорт)</th>
                <th>Статус</th>
                <th>Комментарий</th>
            </tr>
        </thead>
        <tbody>
`;

for (const [specName, specData] of Object.entries(comparison.details)) {
    let statusClass = "";
    let statusText = "";

    if (specData.status === "matched") {
        statusClass = "matched";
        statusText = "✓ Соответствует";
    } else if (specData.status === "mismatched") {
        statusClass = "mismatched";
        statusText = "✗ Не соответствует";
    } else if (specData.status === "missing") {
        statusClass = "missing";
        statusText = "− Отсутствует";
    }

    detailsHTML += `
        <tr class="${statusClass}">
            <td class="spec-name">${specName}</td>
            <td>${specData.expected}</td>
            <td>${specData.actual ?? "—"}</td>
            <td class="status-cell">${statusText}</td>
            <td class="message-cell">${specData.message}</td>
        </tr>
    `;
}

detailsHTML += `
        </tbody>
    </table>
`;

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
