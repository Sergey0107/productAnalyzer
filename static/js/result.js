const analysisId = window.location.pathname.split('/').pop();

let analysisData = null;
let fieldVerifications = {};

document.addEventListener('DOMContentLoaded', async () => {
    try {
        await loadAnalysisData();
        renderPage();
    } catch (err) {
        console.error('Ошибка инициализации страницы:', err);
        showError('Ошибка загрузки данных анализа');
    }
});

async function loadAnalysisData() {
    const response = await fetch(`/api/analysis/${analysisId}`, {
        credentials: 'include'
    });

    if (!response.ok) {
        if (response.status === 401) {
            window.location.href = '/login';
            return;
        }
        throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();

    if (!data.success) {
        throw new Error(data.error || 'Ошибка загрузки анализа');
    }

    analysisData = data.analysis;
    fieldVerifications = {};

    for (const f of data.fields) {
        fieldVerifications[f.field_key] = f;
    }
}

function renderPage() {
    renderAnalysisInfo();
    renderResultsTable();

    document.getElementById('loading')?.classList.add('hidden');
    document.getElementById('results-section')?.classList.remove('hidden');
}

function renderAnalysisInfo() {
    const infoDiv = document.getElementById('analysis-info');

    const statusMap = {
        pending: 'Ожидает обработки',
        processing: 'В обработке',
        completed: 'Завершено',
        failed: 'Ошибка'
    };

    infoDiv.innerHTML = `
        <h2>Анализ #${analysisData.id}</h2>
        <div class="info-grid">
            <div><strong>ТЗ:</strong> ${escapeHtml(analysisData.tz_filename)}</div>
            <div><strong>Паспорт:</strong> ${escapeHtml(analysisData.passport_filename)}</div>
            <div>
                <strong>Статус:</strong>
                <span class="status-${analysisData.status}">
                    ${statusMap[analysisData.status] || analysisData.status}
                </span>
            </div>
        </div>
    `;
}

function renderResultsTable() {
    const tbody = document.getElementById('results-tbody');
    tbody.innerHTML = '';

    const keys = Object.keys(fieldVerifications);

    if (keys.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8">Нет данных для отображения</td></tr>';
        return;
    }

    keys.forEach((fieldKey, index) => {
        const row = createResultRow(fieldKey, index);
        tbody.appendChild(row);
    });
}

function createResultRow(fieldKey, index) {
    const fv = fieldVerifications[fieldKey];
    const safeKey = fieldKey.replace(/[^a-zA-Z0-9_-]/g, '_');

    const row = document.createElement('tr');

    const matchText = fv.auto_match ? 'Совпадает' : 'Не совпадает';
    const matchClass = fv.auto_match ? 'match-yes' : 'match-no';

    row.innerHTML = `
        <td>${escapeHtml(fieldKey)}</td>
        <td>${formatValue(fv.tz_value)}</td>
        <td>${formatValue(fv.passport_value)}</td>
        <td>${formatValue(fv.quote)}</td>
        <td class="${matchClass}">${matchText}</td>
        <td>
            <label><input type="radio" name="verify_${index}" value="true"
                ${fv.manual_verification === true ? 'checked' : ''}> ✓</label>
            <label><input type="radio" name="verify_${index}" value="false"
                ${fv.manual_verification === false ? 'checked' : ''}> ✗</label>
            <label><input type="radio" name="verify_${index}" value=""
                ${fv.manual_verification == null ? 'checked' : ''}> —</label>
        </td>
        <td>
            <textarea id="comment_${safeKey}" rows="2"
                placeholder="Комментарий...">${escapeHtml(fv.specialist_comment || '')}</textarea>
        </td>
        <td>
            <button id="save_${safeKey}" disabled>Сохранить</button>
            <span id="status_${safeKey}" class="field-status"></span>
        </td>
    `;

    const radios = row.querySelectorAll(`input[name="verify_${index}"]`);
    const textarea = row.querySelector(`#comment_${safeKey}`);
    const saveBtn = row.querySelector(`#save_${safeKey}`);

    [...radios, textarea].forEach(el => {
        el.addEventListener('change', () => {
            saveBtn.disabled = false;
            saveBtn.style.backgroundColor = '#ff9800';
        });
    });

    saveBtn.addEventListener('click', () => {
        saveFieldVerification(fieldKey, index);
    });

    return row;
}

async function saveFieldVerification(fieldKey, index) {
    const fv = fieldVerifications[fieldKey];
    const safeKey = fieldKey.replace(/[^a-zA-Z0-9_-]/g, '_');

    const radios = document.getElementsByName(`verify_${index}`);
    let manual = null;

    for (const r of radios) {
        if (r.checked) {
            manual = r.value === '' ? null : r.value === 'true';
        }
    }

    const comment = document.getElementById(`comment_${safeKey}`).value.trim();
    const statusSpan = document.getElementById(`status_${safeKey}`);
    const saveBtn = document.getElementById(`save_${safeKey}`);

    statusSpan.textContent = 'Сохранение...';

    const payload = {
        field_key: fieldKey,
        tz_value: fv.tz_value ?? '',
        passport_value: fv.passport_value ?? '',
        quote: fv.quote ?? '',
        auto_match: fv.auto_match ?? null,
        manual_verification: manual,
        specialist_comment: comment || null
    };

    try {
        const res = await fetch(`/api/analysis/${analysisId}/field-verification`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(payload)
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = await res.json();
        if (!data.success) throw new Error(data.error);

        fieldVerifications[fieldKey] = data.field_verification;

        statusSpan.textContent = 'Сохранено';
        saveBtn.disabled = true;
        saveBtn.style.backgroundColor = '#4CAF50';

        setTimeout(() => (statusSpan.textContent = ''), 2000);
    } catch (err) {
        console.error(err);
        statusSpan.textContent = 'Ошибка';
        saveBtn.disabled = false;
    }
}

function showError(message) {
    const errorDiv = document.getElementById('error-message');
    errorDiv.textContent = message;
    errorDiv.classList.remove('hidden');
    
    document.getElementById('loading')?.classList.add('hidden');
}

function escapeHtml(value) {
    if (!value) return '';
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function formatValue(value) {
    if (!value) return '<span style="color:#999">N/A</span>';
    return escapeHtml(value);
}

async function saveGeneralComment() {
    const comment = document.getElementById('general-comment').value.trim();
    const radios = document.getElementsByName('general-verification');
    
    let verification = null;
    for (const r of radios) {
        if (r.checked) {
            verification = r.value === '' ? null : r.value === 'true';
        }
    }

    try {
        const formData = new FormData();
        if (comment) formData.append('comment', comment);
        if (verification !== null) formData.append('manual_verification', verification);

        const res = await fetch(`/api/analysis/${analysisId}`, {
            method: 'PATCH',
            credentials: 'include',
            body: formData
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = await res.json();
        if (!data.success) throw new Error(data.error);

        alert('Общий комментарий сохранен');
    } catch (err) {
        console.error(err);
        alert('Ошибка сохранения комментария');
    }
}