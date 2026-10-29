// ==========================================================================
// NightWise AI - Transformer Attention & Self-Attention Heatmap Explorer
// ==========================================================================

let attentionPayload = null;
let selectedTokenIndex = null;
let currentLayer = 0;
let currentHead = 'avg';

window.loadAttentionData = async function(text) {
  try {
    const res = await fetch('/api/attention', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text })
    });
    if (!res.ok) return;
    attentionPayload = await res.json();
    initAttentionView();
  } catch (err) {
    console.error("Error loading attention data:", err);
  }
};

function initAttentionView() {
  if (!attentionPayload) return;

  // 1. Populate Layer Selector
  const layerSel = document.getElementById('layer-select');
  layerSel.innerHTML = '';
  for (let i = 0; i < attentionPayload.num_layers; i++) {
    const opt = document.createElement('option');
    opt.value = i;
    opt.textContent = `Layer ${i} ${i === attentionPayload.num_layers - 1 ? '(Final Output)' : ''}`;
    layerSel.appendChild(opt);
  }
  layerSel.value = Math.min(attentionPayload.num_layers - 1, currentLayer);
  currentLayer = parseInt(layerSel.value);

  layerSel.onchange = (e) => {
    currentLayer = parseInt(e.target.value);
    drawHeatmaps();
  };

  document.getElementById('head-select').onchange = (e) => {
    currentHead = e.target.value;
    drawHeatmaps();
  };

  // 2. Render Tokens
  renderTokens();

  // 3. Render Focus Chips
  renderFocusChips();

  // 4. Render Architecture Specs
  renderArchSpecs();

  // 5. Draw Heatmap Canvases
  drawHeatmaps();
}

function renderTokens() {
  const container = document.getElementById('tokens-container');
  container.innerHTML = '';

  attentionPayload.tokens.forEach((tok, idx) => {
    const pill = document.createElement('div');
    pill.className = `token-pill ${idx === selectedTokenIndex ? 'active' : ''}`;
    pill.textContent = tok.replace(/Ġ/g, ' ').replace(/ /g, ' ');
    pill.onclick = () => selectToken(idx);
    container.appendChild(pill);
  });
}

function selectToken(idx) {
  selectedTokenIndex = idx;
  renderTokens();

  const tooltip = document.getElementById('token-tooltip');
  const token = attentionPayload.tokens[idx];
  tooltip.classList.remove('hidden');
  tooltip.innerHTML = `
    <strong>Token [${idx}]: "${token.trim()}"</strong><br>
    <em>Query (Q):</em> Seeking context from prior tokens.<br>
    <em>Key (K):</em> Matched against subsequent tokens.<br>
    <em>Value (V):</em> Information aggregated into the resulting representation.
  `;

  drawHeatmaps();
}

function renderFocusChips() {
  const container = document.getElementById('focus-chips');
  const items = attentionPayload.key_token_focus || [];
  if (!items.length) {
    container.innerHTML = `<span class="muted" style="font-size:11px;">Standard attention distribution active</span>`;
    return;
  }

  container.innerHTML = items.map(item => `
    <div class="focus-chip">
      <strong>${item.token}</strong>: ${item.score}% attention weight
    </div>
  `).join('');
}

function renderArchSpecs() {
  const container = document.getElementById('arch-specs');
  const arch = attentionPayload.architecture || {};
  container.innerHTML = `
    <div class="spec-item"><small>Hidden Dim (d_model)</small><b>${arch.hidden_size || 896}</b></div>
    <div class="spec-item"><small>Total Layers</small><b>${arch.num_hidden_layers || 24}</b></div>
    <div class="spec-item"><small>Attention Heads</small><b>${arch.num_attention_heads || 14}</b></div>
    <div class="spec-item"><small>KV Heads (GQA)</small><b>${arch.num_key_value_heads || 2}</b></div>
    <div class="spec-item"><small>Vocabulary</small><b>${arch.vocab_size || 151936}</b></div>
    <div class="spec-item"><small>RoPE Base</small><b>${arch.rope_theta || 1000000}</b></div>
  `;
}

function drawHeatmaps() {
  if (!attentionPayload) return;

  // 1. Draw Real HuggingFace Heatmap
  const hfCanvas = document.getElementById('hf-heatmap-canvas');
  const layerData = attentionPayload.layers[currentLayer] || attentionPayload.layers[0];
  let matrix = layerData.head_avg;
  if (currentHead !== 'avg') {
    const hIdx = parseInt(currentHead);
    if (layerData.heads && layerData.heads[hIdx]) {
      matrix = layerData.heads[hIdx];
    }
  }
  renderMatrixToCanvas(hfCanvas, matrix, attentionPayload.tokens, selectedTokenIndex);

  // 2. Draw Scratch PyTorch Heatmap
  const scratchCanvas = document.getElementById('scratch-heatmap-canvas');
  const scratchComp = attentionPayload.scratch_comparison;
  if (scratchComp) {
    let sMatrix = scratchComp.head_avg;
    if (currentHead !== 'avg') {
      const hIdx = parseInt(currentHead) % scratchComp.num_heads;
      sMatrix = scratchComp.heads[hIdx] || sMatrix;
    }
    renderMatrixToCanvas(scratchCanvas, sMatrix, attentionPayload.tokens, selectedTokenIndex);
  }
}

function renderMatrixToCanvas(canvas, matrix, tokens, highlightRow) {
  const ctx = canvas.getContext('2d');
  const N = matrix.length;
  if (!N) return;

  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const padding = 50;
  const cellW = (w - padding) / N;
  const cellH = (h - padding) / N;

  // Draw cells
  for (let i = 0; i < N; i++) {
    for (let j = 0; j < N; j++) {
      const val = matrix[i][j];
      const x = padding + j * cellW;
      const y = padding + i * cellH;

      // Color interpolation: dark navy -> cyan -> violet
      let r = Math.round(val * 168);
      let g = Math.round(val * 85 + (1 - val) * 15);
      let b = Math.round(val * 247 + (1 - val) * 35);

      if (highlightRow !== null && highlightRow === i) {
        // Highlight active Query row
        ctx.fillStyle = `rgb(${Math.min(255, r + 40)}, ${Math.min(255, g + 80)}, ${b})`;
      } else {
        ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
      }

      ctx.fillRect(x, y, cellW - 1, cellH - 1);
    }
  }

  // Draw Labels
  ctx.fillStyle = "#94a3b8";
  ctx.font = "9px monospace";
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";

  for (let i = 0; i < N; i++) {
    const tok = (tokens[i] || '').trim();
    const shortTok = tok.length > 5 ? tok.substring(0, 5) + '…' : tok;
    const y = padding + i * cellH + cellH / 2;
    ctx.fillText(shortTok, padding - 6, y);
  }

  // Draw Column headers rotated
  ctx.save();
  ctx.textAlign = "left";
  for (let j = 0; j < N; j++) {
    const tok = (tokens[j] || '').trim();
    const shortTok = tok.length > 5 ? tok.substring(0, 5) + '…' : tok;
    const x = padding + j * cellW + cellW / 2;
    ctx.save();
    ctx.translate(x, padding - 8);
    ctx.rotate(-Math.PI / 4);
    ctx.fillText(shortTok, 0, 0);
    ctx.restore();
  }
  ctx.restore();
}

// Initial load on page ready
window.addEventListener('load', () => {
  setTimeout(() => {
    window.loadAttentionData("I'm leaving office and walking home at 2 AM, show me the safest way.");
  }, 1500);
});
