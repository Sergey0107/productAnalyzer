// Получаем ID анализа из URL
const analysisId = window.location.pathname.split('/').pop();

// Глобальные переменные
let analysisData = null;
let fieldVerifications = {};

// Загрузка данных при загрузке страницы
document.addEventListener('DOMContentLoaded', async () => {
    console.log('Страница загружена, начинаем загрузку данных...');
    await loadAnalysisData();
});

// Загрузка данных анализа
async function loadAnalysisData() {
    try {
        console.log(`Загружаем анализ #${analysisId}...`);
        const response = await fetch(`/api/analysis/${analysisId}`, {
            credentials: 'include'
        });

        if (!response.ok) {
            if (response.status === 401) {
                console.error('Требуется авторизация');
                window.location.href = '/login';
                return;
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Данные анализа получены:', data);

        if (!data.success) {
            throw new Error(data.error || 'Ошибка загрузки данных');
        }

        analysisData = data.analysis;
         if (typeof analysisData.comparison_result === 'string') {
            try {
                analysisData.comparison_result = JSON.parse(analysisData.comparison_result);
                console.log('Parsed comparison_result:', analysisData.comparison_result);
            } catch (parseError) {
                console.error('Error parsing comparison_result:', parseError);
            }
        }
        console.log('Analysis data:', analysisData);

        // Загружаем проверки полей
        await loadFieldVerifications();

        // Если проверок полей нет, создаем их автоматически из результатов
        if (Object.keys(fieldVerifications).length === 0 && analysisData.comparison_result) {
            console.log('Проверки полей не найдены, инициализируем...');
            await initializeFieldVerifications();
        }

        // Отображаем данные
        displayAnalysisInfo();
        displayResults();

        document.getElementById('loading').classList.add('hidden');
        document.getElementById('results-section').classList.remove('hidden');

    } catch (error) {
        console.error('Error loading analysis:', error);
        document.getElementById('loading').classList.add('hidden');
        const errorDiv = document.getElementById('error-message');
        errorDiv.textContent = 'Ошибка загрузки: ' + error.message;
        errorDiv.classList.remove('hidden');
    }
}

// Загрузка проверок полей
async function loadFieldVerifications() {
    try {
        console.log(`Загружаем проверки полей для анализа #${analysisId}...`);
        const response = await fetch(`/api/analysis/${analysisId}/field-verifications`, {
            credentials: 'include'
        });

        console.log('Field verifications response status:', response.status);

        if (response.ok) {
            const data = await response.json();
            console.log('Field verifications data:', data);
            if (data.success) {
                fieldVerifications = data.field_verifications || {};
                console.log(`Загружено ${Object.keys(fieldVerifications).length} проверок полей`);
            } else {
                console.error('Field verifications error:', data.error);
            }
        } else {
            const errorText = await response.text();
            console.error('Field verifications HTTP error:', response.status, errorText);
        }
    } catch (error) {
        console.error('Error loading field verifications:', error);
    }
}

// Инициализация проверок полей из результатов сравнения
async function initializeFieldVerifications() {
    try {
        console.log('Инициализируем проверки полей...');
        const response = await fetch(`/api/analysis/${analysisId}/save-all-fields`, {
            method: 'POST',
            credentials: 'include'
        });

        if (response.ok) {
            const data = await response.json();
            if (data.success) {
                console.log(`✓ Инициализировано ${data.saved_count} полей`);
                // Перезагружаем проверки
                await loadFieldVerifications();
            } else {
                console.error('Ошибка инициализации:', data.error);
            }
        } else {
            const errorText = await response.text();
            console.error('HTTP error при инициализации:', response.status, errorText);
        }
    } catch (error) {
        console.error('Error initializing field verifications:', error);
    }
}

// Отображение информации об анализе
function displayAnalysisInfo() {
    const infoDiv = document.getElementById('analysis-info');

    const statusText = {
        'pending': 'Ожидает обработки',
        'processing': 'В обработке',
        'completed': 'Завершено',
        'failed': 'Ошибка'
    };

    infoDiv.innerHTML = `
        <h2>Анализ #${analysisData.id}</h2>
        <div class="info-grid">
            <div class="info-item">
                <strong>Техническое задание:</strong> ${analysisData.tz_filename}
            </div>
            <div class="info-item">
                <strong>Паспорт:</strong> ${analysisData.passport_filename}
            </div>
            <div class="info-item">
                <strong>Статус:</strong> <span class="status-${analysisData.status}">${statusText[analysisData.status]}</span>
            </div>
            <div class="info-item">
                <strong>Время обработки:</strong> ${analysisData.processing_time ? analysisData.processing_time + ' сек.' : 'N/A'}
            </div>
        </div>
    `;
}

// Отображение результатов
function displayResults() {
    console.log('Отображаем результаты...');
    const tbody = document.getElementById('results-tbody');
    tbody.innerHTML = '';

    if (!analysisData.comparison_result) {
        console.error('Нет comparison_result в данных анализа');
        tbody.innerHTML = '<tr><td colspan="8">Нет результатов сравнения</td></tr>';
        return;
    }

    // Извлекаем данные сравнения
    let comparisonData = null;

    try {
        // 1. Пытаемся получить данные из response.choices[0].message.content
        if (analysisData.comparison_result.response &&
            analysisData.comparison_result.response.choices &&
            analysisData.comparison_result.response.choices[0] &&
            analysisData.comparison_result.response.choices[0].message &&
            analysisData.comparison_result.response.choices[0].message.content) {

            const content = analysisData.comparison_result.response.choices[0].message.content;
            console.log('Извлекаем данные из content:', content.substring(0, 200) + '...');

            // Извлекаем JSON из code block
            const jsonMatch = content.match(/```json\s*([\s\S]*?)\s*```/);
            if (jsonMatch && jsonMatch[1]) {
                comparisonData = JSON.parse(jsonMatch[1].trim());
                console.log('Распарсили данные из code block:', comparisonData);
            }
        }

        // 2. Если не удалось получить из content, пробуем напрямую
        if (!comparisonData && analysisData.comparison_result.details) {
            comparisonData = analysisData.comparison_result;
            console.log('Используем comparison_result напрямую');
        }

        // 3. Если все еще нет данных
        if (!comparisonData) {
            console.error('Не удалось извлечь данные сравнения:', analysisData.comparison_result);
            tbody.innerHTML = '<tr><td colspan="8">Не удалось извлечь данные сравнения</td></tr>';
            return;
        }

    } catch (e) {
        console.error('Ошибка при обработке comparison_result:', e);
        tbody.innerHTML = '<tr><td colspan="8">Ошибка обработки данных сравнения</td></tr>';
        return;
    }

    // Проверяем наличие details
    if (!comparisonData.details || typeof comparisonData.details !== 'object') {
        console.error('Нет details в данных сравнения:', comparisonData);
        tbody.innerHTML = '<tr><td colspan="8">Нет детализированных результатов сравнения</td></tr>';
        return;
    }

    // Получаем все поля для сравнения из details
    const fieldKeys = Object.keys(comparisonData.details);
    console.log(`Найдено ${fieldKeys.length} полей в details:`, fieldKeys);

    if (fieldKeys.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8">Нет данных для отображения</td></tr>';
        return;
    }

    // Создаем строки для каждого поля
    fieldKeys.forEach((fieldKey, index) => {
        const fieldData = comparisonData.details[fieldKey];

        // Получаем tz_value из tz_data если нет в fieldData
        let tzValue = fieldData.expected;
        if (!tzValue && analysisData.comparison_result.tz_data &&
            analysisData.comparison_result.tz_data[fieldKey]) {
            tzValue = analysisData.comparison_result.tz_data[fieldKey];
        }

        // Получаем passport_value из passport_data если нет в fieldData
        let passportValue = fieldData.actual;
        if (!passportValue && analysisData.comparison_result.passport_data &&
            analysisData.comparison_result.passport_data[fieldKey]) {
            passportValue = analysisData.comparison_result.passport_data[fieldKey];
        }

        // Создаем объект с данными для строки в формате, ожидаемом createResultRow
        const rowData = {
            key: fieldKey,
            tz_value: tzValue || null,  // expected = значение из ТЗ
            passport_value: passportValue || null,  // actual = значение из паспорта
            match: fieldData.status === 'matched' || fieldData.status === 'complete',  // match если status = 'matched'
            quote: fieldData.message || ''  // message как quote
        };

        console.log(`Создаем строку для поля: ${fieldKey}`, rowData);
        const row = createResultRow(rowData, index);
        tbody.appendChild(row);
    });

    console.log(`✓ Отображено ${fieldKeys.length} строк в таблице`);

    // Загружаем общий комментарий
    if (analysisData.comment) {
        document.getElementById('general-comment').value = analysisData.comment;
    }

    // Устанавливаем общую проверку
    if (analysisData.manual_verification !== null && analysisData.manual_verification !== undefined) {
        const radioValue = analysisData.manual_verification ? 'true' : 'false';
        const radio = document.querySelector(`input[name="general-verification"][value="${radioValue}"]`);
        if (radio) {
            radio.checked = true;
        }
    }
}

// Создание строки таблицы результатов
// Создание строки таблицы результатов
function createResultRow(item, index) {
    const row = document.createElement('tr');

    const fieldKey = item.key || `field_${index}`;
    const verification = fieldVerifications[fieldKey] || {};

    // Используем данные из verification если они есть, иначе из item
    const tzValue = verification.tz_value !== undefined ? verification.tz_value : item.tz_value;
    const passportValue = verification.passport_value !== undefined ? verification.passport_value : item.passport_value;
    const quote = verification.quote !== undefined ? verification.quote : (item.quote || '');
    const autoMatch = verification.auto_match !== undefined ? verification.auto_match : item.match;

    // Статус автоматической проверки
    const matchClass = autoMatch ? 'match-yes' : 'match-no';
    const matchText = autoMatch ? 'Совпадает' : 'Не совпадает';

    // Создаем безопасный ID для элементов
    const safeFieldKey = fieldKey.replace(/[^a-zA-Z0-9_-]/g, '_');

    row.innerHTML = `
        <td>${escapeHtml(fieldKey) || 'N/A'}</td>
        <td>${formatValue(tzValue)}</td>
        <td>${formatValue(passportValue)}</td>
        <td>${formatValue(quote)}</td>
        <td class="${matchClass}">${matchText}</td>
        <td>
            <div class="field-verification-cell">
                <label>
                    <input type="radio" 
                           name="field_verification_${index}" 
                           value="true"
                           ${verification.manual_verification === true ? 'checked' : ''}
                           data-field-key="${escapeHtml(fieldKey)}"
                           data-index="${index}">
                    <span>✓</span>
                </label>
                <label>
                    <input type="radio" 
                           name="field_verification_${index}" 
                           value="false"
                           ${verification.manual_verification === false ? 'checked' : ''}
                           data-field-key="${escapeHtml(fieldKey)}"
                           data-index="${index}">
                    <span>✗</span>
                </label>
                <label>
                    <input type="radio" 
                           name="field_verification_${index}" 
                           value=""
                           ${verification.manual_verification === null || verification.manual_verification === undefined ? 'checked' : ''}
                           data-field-key="${escapeHtml(fieldKey)}"
                           data-index="${index}">
                    <span>—</span>
                </label>
            </div>
        </td>
        <td class="field-comment-cell">
            <textarea 
                class="field-comment-input" 
                id="comment_${safeFieldKey}"
                placeholder="Комментарий..."
                rows="2"
                data-field-key="${escapeHtml(fieldKey)}"
                data-index="${index}"
            >${escapeHtml(verification.specialist_comment || '')}</textarea>
        </td>
        <td>
            <button 
                class="save-field-btn" 
                id="save_btn_${safeFieldKey}"
                data-field-key="${escapeHtml(fieldKey)}"
                data-index="${index}"
                disabled
            >
                Сохранить
            </button>
            <span class="field-status" id="status_${safeFieldKey}"></span>
        </td>
    `;

    // Добавляем обработчики событий после создания элементов
    setTimeout(() => {
        const radios = row.querySelectorAll(`input[name="field_verification_${index}"]`);
        radios.forEach(radio => {
            radio.addEventListener('change', () => {
                markFieldChanged(fieldKey, index);
            });
        });

        const textarea = row.querySelector(`#comment_${safeFieldKey}`);
        if (textarea) {
            textarea.addEventListener('input', () => { // Используем input вместо change для мгновенной реакции
                markFieldChanged(fieldKey, index);
            });
        }

        const saveBtn = row.querySelector(`#save_btn_${safeFieldKey}`);
        if (saveBtn) {
            saveBtn.addEventListener('click', () => {
                saveFieldVerification(fieldKey, index);
            });
        }
    }, 0);

    return row;
}

// Экранирование HTML для безопасности
function escapeHtml(text) {
    if (!text) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}

// Форматирование значения для отображения
function formatValue(value) {
    if (value === null || value === undefined || value === '') {
        return '<span style="color: #999;">N/A</span>';
    }

    if (typeof value === 'object') {
        return '<pre>' + JSON.stringify(value, null, 2) + '</pre>';
    }

    return escapeHtml(String(value));
}

// Отметить поле как измененное
function markFieldChanged(fieldKey, index) {
    const safeFieldKey = fieldKey.replace(/[^a-zA-Z0-9_-]/g, '_');
    const saveBtn = document.getElementById(`save_btn_${safeFieldKey}`);
    if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.style.backgroundColor = '#ff9800';
    }
}

// Сохранение проверки поля
// Сохранение проверки поля
async function saveFieldVerification(fieldKey, index) {
    const safeFieldKey = fieldKey.replace(/[^a-zA-Z0-9_-]/g, '_');
    const saveBtn = document.getElementById(`save_btn_${safeFieldKey}`);
    const statusSpan = document.getElementById(`status_${safeFieldKey}`);

    console.log(`Сохраняем поле: ${fieldKey}`);

    // Получаем значения
    const verificationRadios = document.getElementsByName(`field_verification_${index}`);
    let manualVerification = null;

    for (const radio of verificationRadios) {
        if (radio.checked) {
            if (radio.value === 'true') {
                manualVerification = true;
            } else if (radio.value === 'false') {
                manualVerification = false;
            } else {
                manualVerification = null;
            }
            break;
        }
    }

    const commentTextarea = document.getElementById(`comment_${safeFieldKey}`);
    const comment = commentTextarea ? commentTextarea.value.trim() : '';

    // Получаем данные из существующей записи или из результатов сравнения
    const verification = fieldVerifications[fieldKey] || {};

    // Получаем данные сравнения (они могут быть в строке или объекте)
    let comparisonResult = analysisData.comparison_result;
    if (typeof comparisonResult === 'string') {
        try {
            comparisonResult = JSON.parse(comparisonResult);
        } catch (e) {
            console.error('Ошибка парсинга comparison_result при сохранении:', e);
        }
    }

    const comparisonItem = comparisonResult ? comparisonResult[fieldKey] || {} : {};

    const requestData = {
        field_key: fieldKey,
        tz_value: verification.tz_value !== undefined ? verification.tz_value : String(comparisonItem.tz_value || comparisonItem.tz || ''),
        passport_value: verification.passport_value !== undefined ? verification.passport_value : String(comparisonItem.passport_value || comparisonItem.passport || ''),
        quote: verification.quote !== undefined ? verification.quote : (comparisonItem.comment || comparisonItem.quote || ''),
        auto_match: verification.auto_match !== undefined ? verification.auto_match : comparisonItem.match,
        manual_verification: manualVerification,
        specialist_comment: comment || null
    };

    console.log('Отправляем данные:', requestData);

    try {
        // Показываем статус сохранения
        if (statusSpan) {
            statusSpan.textContent = 'Сохранение...';
            statusSpan.className = 'field-status saving';
        }
        if (saveBtn) {
            saveBtn.disabled = true;
        }

        const response = await fetch(`/api/analysis/${analysisId}/field-verification`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify(requestData)
        });

        console.log('Response status:', response.status);

        if (!response.ok) {
            const errorText = await response.text();
            console.error('HTTP error:', errorText);
            throw new Error(`HTTP error ${response.status}`);
        }

        const data = await response.json();
        console.log('Response data:', data);

        if (data.success) {
            // Обновляем локальный кэш
            fieldVerifications[fieldKey] = {
                tz_value: data.field_verification.tz_value,
                passport_value: data.field_verification.passport_value,
                quote: data.field_verification.quote,
                auto_match: data.field_verification.auto_match,
                manual_verification: manualVerification,
                specialist_comment: comment || null
            };

            // Показываем успех
            if (statusSpan) {
                statusSpan.textContent = 'Сохранено';
                statusSpan.className = 'field-status saved';
            }
            if (saveBtn) {
                saveBtn.style.backgroundColor = '#4CAF50';
            }

            // Убираем статус через 2 секунды
            setTimeout(() => {
                if (statusSpan) {
                    statusSpan.textContent = '';
                    statusSpan.className = 'field-status';
                }
            }, 2000);
        } else {
            throw new Error(data.error || 'Ошибка сохранения');
        }

    } catch (error) {
        console.error('Error saving field verification:', error);
        if (statusSpan) {
            statusSpan.textContent = 'Ошибка';
            statusSpan.className = 'field-status error';
        }
        if (saveBtn) {
            saveBtn.disabled = false;
        }
        alert('Ошибка при сохранении: ' + error.message);
    }
}

// Сохранение общего комментария
async function saveGeneralComment() {
    const comment = document.getElementById('general-comment').value.trim();
    const verificationRadios = document.getElementsByName('general-verification');
    
    let manualVerification = null;
    for (const radio of verificationRadios) {
        if (radio.checked) {
            if (radio.value === 'true') {
                manualVerification = true;
            } else if (radio.value === 'false') {
                manualVerification = false;
            }
            break;
        }
    }
    
    try {
        const formData = new FormData();
        if (manualVerification !== null) {
            formData.append('manual_verification', manualVerification);
        }
        if (comment) {
            formData.append('comment', comment);
        }
        
        const response = await fetch(`/api/analysis/${analysisId}`, {
            method: 'PATCH',
            credentials: 'include',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error('Ошибка сохранения');
        }
        
        const data = await response.json();
        
        if (data.success) {
            alert('Общий комментарий сохранен успешно');
        } else {
            throw new Error(data.error || 'Ошибка сохранения');
        }
        
    } catch (error) {
        console.error('Error saving general comment:', error);
        alert('Ошибка при сохранении: ' + error.message);
    }
}