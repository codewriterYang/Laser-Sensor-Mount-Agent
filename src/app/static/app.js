const API = '/api/v1';
let state = {
  stepFileId: null, productGraphId: null, processId: null,
  steps: [], approvedId: null, instructionId: null, currentStep: 0,
};

function toast(msg, type='success') {
  const t = document.createElement('div'); t.className = `toast ${type}`; t.textContent = msg;
  document.body.appendChild(t); setTimeout(() => t.remove(), 3000);
}

function setStep(n) {
  state.currentStep = n;
  const dots = [
    { id: 's1', step: 1 }, { id: 'r1', step: 2 },
    { id: 's3', step: 3 }, { id: 'r2', step: 4 },
    { id: 's5', step: 5 }, { id: 'r3', step: 6 },
    { id: 's7', step: 7 },
  ];
  for (const dot of dots) {
    const el = document.getElementById(dot.id);
    el.className = 'step-dot' + (dot.step < n ? ' done' : dot.step === n ? ' active' : '');
  }
}

// === 上传 STEP ===
async function uploadFile() {
  const file = document.getElementById('file-input').files[0];
  if (!file) return;
  const zone = document.getElementById('upload-zone');
  const text = document.getElementById('upload-text');
  text.innerHTML = '⏳ 正在解析 STEP 文件并生成 BOM 库，请稍候...';
  zone.style.opacity = '0.6';
  zone.style.pointerEvents = 'none';

  const form = new FormData(); form.append('file', file);
  try {
    const r = await fetch(`${API}/step/analyze`, { method: 'POST', body: form });
    const data = await r.json();
    if (!data.success) { toast(data.error.message, 'error'); text.textContent = '点击此处选择 .step 文件'; zone.style.opacity = '1'; zone.style.pointerEvents = ''; return; }

    state.productGraphId = data.data.productGraphId;
    state.stepFileId = data.data.stepFileId;
    state.uploadedFileName = file.name;

    zone.classList.add('done');
    zone.onclick = null;
    zone.style.opacity = '1';
    text.innerHTML = `✅ 已解析：${file.name}`;
    document.getElementById('upload-status').innerHTML =
      `<span class="badge badge-success">解析完成</span> <small style="color:var(--muted);margin-left:8px;">BOM 已自动生成</small>`;

    loadBomStats();
    // 新任务：解锁模式选择器
    document.querySelectorAll('input[name="imgMode"]').forEach(r => r.disabled = false);
    setStep(1);
    loadProductGraph();
  } catch(e) { toast('上传失败：' + e.message, 'error'); text.textContent = '点击此处选择 .step 文件'; zone.style.opacity = '1'; zone.style.pointerEvents = ''; }
}

// === 产品结构图 ===
async function loadProductGraph() {
  try {
    const r = await fetch(`${API}/product-graphs/${state.productGraphId}`);
    const data = await r.json();
    const pg = data.data;
    document.getElementById('pg-status').textContent = `${pg.nodes.length} 个节点，${pg.edges.length} 条边`;

    const nodeMap = {};
    pg.nodes.forEach(n => { nodeMap[n.nodeId] = { name: n.name, type: n.nodeType, quantity: n.quantity || 1, metadata: n.metadata || {} }; });
    const relMap = { 'contains': '包含', 'attached_to': '连接到', 'fastened_by': '被紧固于' };

    let nodesHtml = `<details open><summary>节点列表（${pg.nodes.length}）</summary><table>
      <tr><th>类型</th><th>名称</th><th style="text-align:center;">数量</th><th>特征</th></tr>`;
    pg.nodes.forEach(n => {
      const meta = n.metadata || {};
      const features = [];
      if (meta.faceCount) features.push(`${meta.faceCount}面`);
      if (meta.surfaceTypes && meta.surfaceTypes.length) features.push(meta.surfaceTypes.join('、'));
      if (meta.length) features.push(`${meta.length}×${meta.width}×${meta.height}mm`);
      const featureStr = features.length ? `<small style="color:var(--muted)">${features.join(' | ')}</small>` : '';
      nodesHtml += `<tr><td>${n.nodeType === 'assembly' ? '🔧 装配体' : '📦 零件'}</td><td>${n.name}</td><td style="text-align:center;">${n.quantity || 1}</td><td>${featureStr}</td></tr>`;
    });
    nodesHtml += '</table></details>';

    let edgesHtml = `<details style="margin-top:8px;"><summary>关系列表（${pg.edges.length}）</summary><table>
      <tr><th>源</th><th>关系</th><th>目标</th></tr>`;
    pg.edges.forEach(e => {
      const src = nodeMap[e.source] ? nodeMap[e.source].name : e.source.substring(0,8)+'...';
      const tgt = nodeMap[e.target] ? nodeMap[e.target].name : e.target.substring(0,8)+'...';
      edgesHtml += `<tr><td>${src}</td><td>${relMap[e.relation] || e.relation}</td><td>${tgt}</td></tr>`;
    });
    edgesHtml += '</table></details>';

    document.getElementById('pg-content').innerHTML = nodesHtml + edgesHtml;
    document.getElementById('card-graph').style.display = '';
    setStep(2);
  } catch(e) { toast('加载产品结构失败：' + e.message, 'error'); }
}

