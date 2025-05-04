document.addEventListener('DOMContentLoaded', () => {
    const uploadForm = document.getElementById('upload-form');
    const rtspForm = document.getElementById('rtsp-form');
    const countDisplay = document.getElementById('count');
    const outputImg = document.getElementById('output-img');
    const historyTable = document.getElementById('history-table');

    // Загрузка истории при старте
    fetchHistory();

    // Обработка загрузки файла
    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(uploadForm);
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        if (result.error) {
            alert(result.error);
            return;
        }
        countDisplay.textContent = `Количество грузовиков: ${result.count}`;
        if (result.output_path) {
            outputImg.src = result.output_path;
            outputImg.classList.remove('hidden');
        } else {
            outputImg.classList.add('hidden');
        }
        fetchHistory();
    });

    // Обработка RTSP-потока
    rtspForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(rtspForm);
        const response = await fetch('/process_rtsp', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        if (result.error) {
            alert(result.error);
            return;
        }
        countDisplay.textContent = `Количество грузовиков: ${result.count}`;
        if (result.output_path) {
            outputImg.src = result.output_path;
            outputImg.classList.remove('hidden');
        } else {
            outputImg.classList.add('hidden');
        }
        fetchHistory();
    });

    // Получение и отображение истории
    async function fetchHistory() {
        const response = await fetch('/history');
        const history = await response.json();
        historyTable.innerHTML = '';
        history.forEach(entry => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td class="border p-2">${entry.id}</td>
                <td class="border p-2">${entry.timestamp}</td>
                <td class="border p-2">${entry.filename}</td>
                <td class="border p-2">${entry.truck_count}</td>
                <td class="border p-2">
                    ${entry.output_path ? `<a href="${entry.output_path}" target="_blank">Просмотр</a>` : '-'}
                </td>
            `;
            historyTable.appendChild(row);
        });
    }
});