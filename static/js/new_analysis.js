document.getElementById('analyzeForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const formData = new FormData(e.target);
    const loading = document.getElementById('loading');

    try {
        loading.classList.remove('hidden');

        const response = await fetch('/api/analysis/create', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error);
        }

        alert('Анализ создан и отправлен на обработку!');
        window.location.href = '/';

    } catch (error) {
        console.error('Ошибка создания анализа:', error);
        alert('Ошибка: ' + error.message);
    } finally {
        loading.classList.add('hidden');
    }
});