// === 第一阶段审核：产品结构 ===
async function reviewProductGraph(action) {
  if (action === 'reject') {
    if (!confirm('确认重新上传？当前数据将丢弃。')) return;
    resetAll();
    return;
  }
  try {
    const r = await fetch(`${API}/product-graphs/review`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ productGraphId: state.productGraphId, action: 'accept', reason: '确认' })
    });
    const data = await r.json();
    if (!data.success) { toast(data.error.message, 'error'); return; }

    document.getElementById('review1-panel').innerHTML =
      '<span class="badge badge-success">✅ 产品结构已确认</span>';
    document.getElementById('card-generate').style.display = '';
    setStep(3);
    toast('产品结构已确认');
  } catch(e) { toast('审核失败：' + e.message, 'error'); }
}

// === 生成装配流程 ===
async function generateProcess() {
  document.getElementById('btn-generate').disabled = true;
  document.getElementById('btn-generate').innerHTML = '<span class="spinner"></span> 正在生成...';

  try {
    const r = await fetch(`${API}/process/generate`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({productGraphId: state.productGraphId})
    });
    const data = await r.json();
    if (!data.success) { toast(data.error.message, 'error'); return; }

    state.processId = data.data.processId;
    state.steps = data.data.steps;
    document.getElementById('draft-content').innerHTML =
      `<p>状态：<span class="badge badge-warn">待审核</span> — 共 ${state.steps.length} 个步骤</p>` +
      `<table><tr><th>序号</th><th>标题</th><th>描述</th></tr>` +
      state.steps.map(s => `<tr><td>${s.sequence}</td><td>${s.title}</td><td>${s.description}</td></tr>`).join('') + '</table>';

    document.getElementById('btn-generate').style.display = 'none';
    // 关键修复：重置审核面板状态（回退后重新生成时）
    document.getElementById('review2-panel').style.display = '';
    document.getElementById('review-steps').style.display = '';
    document.getElementById('btn-submit').style.display = '';
    document.getElementById('review2-header').innerHTML =
      '<h4>🔍 第二阶段审核：装配流程</h4><p style="font-size:0.85rem;margin-bottom:8px;">对每个步骤选择操作：接受、修改或删除</p>';
    document.getElementById('review2-actions').style.display = '';
    document.getElementById('review-result').innerHTML = '';
    document.getElementById('card-instruction').style.display = 'none';
    buildReviewUI();
    setStep(4);
  } catch(e) { toast('生成失败：' + e.message, 'error'); }
  finally { document.getElementById('btn-generate').disabled = false; document.getElementById('btn-generate').textContent = '生成草稿工艺流程'; }
}

