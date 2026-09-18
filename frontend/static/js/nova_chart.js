/* Nova Chart.js renderer — used by the floating Nova widget */
(function (global) {
  let chart;
  const colors = ['#0284c7', '#0ea5e9', '#38bdf8', '#6366f1', '#14b8a6', '#f59e0b', '#f43f5e'];

  function renderNovaChart(canvasId, payload) {
    const canvas = document.getElementById(canvasId || 'novaChart');
    if (!canvas || typeof Chart === 'undefined') return;
    const ctx = canvas.getContext('2d');
    const type = (payload && payload.type) || 'bar';
    const labels = (payload && payload.labels) || [];
    const values = (payload && payload.values) || [];
    const titleEl = document.getElementById('novaChartTitle');
    if (titleEl) titleEl.textContent = (payload && payload.title) || 'Chart';
    if (chart) chart.destroy();
    var empty = document.getElementById('novaChartEmpty');
    if (empty) empty.classList.add('hidden');
    chart = new Chart(ctx, {
      type: type,
      data: {
        labels: labels,
        datasets: [{
          label: (payload && payload.title) || 'Value',
          data: values,
          backgroundColor: labels.map(function (_, i) { return colors[i % colors.length]; }),
          borderColor: '#0369a1',
          borderWidth: type === 'line' ? 2 : 0,
          tension: 0.3,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: type === 'doughnut' || type === 'pie' } },
        scales: (type === 'doughnut' || type === 'pie') ? {} : {
          y: { beginAtZero: true, ticks: { precision: 0 } },
          x: { ticks: { maxRotation: 45, minRotation: 0 } }
        }
      }
    });
    return chart;
  }

  global.renderNovaChart = renderNovaChart;
})(window);
