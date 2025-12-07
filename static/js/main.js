document.getElementById('analyzeForm').addEventListener('submit', async function(e) {
    e.preventDefault();

    const startTime = performance.now();
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
        const endTime = performance.now();
        const totalTime = ((endTime - startTime) / 1000).toFixed(2);

        result.totalTime = totalTime;
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
    console.log("RAW RESULT:", result);

    const resultsDiv = document.getElementById('results');
    const summaryDiv = document.getElementById('summary');
    const detailsDiv = document.getElementById('details');
    const sourceDataDiv = document.getElementById('sourceData');


    const response = result?.comparison?.response;

    if (!response) {
        showError("Отсутствуют данные LLM-ответа (result.comparison.response=null)");
        return;
    }

    const choices = response.choices;
    if (!choices || !choices[0]) {
        showError("Некорректная структура ответа LLM (choices пустой)");
        return;
    }

    const rawContent = choices[0].message?.content;
    if (!rawContent) {
        showError("Ответ модели не содержит message.content");
        return;
    }

    const comparison = parseLLMJson(rawContent);
    if (!comparison) {
        showError("Не удалось распарсить JSON из ответа LLM");
        return;
    }

    const originalTzData = result.tz_data;
    const originalPassportData = result.passport_data;

    // Получаем информацию о времени выполнения
    const processingTime = result.processing_time || 'N/A';
    const totalTime = result.totalTime || 'N/A';

    let summaryHtml = comparison.matched
        ? `<div class="summary-status matched">✓ Изделие соответствует ожидаемым характеристикам</div>`
        : `<div class="summary-status mismatched">✗ Изделие НЕ соответствует ожидаемым характеристикам</div>`;

    summaryDiv.innerHTML = summaryHtml;

    let sourceDataHTML = `
        <h3>Исходные данные</h3>
        <div class="timing-info" style="margin-bottom: 15px; padding: 10px; background: #e8f5e9; border-left: 4px solid #4caf50; font-size: 0.9em;">
            <strong>⏱ Время выполнения:</strong><br>
            • Обработка на сервере: <strong>${processingTime} сек</strong><br>
            • Общее время (от нажатия кнопки): <strong>${totalTime} сек</strong>
        </div>
        <div class="source-container">

            <details class="source-block">
                <summary>Исходный JSON ТЗ</summary>
                <pre>${JSON.stringify(originalTzData, null, 2)}</pre>
            </details>

            <details class="source-block">
                <summary>Исходный JSON Паспорта</summary>
                <pre>${JSON.stringify(originalPassportData, null, 2)}</pre>
            </details>

        </div>
        <hr>
        <h3>Детали сравнения</h3>
    `;

    if (sourceDataDiv) {
        sourceDataDiv.innerHTML = sourceDataHTML;
    } else {
        summaryDiv.insertAdjacentHTML("afterend", `<div id="sourceData">${sourceDataHTML}</div>`);
    }

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
        const statuses = {
            matched: ["matched", "✓ Соответствует"],
            mismatched: ["mismatched", "✗ Не соответствует"],
            missing: ["missing", "− Отсутствует"]
        };

        const [cls, text] = statuses[specData.status] || ["unknown", "?"];

        detailsHTML += `
            <tr class="${cls}">
                <td>${specName}</td>
                <td>${formatValue(specData.expected)}</td>
                <td>${formatValue(specData.actual) ?? "—"}</td>
                <td>${text}</td>
                <td>${specData.message}</td>
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

    const sourceDataDiv = document.getElementById('sourceData');
    if (sourceDataDiv) sourceDataDiv.innerHTML = '';

    resultsDiv.classList.remove('hidden');
    resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}


function parseLLMJson(content) {
    try {
        const start = content.indexOf('{');
        const end = content.lastIndexOf('}') + 1;

        if (start !== -1 && end > start) {
            return JSON.parse(content.substring(start, end));
        }

        throw new Error("JSON-объект не найден.");
    } catch (e) {
        console.error("Ошибка разбора JSON:", e, content);
        alert("Ошибка: не удалось распарсить ответ модели.");
        return null;
    }
}


function formatValue(value) {
    if (value === null || value === undefined) {
        return "null";
    }
    if (typeof value === 'object') {
        if (Array.isArray(value)) {
            return value.join('; ');
        }
        return JSON.stringify(value, null, 2);
    }
    return String(value);
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('загружено');
});