// === 第二阶段审核 ===
function buildReviewUI() {
  document.getElementById('review-steps').innerHTML = state.steps.map(s => `
    <div class="review-row" id="row-${s.stepId}">
      <span style="font-weight:600;width:24px;">${s.sequence}.</span>
      <div class="step-info"><strong>${s.title}</strong><br><small style="color:var(--muted)">${s.description}</small></div>
      <div style="display:flex;flex-direction:column;gap:4px;min-width:320px;">
        <select id="action-${s.stepId}" onchange="onActionChange('${s.stepId}')">
          <option value="accept">✅ 接受</option><option value="modify">✏️ 修改</option><option value="delete">🗑️ 删除</option>
        </select>
        <div id="modify-fields-${s.stepId}" style="display:none;flex-direction:column;gap:4px;">
          <input id="new-title-${s.stepId}" value="${s.title}" placeholder="新标题" style="padding:4px 8px;border:1px solid var(--border);border-radius:4px;font-size:0.85rem;">
          <textarea id="new-desc-${s.stepId}" placeholder="新描述" rows="2" style="padding:4px 8px;border:1px solid var(--border);border-radius:4px;font-size:0.85rem;resize:vertical;">${s.description}</textarea>
        </div>
        <div id="delete-confirm-${s.stepId}" style="display:none;color:var(--danger);font-size:0.8rem;">⚠️ 此步骤将被删除</div>
      </div>
    </div>
  `).join('');
}

function onActionChange(stepId) {
  const action = document.getElementById(`action-${stepId}`).value;
  document.getElementById(`modify-fields-${stepId}`).style.display = action === 'modify' ? 'flex' : 'none';
  document.getElementById(`delete-confirm-${stepId}`).style.display = action === 'delete' ? 'block' : 'none';
  const row = document.getElementById(`row-${stepId}`);
  row.style.background = action === 'delete' ? '#fee2e2' : action === 'modify' ? '#fef9c3' : '';
}

async function submitReview() {
  const decisions = state.steps.map(s => {
    const action = document.getElementById(`action-${s.stepId}`).value;
    const decision = { stepId: s.stepId, action };
    if (action === 'modify') {
      decision.reason = document.getElementById(`new-desc-${s.stepId}`).value || s.description;
      decision.newTitle = document.getElementById(`new-title-${s.stepId}`).value || s.title;
    } else { decision.reason = action === 'delete' ? '工程师删除此步骤' : '审核通过'; }
    return decision;
  });

  const modifyCount = decisions.filter(d => d.action === 'modify').length;
  const deleteCount = decisions.filter(d => d.action === 'delete').length;
  if (modifyCount > 0 || deleteCount > 0) {
    let msg = '确认提交审核结果？';
    if (modifyCount > 0) msg += `\n修改 ${modifyCount} 个步骤`;
    if (deleteCount > 0) msg += `\n删除 ${deleteCount} 个步骤`;
    if (!confirm(msg)) return;
  }

  try {
    const r = await fetch(`${API}/process/review`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({processId: state.processId, decisions})
    });
    const data = await r.json();
    if (!data.success) { toast(data.error.message, 'error'); return; }

    state.approvedId = data.data.approvedProcessId;
    document.getElementById('review2-header').innerHTML =
      '<span class="badge badge-success">✅ 装配流程已审核通过</span>';
    document.getElementById('review-steps').style.display = 'none';
    document.getElementById('review2-actions').style.display = 'none';

    // 关键修复：确保指导书卡片的渲染按钮可见
    document.getElementById('card-instruction').style.display = '';
    document.getElementById('render-actions').style.display = '';
    document.getElementById('btn-render').style.display = '';
    document.getElementById('instruction-content').innerHTML = '';
    document.getElementById('review3-panel').style.display = 'none';
    document.getElementById('card-pdf').style.display = 'none';

    setStep(5);
    toast('装配流程审核通过');
  } catch(e) { toast('审核失败：' + e.message, 'error'); }
}

