// Загрузка списка анализов
async function loadAnalyses() {
    try {
        const response = await fetch('/api/analyses');
        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error);
        }

        const analysesList = document.getElementById('analyses-list');
        const emptyState = document.getElementById('empty-state');

        if (data.analyses.length === 0) {
            analysesList.classList.add('hidden');
            emptyState.classList.remove('hidden');
            return;
        }

        analysesList.innerHTML = data.analyses.map(analysis => `
            <div class="analysis-item">
                <div class="analysis-content">
                    <div class="analysis-field">
                        <span class="analysis-label">Техническое задание:</span>
                        <span class="analysis-value">${escapeHtml(analysis.tz_filename)}</span>
                    </div>
                    <div class="analysis-field">
                        <span class="analysis-label">Паспорт изделия:</span>
                        <span class="analysis-value">${escapeHtml(analysis.passport_filename)}</span>
                    </div>
                    <div class="analysis-field">
                        <span class="analysis-label">Статус:</span>
                        <span class="status-badge status-${analysis.status}">${getStatusText(analysis.status)}</span>
                    </div>
                </div>
                <div class="analysis-actions">
                    ${analysis.status === 'completed' ? 
                        `<button onclick="openAnalysis(${analysis.id})" class="btn-open">Открыть</button>` : 
                        `<button class="btn-open" disabled>Открыть</button>`
                    }
                </div>
            </div>
        `).join('');

        analysesList.classList.remove('hidden');
        emptyState.classList.add('hidden');

    } catch (error) {
        console.error('Ошибка загрузки анализов:', error);
        alert('Ошибка загрузки списка анализов');
    }
}

function getStatusText(status) {
    const statusMap = {
        'pending': 'ожидает',
        'processing': 'в процессе',
        'completed': 'готово',
        'failed': 'ошибка'
    };
    return statusMap[status] || status;
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

function openAnalysis(id) {
    window.location.href = `/analysis/${id}`;
}

// Загружаем список при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    loadAnalyses();

    // Обновляем список каждые 5 секунд для отслеживания прогресса
    setInterval(loadAnalyses, 5000);
});