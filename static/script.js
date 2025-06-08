document.addEventListener('DOMContentLoaded', () => {
    const datasetFile = document.getElementById('dataset-file');
    const inputFile = document.getElementById('input-file');
    const predictBtn = document.querySelector('.predict-btn');
    const optimizeBtn = document.querySelector('.optimize-btn');
    const inventoryInput = document.getElementById('inventory-size');

    let uploadedDataset = null;
    let uploadedInput = null;

    datasetFile.addEventListener('change', (e) => {
        uploadedDataset = e.target.files[0];
        document.querySelector('.dataset-status').textContent = uploadedDataset.name;
    });

    inputFile.addEventListener('change', (e) => {
        uploadedInput = e.target.files[0];
        document.querySelector('.input-status').textContent = uploadedInput.name;
    });

    predictBtn.addEventListener('click', async (e) => {
        
        e.preventDefault();
        if (!uploadedDataset || !uploadedInput) {
            alert('Please upload both dataset and input set.');
            return;
        }

        const formData = new FormData();
        formData.append('train', uploadedDataset);

        await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        const inputForm = new FormData();
        inputForm.append('input', uploadedInput);

        const predictionRes = await fetch('/predict', {
            method: 'POST',
            body: inputForm
        });

        const predictionData = await predictionRes.json();

        const predictionList = predictionData.named_predictions
            .map((item) => `<li>${item.name}: ${item.value !== null ? item.value.toFixed(2) : "N/A"} units</li>`)
            .join('');

        const resultsContainer = document.querySelector('.results-placeholder');
        resultsContainer.innerHTML = `
            <h3>Forecasted Demand (Before Optimization)</h3>
            <ul>${predictionList}</ul>
        `;
    });

    optimizeBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        const inventorySize = inventoryInput.value;
        if (!inventorySize || inventorySize <= 0) {
            alert('Please enter a valid inventory size.');
            return;
        }

        const formData = new FormData();
        formData.append('inventory', inventorySize);

        const res = await fetch('/optimize', {
            method: 'POST',
            body: formData
        });

        const data = await res.json();

        document.querySelector('.before-card .metric-value').textContent = data.before_optimization.toFixed(2);
        document.querySelector('.after-card .metric-value').textContent = data.after_optimization.toFixed(2);

        document.querySelector('.before-card .empty-state').innerHTML = '';
        document.querySelector('.after-card .empty-state').innerHTML = '';

        const summaryBox = document.querySelector('.summary-placeholder');
        summaryBox.innerHTML = `
            <p><strong>Total Space Used:</strong> ${data.after_optimization.toFixed(0)} cubic meters (Max: 5000)</p>
            ${data.after_optimization > 5000 ? "<p style='color:red;'><strong>Warning:</strong> Storage Exceeds 5000 cubic meters! Optimization required.</p>" : ""}
            <p><strong>Evaluation Metrics:</strong></p>
            <ul>
                ${Object.entries(data.metrics).map(([cat, vals]) => `
                    <li><strong>${cat}</strong>: RMSE=${vals.RMSE.toFixed(2)}, MSE=${vals.MSE.toFixed(2)}, R²=${vals.R2.toFixed(2)}</li>
                `).join('')}
            </ul>
        `;

        if (data.inventory_changes) {
            const changesList = data.inventory_changes.map(item =>
                `<li>${item.Infrastructure_Machineries}: ${item.Predicted_Sales.toFixed(0)} ➜ ${item.Optimized_Inventory.toFixed(0)} units (Δ ${item.Change.toFixed(0)})</li>`
            ).join('');

            summaryBox.innerHTML += `
                <p><strong>Allocated Inventory (After Optimization):</strong></p>
                <ul>${changesList}</ul>
            `;
        }
    });
    // Fill Before Optimization section
const beforeDetailsHTML = data.before_details.map(item =>
    `<li>${item.Infrastructure_Machineries}: ${item.Predicted_Sales.toFixed(0)} units</li>`
).join('');
const beforeCard = document.querySelector('.before-card .empty-state');
beforeCard.innerHTML = `
    <h4>BEFORE OPTIMIZATION: Forecasted Demand</h4>
    <ul>${beforeDetailsHTML}</ul>
    <p><strong>Total Space Needed:</strong> ${data.total_predicted_space.toFixed(0)} cubic meters</p>
    ${data.total_predicted_space > 5000 ? `<p style="color:red;"><strong>Warning:</strong> Storage Exceeds 5000 cubic meters! Optimization required.</p>` : ''}
`;

// Fill After Optimization section
const afterDetailsHTML = data.after_details.map(item =>
    `<li>${item.Infrastructure_Machineries}: ${item.Optimized_Inventory.toFixed(0)} units</li>`
).join('');
const afterCard = document.querySelector('.after-card .empty-state');
afterCard.innerHTML = `
    <h4>AFTER OPTIMIZATION: Allocated Inventory</h4>
    <ul>${afterDetailsHTML}</ul>
    <p><strong>Total Space Used:</strong> ${data.total_optimized_space.toFixed(0)} cubic meters (Max: 5000)</p>
`;

});