function rollbackToProductGraph() {
  if (!confirm('确认回退到产品结构审核阶段？当前流程将丢弃。')) return;
  state.processId = null; state.steps = []; state.approvedId = null;
  document.getElementById('draft-content').innerHTML = '';
  document.getElementById('review2-panel').style.display = 'none';
  document.getElementById('review-result').innerHTML = '';
  document.getElementById('btn-generate').style.display = '';
  document.getElementById('card-instruction').style.display = 'none';
  setStep(2);
  toast('已回退到产品结构审核阶段');
}

function rollbackToProcessReview() {
  if (!confirm('确认回退？当前指导书将丢弃，需重新提交流程审核。')) return;
  state.instructionId = null; state.approvedId = null;
  document.getElementById('instruction-content').innerHTML = '';
  document.getElementById('review3-panel').style.display = 'none';
  document.getElementById('btn-render').style.display = '';
  document.getElementById('card-pdf').style.display = 'none';
  document.getElementById('card-instruction').style.display = 'none';
  // 重新显示流程审核
  document.getElementById('review2-header').innerHTML =
    '<h4>🔍 第二阶段审核：装配流程</h4><p style="font-size:0.85rem;margin-bottom:8px;">对每个步骤选择操作：接受、修改或删除</p>';
  document.getElementById('review2-actions').style.display = '';
  document.getElementById('review-steps').style.display = '';
  document.getElementById('btn-submit').style.display = '';
  document.getElementById('review-result').innerHTML = '';
  setStep(4);
  toast('已回退到流程审核阶段');
}

// === 渲染指导书（SSE 流式） ===
async function renderInstruction() {
  document.getElementById('btn-render').disabled = true;
  document.getElementById('btn-render').innerHTML = '<span class="spinner"></span> 正在渲染...';
  // 锁定模式选择器
  document.querySelectorAll('input[name="imgMode"]').forEach(r => r.disabled = true);
  const mode = document.querySelector('input[name="imgMode"]:checked')?.value || 'comparison';

  try {
    // 使用 SSE 流式端点
    const response = await fetch(`${API}/instruction/render-stream`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({approvedProcessId: state.approvedId, mode: mode})
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let instructionId = null;

    while (true) {
      const {done, value} = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, {stream: true});
      const lines = buffer.split('\n');
      buffer = lines.pop(); // 保留不完整的行

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const event = JSON.parse(line.slice(6));

          if (event.type === 'progress') {
            document.getElementById('btn-render').innerHTML =
              `<span class="spinner"></span> ${event.message}`;
          } else if (event.type === 'done') {
            instructionId = event.instructionId;
            toast(event.message);
          } else if (event.type === 'error') {
            toast(event.message, 'error');
          }
        } catch(e) { /* 忽略解析错误 */ }
      }
    }

    if (instructionId) {
      state.instructionId = instructionId;
      // 获取完整指导书并展示
      const r2 = await fetch(`${API}/instruction/${state.instructionId}`);
      const d2 = await r2.json();
      const sections = d2.data.sections;

      let html = `<h2 style="margin:16px 0 12px;">📄 装配指导书预览</h2>`;
      for (const s of sections) {
        const typeNames = { cover: '📋 封面', overview: '📖 概述', step: '🔧 装配步骤', safety: '⚠️ 安全须知', ending: '✅ 尾页' };
        html += `<div class="card" style="margin:8px 0;"><h3 style="font-size:0.9rem;color:var(--primary);">${typeNames[s.sectionType] || s.sectionType}</h3>`;
        for (const line of s.content.split('\n').filter(l => l.trim())) {
          html += `<p style="margin:4px 0;font-size:0.9rem;">${line}</p>`;
        }
        if (s.imagePath) {
          const imgUrl = '/' + s.imagePath.replace(/\\/g, '/') + '?t=' + Date.now();
          html += `<div style="margin:12px 0;text-align:center;"><img src="${imgUrl}" alt="步骤图" class="zoomable" onclick="openZoom(this)" style="max-width:100%;border:1px solid var(--border);border-radius:8px;"></div>`;
        }
        html += `</div>`;
      }

      document.getElementById('instruction-content').innerHTML = html;
      document.getElementById('render-actions').style.display = 'none';
      document.getElementById('review3-panel').style.display = '';
      // 同步模式选择器：渲染时用的模式 = 重新生成时的默认模式
      const usedMode = document.querySelector('input[name="imgMode"]:checked')?.value || 'comparison';
      const regenRadio = document.querySelector(`input[name="imgMode2"][value="${usedMode}"]`);
      if (regenRadio) regenRadio.checked = true;
      setStep(6);
    }
  } catch(e) { toast('渲染失败：' + e.message, 'error'); }
  finally {
    document.getElementById('btn-render').disabled = false;
    document.getElementById('btn-render').textContent = '渲染装配指导书';
    // 模式选择器保持锁定，直到重新上传 STEP 文件
  }
}

