let statusChart; let monthlyChart; let materialChart;
const statusOrder = ['VENCIDA', 'CRITICO', 'ALERTA', 'AVISO', 'ATENCAO', 'OK'];
const statusLabels = {VENCIDA:'Vencidas', CRITICO:'Crítico (7 dias)', ALERTA:'Alerta (15 dias)', AVISO:'Aviso (30 dias)', ATENCAO:'Atenção (60 dias)', OK:'Em dia'};
const statusColors = {VENCIDA:'#e31b54', CRITICO:'#f05a7f', ALERTA:'#e1a72c', AVISO:'#e8c55a', ATENCAO:'#6e69c8', OK:'#2e8c7d'};

function formatDate(value) { return new Intl.DateTimeFormat('pt-BR').format(new Date(`${value}T00:00:00`)); }
function formatDays(days) { const n = Number(days); return n < 0 ? `vencida há ${Math.abs(n)} dia(s)` : n === 0 ? 'vence hoje' : `${n} dia(s)`; }
function statusClass(status) { return `status-${status.toLowerCase()}`; }

function drawStatusChart(items) {
  const counts = Object.fromEntries(statusOrder.map(status => [status, 0]));
  items.forEach(item => { counts[item.status] = (counts[item.status] || 0) + 1; });
  const visible = statusOrder.filter(status => counts[status] > 0);
  if (statusChart) statusChart.destroy();
  statusChart = new Chart(document.getElementById('status-chart'), { type: 'doughnut', data: { labels: visible.map(s => statusLabels[s]), datasets: [{ data: visible.map(s => counts[s]), backgroundColor: visible.map(s => statusColors[s]), borderWidth: 0 }] }, options: { cutout: '73%', plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 7, padding: 14, font: { family: 'DM Sans', size: 10 } } } } } });
}
function drawMonthlyChart(items) {
  if (monthlyChart) monthlyChart.destroy();
  monthlyChart = new Chart(document.getElementById('monthly-chart'), { type: 'bar', data: { labels: items.map(i => i.ano_mes_vencimento), datasets: [{ label: 'Ferramentas', data: items.map(i => i.qtd_ferramentas), backgroundColor: '#25008f', borderRadius: 5, maxBarThickness: 34 }] }, options: { maintainAspectRatio: false, scales: { y: { beginAtZero: true, ticks: { precision: 0, color: '#777780' }, grid: { color: '#ececf0' } }, x: { ticks: { color: '#777780' }, grid: { display: false } } }, plugins: { legend: { display: false } } } });
}
function drawMaterialChart(items, selectedCode = '') {
  const selected = selectedCode ? items.filter(item => item.id === selectedCode) : items;
  const ordered = [...selected].sort((a, b) => Number(a.dias_para_vencer) - Number(b.dias_para_vencer));
  if (materialChart) materialChart.destroy();
  materialChart = new Chart(document.getElementById('material-chart'), { type: 'bar', data: { labels: ordered.map(i => `${i.id} - ${i.nome}`), datasets: [{ label: 'Dias para vencer', data: ordered.map(i => i.dias_para_vencer), backgroundColor: ordered.map(i => i.cor_status), borderRadius: 5, maxBarThickness: 28 }] }, options: { indexAxis: 'y', maintainAspectRatio: false, scales: { x: { grid: { color: '#edf1f0' }, ticks: { color: '#93a09f' } }, y: { grid: { display: false }, ticks: { color: '#526164', font: { size: 10 } } } }, plugins: { legend: { display: false }, tooltip: { callbacks: { label: context => { const item = ordered[context.dataIndex]; return ` ${formatDays(item.dias_para_vencer)} | ${statusLabels[item.status]}`; } } } } } });
}
function fillTable(items) {
  const actionable = items.filter(i => i.esta_vencida || i.vence_em_30_dias);
  const body = document.getElementById('products'); body.innerHTML = '';
  document.getElementById('empty').classList.toggle('hidden', actionable.length > 0);
  actionable.forEach(item => { const tr = document.createElement('tr'); const daysClass = item.dias_para_vencer < 0 ? 'days-expired' : 'days-warning'; tr.innerHTML = `<td>${item.nome}<span class="product-code">${item.codigo}</span></td><td>${item.categoria}</td><td>${item.localizacao}</td><td>${formatDate(item.data_validade)}</td><td class="${daysClass}">${formatDays(item.dias_para_vencer)}</td><td><span class="status ${statusClass(item.status)}">${statusLabels[item.status]}</span></td>`; body.appendChild(tr); });
}
async function loadDashboard() {
  const category = document.getElementById('category-filter').value;
  const response = await fetch(`/api/dashboard${category ? `?categoria=${encodeURIComponent(category)}` : ''}`);
  if (!response.ok) throw new Error('Não foi possível carregar os dados');
  const data = await response.json(); const k = data.kpis;
  document.getElementById('total').textContent = k.total_ferramentas; document.getElementById('expired').textContent = k.qtd_vencidas; document.getElementById('thirty').textContent = k.qtd_vencendo_30d; document.getElementById('compliance').textContent = `${k.perc_conformidade}%`; document.getElementById('healthy-total').textContent = k.qtd_ok; document.getElementById('updated').textContent = `Atualizado em ${formatDate(data.atualizado_em)}`;
  const expired = Number(k.qtd_vencidas); const due = Number(k.qtd_vencendo_30d); const banner = document.getElementById('critical-banner'); banner.classList.toggle('hidden', expired === 0 && due === 0); document.getElementById('critical-title').textContent = expired ? `${expired} produto(s) vencido(s) exigem ação imediata` : 'Renovações próximas'; document.getElementById('critical-copy').textContent = expired ? `${due} item(ns) também estão dentro da janela de alerta de 30 dias.` : `${due} produto(s) vencem nos próximos 30 dias.`;
  const selector = document.getElementById('category-filter'); const current = selector.value; selector.innerHTML = '<option value="">Todas as categorias</option>' + data.categorias.map(c => `<option>${c}</option>`).join(''); selector.value = current;
  const materialSelector = document.getElementById('material-filter'); const selectedMaterial = materialSelector.value; materialSelector.innerHTML = '<option value="">Todos os materiais</option>' + data.ferramentas.map(item => `<option value="${item.id}">${item.id} - ${item.nome}</option>`).join(''); materialSelector.value = data.ferramentas.some(item => item.id === selectedMaterial) ? selectedMaterial : '';
  drawStatusChart(data.ferramentas); drawMonthlyChart(data.meses); drawMaterialChart(data.ferramentas, materialSelector.value); fillTable(data.ferramentas);
}
document.getElementById('refresh').addEventListener('click', loadDashboard); document.getElementById('category-filter').addEventListener('change', loadDashboard); document.getElementById('material-filter').addEventListener('change', () => { const category = document.getElementById('category-filter').value; loadDashboard(category); }); document.getElementById('export-excel').addEventListener('click', () => { const category = document.getElementById('category-filter').value; window.location.href = `/exportar/excel${category ? `?categoria=${encodeURIComponent(category)}` : ''}`; }); loadDashboard().catch(error => { document.getElementById('updated').textContent = 'Banco indisponível'; console.error(error); }); setInterval(() => loadDashboard().catch(error => console.error('Atualização automática:', error)), 60000);
