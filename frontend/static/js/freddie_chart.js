/* Freddie Chart.js renderer — used by frontend/templates/freddie.html */
(function (global) {
  let chart;
  const colors = ['#0284c7', '#0ea5e9', '#38bdf8', '#6366f1', '#14b8a6', '#f59e0b', '#f43f5e'];

  function renderFreddieChart(canvasId, payload) {
    const canvas = document.getElementById(canvasId || 'freddieChart');
    if (!canvas || typeof Chart === 'undefined') return;
    const ctx = canvas.getContext('2d');
    const type = (payload && payload.type) || 'bar';
    const labels = (payload && payload.labels) || [];
    const values = (payload && payload.values) || [];
    const titleEl = document.getElementById('freddieChartTitle');
    if (titleEl) titleEl.textContent = (payload && payload.title) || 'Chart box';
    if (chart) chart.destroy();
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

  global.renderFreddieChart = renderFreddieChart;
})(window);