// === 第三阶段审核 ===
async function reviewInstruction(action) {
  if (action === 'reject') {
    if (!confirm('确认驳回？将回退到流程生成阶段。')) return;
    state.instructionId = null; state.approvedId = null;
    document.getElementById('instruction-content').innerHTML = '';
    document.getElementById('review3-panel').style.display = 'none';
    document.getElementById('card-pdf').style.display = 'none';
    document.getElementById('card-instruction').style.display = 'none';
    // 回退到流程生成
    document.getElementById('draft-content').innerHTML = '';
    document.getElementById('review2-panel').style.display = 'none';
    document.getElementById('review-result').innerHTML = '';
    document.getElementById('btn-generate').style.display = '';
    document.getElementById('card-generate').style.display = '';
    setStep(3);
    toast('已回退到流程生成阶段');
    return;
  }

  if (action === 'regenerate_images') {
    if (!confirm('确认重新生成图片？可能需要等待较长时间。')) return;
    const btn = document.getElementById('btn-regen');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> 正在重新生成图片，请稍候...';
    // 锁定模式选择器
    document.querySelectorAll('input[name="imgMode2"]').forEach(r => r.disabled = true);
    try {
      const mode = document.querySelector('input[name="imgMode2"]:checked')?.value || 'comparison';
      const r = await fetch(`${API}/instruction/review`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ instructionId: state.instructionId, action: 'regenerate_images', reason: '重新生成', mode: mode })
      });
      const data = await r.json();
      if (!data.success) { toast(data.error.message, 'error'); return; }

      state.instructionId = data.data.instructionId;
      const r2 = await fetch(`${API}/instruction/${state.instructionId}`);
      const d2 = await r2.json();
      const sections = d2.data.sections;
      let html = '';
      for (const s of sections) {
        const typeNames = { cover: '📋 封面', overview: '📖 概述', step: '🔧 装配步骤', safety: '⚠️ 安全须知', ending: '✅ 尾页' };
        html += `<div class="card" style="margin:8px 0;"><h3 style="font-size:0.9rem;color:var(--primary);">${typeNames[s.sectionType] || s.sectionType}</h3>`;
        for (const line of s.content.split('\n').filter(l => l.trim())) { html += `<p style="margin:4px 0;font-size:0.9rem;">${line}</p>`; }
        if (s.imagePath) {
          const imgUrl = '/' + s.imagePath.replace(/\\/g, '/') + '?t=' + Date.now();
          html += `<div style="margin:12px 0;text-align:center;"><img src="${imgUrl}" alt="步骤图" class="zoomable" onclick="openZoom(this)" style="max-width:100%;border:1px solid var(--border);border-radius:8px;"></div>`;
        }
        html += `</div>`;
      }
      document.getElementById('instruction-content').innerHTML = html;
      toast('图片已重新生成（模式：' + mode + '）');
    } catch(e) { toast('重新生成失败：' + e.message, 'error'); }
    finally {
      btn.disabled = false; btn.textContent = '🔄 重新生成图片';
      document.querySelectorAll('input[name="imgMode2"]').forEach(r => r.disabled = false);
    }
    return;
  }

  // approve
  try {
    const r = await fetch(`${API}/instruction/review`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ instructionId: state.instructionId, action: 'approve', reason: '确认' })
    });
    const data = await r.json();
    if (!data.success) { toast(data.error.message, 'error'); return; }

    document.getElementById('review3-header').innerHTML =
      '<span class="badge badge-success">✅ 指导书已确认</span>';
    document.getElementById('review3-actions').style.display = 'none';
    document.getElementById('card-pdf').style.display = '';
    setStep(7);
    toast('指导书审核通过');
  } catch(e) { toast('审核失败：' + e.message, 'error'); }
}

