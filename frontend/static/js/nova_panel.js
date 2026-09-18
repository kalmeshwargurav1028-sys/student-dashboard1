/* Nova floating panel — open/close + ask/ingest */
(function () {
  var ingestUrl = '/api/nova/ingest';
  var askUrl = '/api/nova/ask';
  var statusUrl = '/api/nova/status';

  function $(id) { return document.getElementById(id); }

  function setStatus(msg, isError) {
    var el = $('novaStatus');
    if (!el) return;
    var count = $('novaChunkCount');
    var countHtml = count ? count.outerHTML : '';
    if (msg) {
      el.innerHTML = msg;
      el.className = 'text-[11px] ' + (isError ? 'text-red-500' : 'text-slate-400');
    } else {
      el.innerHTML = 'Indexed: ' + countHtml + ' chunks';
      el.className = 'text-[11px] text-slate-400';
    }
  }

  function setChunkCount(n) {
    var el = $('novaChunkCount');
    if (el) el.textContent = n == null ? '—' : String(n);
  }

  function showChartEmpty(show) {
    var empty = $('novaChartEmpty');
    if (empty) empty.classList.toggle('hidden', !show);
  }

  function openPanel() {
    var panel = $('novaPanel');
    var fab = $('novaFab');
    if (!panel || !fab) return;
    panel.classList.add('is-open');
    fab.classList.add('is-open');
    fab.setAttribute('aria-expanded', 'true');
    loadStatus();
    var q = $('novaQuestion');
    if (q) setTimeout(function () { q.focus(); }, 180);
  }

  function closePanel() {
    var panel = $('novaPanel');
    var fab = $('novaFab');
    if (!panel || !fab) return;
    panel.classList.remove('is-open');
    fab.classList.remove('is-open');
    fab.setAttribute('aria-expanded', 'false');
  }

  function togglePanel() {
    var panel = $('novaPanel');
    if (panel && panel.classList.contains('is-open')) closePanel();
    else openPanel();
  }

  async function loadStatus() {
    try {
      var res = await fetch(statusUrl, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
      var data = await res.json();
      if (data && data.ok) setChunkCount(data.chunks || 0);
    } catch (e) { /* ignore */ }
  }

  function bind() {
    var fab = $('novaFab');
    var panel = $('novaPanel');
    if (!fab || !panel) return;

    fab.addEventListener('click', function (e) {
      e.preventDefault();
      togglePanel();
    });

    var closeBtn = $('novaCloseBtn');
    if (closeBtn) closeBtn.addEventListener('click', closePanel);

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && panel.classList.contains('is-open')) closePanel();
    });

    document.addEventListener('mousedown', function (e) {
      if (!panel.classList.contains('is-open')) return;
      if (panel.contains(e.target) || fab.contains(e.target)) return;
      closePanel();
    });

    document.querySelectorAll('.nova-chip').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var q = $('novaQuestion');
        if (q) {
          q.value = btn.getAttribute('data-q') || '';
          q.focus();
        }
      });
    });

    var ingestBtn = $('novaIngestBtn');
    if (ingestBtn) {
      ingestBtn.addEventListener('click', async function () {
        ingestBtn.disabled = true;
        var icon = ingestBtn.querySelector('svg');
        if (icon) icon.classList.add('animate-spin');
        setStatus('Refreshing portal data…');
        try {
          var res = await fetch(ingestUrl, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { Accept: 'application/json' },
          });
          var data = await res.json();
          if (!data.ok) {
            setStatus(data.error || 'Ingest failed', true);
            if (typeof showToast === 'function') showToast(data.error || 'Ingest failed', 'error');
          } else {
            setChunkCount(data.chunks || 0);
            setStatus('Ready · ' + (data.chunks || 0) + ' chunks indexed');
            if (typeof showToast === 'function') showToast('Nova data refreshed');
          }
        } catch (err) {
          setStatus('Network error while refreshing', true);
        } finally {
          ingestBtn.disabled = false;
          if (icon) icon.classList.remove('animate-spin');
        }
      });
    }

    var form = $('novaAskForm');
    if (form) {
      form.addEventListener('submit', async function (e) {
        e.preventDefault();
        var question = ($('novaQuestion').value || '').trim();
        if (!question) return;
        var btn = $('novaAskBtn');
        btn.disabled = true;
        setStatus('Thinking…');
        try {
          var res = await fetch(askUrl, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
            body: JSON.stringify({ question: question }),
          });
          var data = await res.json();
          if (!data.ok) {
            setStatus(data.error || 'Ask failed', true);
            return;
          }
          $('novaAnswer').textContent = data.answer || '';
          $('novaTools').textContent = (data.tools_used || []).join(' · ');
          var sources = $('novaSources');
          sources.innerHTML = '';
          (data.sources || []).forEach(function (s) {
            var chip = document.createElement('span');
            chip.className = 'inline-flex items-center rounded-md bg-cyan-50 text-cyan-700 ring-1 ring-cyan-100 px-2 py-0.5 text-[10px] font-medium';
            chip.textContent = (s.source || 'source') + (s.score != null ? ' · ' + s.score : '');
            sources.appendChild(chip);
          });
          var hasChart = data.chart && ((data.chart.labels || []).length || (data.chart.values || []).length);
          showChartEmpty(!hasChart);
          if (hasChart && typeof renderNovaChart === 'function') {
            renderNovaChart('novaChart', data.chart || {});
          }
          setStatus('');
          setChunkCount(($('novaChunkCount').textContent === '—') ? null : $('novaChunkCount').textContent);
          loadStatus();
        } catch (err) {
          setStatus('Network error while asking Nova', true);
        } finally {
          btn.disabled = false;
        }
      });
    }

    // Deep-link: /nova or ?nova=1 opens the panel
    try {
      var params = new URLSearchParams(window.location.search);
      if (params.get('nova') === '1') {
        openPanel();
        params.delete('nova');
        var next = window.location.pathname + (params.toString() ? '?' + params.toString() : '');
        window.history.replaceState({}, '', next);
      }
    } catch (e) { /* ignore */ }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }
})();
