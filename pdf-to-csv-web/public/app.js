document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('uploadForm');
    const resultContainer = document.getElementById('resultContainer');

    form.addEventListener('submit', async function(event) {
        event.preventDefault();
        
        const formData = new FormData(form);
        
        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            const result = await response.json();
            displayResult(result);
        } catch (error) {
            console.error('Error:', error);
            resultContainer.innerHTML = 'An error occurred during the upload.';
        }
    });

    function displayResult(result) {
        resultContainer.innerHTML = '';
        const csvData = document.createElement('pre');
        csvData.textContent = result.csvContent;
        resultContainer.appendChild(csvData);
    }
});