// === 导出 PDF（浏览器下载）===
async function exportPdf() {
  document.getElementById('btn-pdf').disabled = true;
  document.getElementById('btn-pdf').innerHTML = '<span class="spinner"></span> 正在导出...';

  try {
    const r = await fetch(`${API}/instruction/export-pdf`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({instructionId: state.instructionId})
    });
    const data = await r.json();
    if (!data.success) { toast(data.error.message, 'error'); return; }

    // 浏览器下载
    const downloadUrl = `${API}/instruction/${state.instructionId}/download-pdf`;
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = `装配指导书_${state.instructionId.substring(0,8)}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    document.getElementById('pdf-result').innerHTML =
      `<p><span class="badge badge-success">✅ PDF 已导出并开始下载</span></p>` +
      `<div class="actions" style="margin-top:12px;"><button class="btn btn-outline" onclick="resetAll()">🔄 开始新任务</button></div>`;
    setStep(8);
    toast('PDF 导出成功，正在下载...');
  } catch(e) { toast('PDF 导出失败：' + e.message, 'error'); }
  finally { document.getElementById('btn-pdf').disabled = false; document.getElementById('btn-pdf').textContent = '导出 PDF'; }
}

// === 重置（允许上传新文件）===
function resetAll() {
  state = { stepFileId: null, productGraphId: null, processId: null, steps: [], approvedId: null, instructionId: null, currentStep: 0 };

  // 重置上传区域
  const zone = document.getElementById('upload-zone');
  zone.classList.remove('done');
  zone.style.opacity = '1';
  zone.style.pointerEvents = '';
  zone.onclick = () => document.getElementById('file-input').click();
  document.getElementById('upload-text').textContent = '点击此处选择 .step 文件，或直接拖拽文件到此处';
  document.getElementById('upload-status').innerHTML = '';
  document.getElementById('file-input').value = '';

  // 隐藏所有后续卡片
  ['card-graph', 'card-generate', 'card-instruction', 'card-pdf'].forEach(id => {
    document.getElementById(id).style.display = 'none';
  });

  // 重置审核1
  document.getElementById('review1-panel').innerHTML = `
    <h4>🔍 第一阶段审核：产品结构</h4>
    <p style="font-size:0.85rem;margin-bottom:8px;">请确认产品结构图中的零件和关系是否正确。</p>
    <div class="actions"><button class="btn btn-success btn-sm" onclick="reviewProductGraph('accept')">✅ 确认结构正确</button>
    <button class="btn btn-danger btn-sm" onclick="reviewProductGraph('reject')">❌ 重新上传</button></div>`;

  // 重置生成流程
  document.getElementById('draft-content').innerHTML = '';
  document.getElementById('review2-panel').style.display = 'none';
  document.getElementById('review-result').innerHTML = '';
  document.getElementById('btn-generate').style.display = '';
  document.getElementById('review2-actions').style.display = '';

  // 重置指导书
  document.getElementById('instruction-content').innerHTML = '';
  document.getElementById('review3-panel').style.display = 'none';
  document.getElementById('render-actions').style.display = '';
  document.getElementById('btn-render').style.display = '';

  // 重置 PDF
  document.getElementById('pdf-result').innerHTML = '';

  setStep(0);
  toast('已重置，可以上传新文件');
}

// 拖拽上传
const zone = document.getElementById('upload-zone');
zone.addEventListener('dragover', e => { e.preventDefault(); zone.style.borderColor = 'var(--primary)'; });
zone.addEventListener('dragleave', () => zone.style.borderColor = 'var(--border)');
zone.addEventListener('drop', e => {
  e.preventDefault(); zone.style.borderColor = 'var(--border)';
  document.getElementById('file-input').files = e.dataTransfer.files;
  uploadFile();
});

// === 图片缩放 ===
let zoomLevel = 1;
function openZoom(img) {
  const overlay = document.getElementById('zoom-overlay');
  const zoomImg = document.getElementById('zoom-img');
  zoomImg.src = img.src;
  zoomLevel = 1;
  zoomImg.style.transform = 'scale(1)';
  overlay.classList.add('active');
  document.getElementById('zoom-controls').style.display = 'flex';
}
function closeZoom() {
  document.getElementById('zoom-overlay').classList.remove('active');
  document.getElementById('zoom-controls').style.display = 'none';
}
function zoomIn() {
  zoomLevel = Math.min(zoomLevel + 0.25, 5);
  document.getElementById('zoom-img').style.transform = `scale(${zoomLevel})`;
}
function zoomOut() {
  zoomLevel = Math.max(zoomLevel - 0.25, 0.25);
  document.getElementById('zoom-img').style.transform = `scale(${zoomLevel})`;
}
function zoomReset() {
  zoomLevel = 1;
  document.getElementById('zoom-img').style.transform = 'scale(1)';
}
// 鼠标滚轮缩放
document.getElementById('zoom-overlay').addEventListener('wheel', e => {
  e.preventDefault();
  if (e.deltaY < 0) zoomIn(); else zoomOut();
}, { passive: false });
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeZoom();
  if (e.key === '+' || e.key === '=') zoomIn();
  if (e.key === '-') zoomOut();
});

// === BOM 库管理 ===
async function loadBomStats() {
  const btn = document.getElementById('bom-refresh-btn');
  const origText = btn.textContent;
  btn.textContent = '⏳ 加载中...';
  btn.disabled = true;
  try {
    const r = await fetch(`${API}/bom/stats`);
    const data = await r.json();
    if (!data.success) return;
    const s = data.data;
    let detail = `<div style="display:flex;gap:16px;flex-wrap:wrap;">`;
    detail += `<span>🔩 材料: ${s.materials} 种</span>`;
    detail += `<span>⚙️ 标准件: ${s.standard_parts} 种</span>`;
    detail += `<span>📋 模板: ${s.part_templates} 种</span>`;
    detail += `</div>`;
    document.getElementById('bom-detail').innerHTML = detail;
    btn.textContent = '✅ 完成';
    setTimeout(() => { btn.textContent = origText; btn.disabled = false; }, 1500);
  } catch(e) {
    console.error('BOM stats error:', e);
    btn.textContent = '❌ 失败';
    setTimeout(() => { btn.textContent = origText; btn.disabled = false; }, 1500);
  }
}

async function exportBom() {
  try {
    const r = await fetch(`${API}/bom/export`);
    const data = await r.json();
    if (!data.success) { toast('导出失败', 'error'); return; }
    const blob = new Blob([JSON.stringify(data.data, null, 2)], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'bom_library.json'; a.click();
    URL.revokeObjectURL(url);
    toast('BOM 库已导出');
  } catch(e) { toast('导出失败：' + e.message, 'error'); }
}

async function importBom(input) {
  if (!input.files.length) return;
  const file = input.files[0];
  const formData = new FormData();
  formData.append('file', file);
  try {
    const r = await fetch(`${API}/bom/import`, { method: 'POST', body: formData });
    const data = await r.json();
    if (!data.success) { toast(data.error.message, 'error'); return; }
    const s = data.data.imported;
    toast(`导入成功：${s.materials} 材料, ${s.standard_parts} 标准件, ${s.part_templates} 模板`);
    loadBomStats();
  } catch(e) { toast('导入失败：' + e.message, 'error'); }
  input.value = '';
}

// 页面加载时获取 BOM 统计
loadBomStats();
