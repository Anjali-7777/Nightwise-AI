// ==========================================================================
// safeMap - Frontend Application Controller
// OpenStreetMap Primary Engine, OpenFreeMap Vector Tiles & 9-Row Breakdown
// ==========================================================================

let map = null;
let isMapReady = false;
let fallbackAttempted = false;
let currentRoutes = [];
let selectedRouteIndex = 0;
let currentPlaces = [];
let currentCameras = [];
let mapMarkers = [];
let activeComponentFilter = null;

const CATEGORY_COLORS = {
  police: "#3b82f6",
  hospital: "#ef4444",
  pharmacy: "#10b981",
  petrol_pump: "#f97316",
  shop: "#eab308",
  transport: "#a855f7",
  cameras: "#cbd5e1"
};

// Fallback Standalone Carto Dark Raster Style
const CARTO_DARK_STYLE = {
  version: 8,
  sources: {
    'carto-dark': {
      type: 'raster',
      tiles: [
        'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
        'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
        'https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'
      ],
      tileSize: 256,
      attribution: '&copy; OpenStreetMap contributors &copy; CARTO'
    }
  },
  layers: [
    {
      id: 'carto-dark-layer',
      type: 'raster',
      source: 'carto-dark',
      minzoom: 0,
      maxzoom: 20
    }
  ]
};

// --- Map Initialization with OpenFreeMap Vector Tiles & Robust Fallbacks ---
async function initMap() {
  let mapStyle = "https://tiles.openfreemap.org/styles/dark";

  try {
    const cfgRes = await fetch('/api/config');
    if (cfgRes.ok) {
      const cfg = await cfgRes.json();
      if (cfg.primary_map_style) {
        mapStyle = cfg.primary_map_style;
      }
      const pill = document.getElementById('model-status-pill');
      if (pill) {
        pill.textContent = "● OpenStreetMap Active | Model Ready";
        pill.style.borderColor = "rgba(56, 189, 248, 0.4)";
        pill.style.color = "#38bdf8";
      }
    }
  } catch (err) {
    console.warn("Using fallback map style:", err);
  }

  try {
    map = new maplibregl.Map({
      container: 'map',
      style: mapStyle,
      center: [79.0882, 21.1458], // Nagpur / Central India default
      zoom: 12
    });

    map.addControl(new maplibregl.NavigationControl(), 'top-right');

    map.on('load', () => {
      isMapReady = true;
      map.resize();
      if (currentRoutes && currentRoutes.length) {
        updateMapDisplay();
      }
    });

    map.on('error', (e) => {
      console.warn("MapLibre event error:", e);
      if (!fallbackAttempted) {
        fallbackAttempted = true;
        try {
          map.setStyle(CARTO_DARK_STYLE);
        } catch (stErr) {
          console.error("Failed setting fallback style:", stErr);
        }
      }
    });

    // Safety timeout: if after 3s style is still not ready, switch to Carto Dark raster
    setTimeout(() => {
      if (!isMapReady && !fallbackAttempted) {
        console.warn("Primary vector style load timeout, switching to Carto Dark raster...");
        fallbackAttempted = true;
        try {
          map.setStyle(CARTO_DARK_STYLE);
        } catch (e) {}
      }
    }, 3000);

  } catch (err) {
    console.error("Map creation error:", err);
    try {
      map = new maplibregl.Map({
        container: 'map',
        style: CARTO_DARK_STYLE,
        center: [79.0882, 21.1458],
        zoom: 12
      });
      map.on('load', () => {
        isMapReady = true;
        map.resize();
      });
    } catch (e2) {
      console.error("Fatal map initialization failure:", e2);
    }
  }

  window.addEventListener('resize', () => {
    if (map) {
      try { map.resize(); } catch (e) {}
    }
  });
}

// --- Live Autocomplete Search (Geoapify) ---
function setupAutocomplete(inputId, dropdownId) {
  const input = document.getElementById(inputId);
  const dropdown = document.getElementById(dropdownId);
  if (!input || !dropdown) return;

  let debounceTimer = null;

  input.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    const q = input.value.trim();
    if (q.length < 2) {
      dropdown.classList.add('hidden');
      dropdown.innerHTML = '';
      return;
    }

    debounceTimer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/geocode?q=${encodeURIComponent(q)}`);
        if (!res.ok) return;
        const data = await res.json();
        const results = data.results || [];
        if (!results.length) {
          dropdown.classList.add('hidden');
          return;
        }

        dropdown.innerHTML = results.map(item => `
          <div class="autocomplete-item" data-name="${item.name.replace(/"/g, '&quot;')}" data-lat="${item.lat}" data-lon="${item.lon}">
            <strong>${item.name}</strong>
            <small>${item.provider === 'canonical_gazetteer' ? '✦ Verified Landmark' : 'OpenStreetMap'} • ${item.address || ''}</small>
          </div>
        `).join('');

        dropdown.classList.remove('hidden');

        dropdown.querySelectorAll('.autocomplete-item').forEach(el => {
          el.addEventListener('click', () => {
            input.value = el.dataset.name;
            dropdown.classList.add('hidden');
            if (map && el.dataset.lat && el.dataset.lon) {
              map.flyTo({ center: [parseFloat(el.dataset.lon), parseFloat(el.dataset.lat)], zoom: 14 });
            }
          });
        });
      } catch (err) {
        console.error("Autocomplete error:", err);
      }
    }, 250);
  });

  document.addEventListener('click', (e) => {
    if (!input.contains(e.target) && !dropdown.contains(e.target)) {
      dropdown.classList.add('hidden');
    }
  });
}

// --- Tab Switching ---
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
    
    btn.classList.add('active');
    const targetId = btn.dataset.tab;
    const targetContent = document.getElementById(targetId);
    if (targetContent) targetContent.classList.remove('hidden');

    if (targetId === 'nav-panel' && map) {
      setTimeout(() => map.resize(), 200);
    }
  });
});

// --- Mode Toggle ---
document.querySelectorAll('.mode-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  });
});

function getSelectedMode() {
  const activeBtn = document.querySelector('.mode-btn.active');
  return activeBtn ? activeBtn.dataset.mode : 'walking';
}

function setOrigin(val) {
  document.getElementById('origin-input').value = val;
}

function setDest(val) {
  document.getElementById('dest-input').value = val;
}

function useCurrentLocation(field) {
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(pos => {
      const lat = pos.coords.latitude.toFixed(4);
      const lon = pos.coords.longitude.toFixed(4);
      const input = document.getElementById(field === 'origin' ? 'origin-input' : 'dest-input');
      if (input) input.value = `Current Location (${lat}, ${lon})`;
    }, () => {
      alert("Unable to retrieve GPS location.");
    });
  }
}

// --- Voice Recognition (Web Speech API) ---
const micBtn = document.getElementById('mic-btn');
let recognition = null;
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRec();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = 'en-IN';

  recognition.onstart = () => micBtn.classList.add('recording');
  recognition.onend = () => micBtn.classList.remove('recording');
  recognition.onresult = (e) => {
    const transcript = e.results[0][0].transcript;
    document.getElementById('agent-input').value = transcript;
    triggerAgentQuery();
  };
  recognition.onerror = () => micBtn.classList.remove('recording');
}

if (micBtn) {
  micBtn.addEventListener('click', () => {
    if (!recognition) {
      alert("Speech recognition not supported in this browser. Please type your query.");
      return;
    }
    try {
      recognition.start();
    } catch (err) {
      recognition.stop();
    }
  });
}

// --- API Execution ---
async function triggerAgentQuery() {
  const query = document.getElementById('agent-input').value.trim();
  if (!query) {
    triggerStructuredRouting();
    return;
  }

  const sendBtn = document.getElementById('send-agent-btn');
  sendBtn.textContent = "Calculating…";
  sendBtn.disabled = true;

  try {
    const res = await fetch('/api/agent', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: query,
        saved_places: {
          home: 'Indiranagar, Bengaluru',
          office: 'Church Street, Bengaluru'
        }
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Agent planning failed");
    }

    const data = await res.json();
    renderWorkflowResults(data);

    if (window.loadAttentionData) {
      window.loadAttentionData(query);
    }
  } catch (err) {
    alert("Planning Error: " + err.message);
  } finally {
    sendBtn.textContent = "Compare Routes ➔";
    sendBtn.disabled = false;
  }
}

async function triggerStructuredRouting() {
  const origin = document.getElementById('origin-input').value.trim();
  const destination = document.getElementById('dest-input').value.trim();
  const mode = getSelectedMode();
  const depTime = document.getElementById('dep-time-input').value.trim();

  if (!origin || !destination) {
    alert("Please enter both Origin and Destination.");
    return;
  }

  const sendBtn = document.getElementById('send-agent-btn');
  sendBtn.textContent = "Calculating…";
  sendBtn.disabled = true;

  try {
    const res = await fetch('/api/routes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        origin: origin,
        destination: destination,
        mode: mode,
        departure_time: depTime
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Routing failed");
    }

    const data = await res.json();
    renderWorkflowResults(data);

    if (window.loadAttentionData) {
      window.loadAttentionData(`Navigate from ${origin} to ${destination} by ${mode} at ${depTime}`);
    }
  } catch (err) {
    alert("Routing Error: " + err.message);
  } finally {
    sendBtn.textContent = "Compare Routes ➔";
    sendBtn.disabled = false;
  }
}

document.getElementById('send-agent-btn').addEventListener('click', triggerAgentQuery);
document.getElementById('agent-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') triggerAgentQuery();
});

['origin-input', 'dest-input', 'dep-time-input'].forEach(id => {
  const el = document.getElementById(id);
  if (el) {
    el.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') triggerStructuredRouting();
    });
  }
});

window.setOrigin = setOrigin;
window.setDest = setDest;
window.triggerStructuredRouting = triggerStructuredRouting;
window.triggerAgentQuery = triggerAgentQuery;

// --- Render Routes & Markers ---
function renderWorkflowResults(data) {
  currentRoutes = data.routes || [];
  currentPlaces = data.corridor_places || [];
  currentCameras = data.corridor_cameras || [];
  selectedRouteIndex = 0;
  activeComponentFilter = null;

  // Sync inputs with resolved place names
  if (data.origin && data.origin.name) {
    const oInp = document.getElementById('origin-input');
    if (oInp && data.parsed) oInp.value = data.origin.name;
  }
  if (data.destination && data.destination.name) {
    const dInp = document.getElementById('dest-input');
    if (dInp && data.parsed) dInp.value = data.destination.name;
  }

  // 1. Data Confidence Badge & Sparse Banner
  const confBadge = document.getElementById('confidence-badge');
  if (confBadge) {
    const conf = data.data_confidence || 'High';
    confBadge.textContent = `● ${conf} Data Confidence`;
    confBadge.className = `confidence-badge badge-${conf.toLowerCase()}`;
  }

  const sparseBanner = document.getElementById('sparse-data-banner');
  if (sparseBanner) {
    if (data.data_confidence === 'Low' || data.confidence_warning) {
      sparseBanner.classList.remove('hidden');
    } else {
      sparseBanner.classList.add('hidden');
    }
  }

  // 2. Agent Explanation & Trace (optional)
  const agentBox = document.getElementById('agent-explanation-box');
  const summaryText = document.getElementById('agent-summary-text');
  const traceList = document.getElementById('agent-trace-list');
  
  if (agentBox && data.trade_off_summary) {
    agentBox.classList.remove('hidden');
    if (summaryText) summaryText.textContent = data.trade_off_summary;
    if (traceList && data.trace && data.trace.length) {
      traceList.innerHTML = data.trace.map(t => `<div>• ${t}</div>`).join('');
    }
  }

  // 3. Comparison Banner with Biggest Difference Component
  const banner = document.getElementById('comparison-banner');
  const headline = document.getElementById('banner-headline');
  const detail = document.getElementById('banner-detail');
  
  if (currentRoutes.length >= 2) {
    banner.classList.remove('hidden');
    const fastest = currentRoutes.find(r => r.id === data.fastest_route_id) || currentRoutes[0];
    const safest = currentRoutes.find(r => r.id === data.safest_route_id) || currentRoutes[1];
    const tradeOff = data.trade_off || {};
    
    if (fastest.id === safest.id) {
      headline.textContent = `${fastest.name} is both Fastest and Safest!`;
      detail.textContent = `Achieves highest score (${fastest.night_score}/100) with minimal travel time.`;
    } else {
      const extraMin = Math.round((safest.duration_s - fastest.duration_s) / 60);
      headline.textContent = `Trade-off: ${safest.name} takes ${extraMin} min longer`;
      detail.textContent = `Score +${Math.round(safest.night_score - fastest.night_score)} pts. Mainly because of higher ${tradeOff.biggest_diff_component || 'environmental support'} (+${tradeOff.biggest_diff_points || 0} pts) and ${safest.metrics.open_places_count} open venues.`;
    }
  } else {
    banner.classList.add('hidden');
  }

  // 4. Render Route Cards with SVG Gauge & 9-Row Breakdown
  renderRouteCards();

  // 5. Update Map Layers & Markers
  updateMapDisplay();
}

function renderRouteCards() {
  const container = document.getElementById('route-cards-container');
  if (!currentRoutes.length) {
    container.innerHTML = `<div class="placeholder-card">No routes available.</div>`;
    return;
  }

  container.innerHTML = currentRoutes.map((r, i) => {
    const isSelected = i === selectedRouteIndex;
    const durMin = Math.round(r.duration_s / 60);
    const distKm = (r.distance_m / 1000).toFixed(1);
    
    // Score Badge Color
    let scoreClass = "score-mid";
    if (r.night_score >= 70) scoreClass = "score-high";
    else if (r.night_score < 45) scoreClass = "score-low";

    // Badges
    const badgeHtml = (r.labels || []).map(l => 
      `<span class="route-tag ${l === 'Safest' ? 'tag-safest' : 'tag-fastest'}">${l}</span>`
    ).join('');

    // SVG Circular Gauge calculation (circumference = 2 * PI * 42 ≈ 264)
    const circumference = 264;
    const strokeDashoffset = Math.round(circumference - (circumference * r.night_score / 100));

    // 9-Row Breakdown HTML
    const b = r.breakdown || {};
    const rowsHtml = Object.entries(b).map(([k, v]) => `
      <div class="breakdown-row ${activeComponentFilter === k ? 'active' : ''}" onclick="event.stopPropagation(); highlightComponent('${k}', ${i})">
        <span class="comp-circle">${v.component_id || '•'}</span>
        <div class="comp-info">
          <div class="comp-title">
            <span>${v.name}</span>
          </div>
          <p class="comp-note">${v.note}</p>
        </div>
        <span class="comp-pts ${!v.available ? 'pts-unavailable' : ''}">
          ${v.available ? `${v.points} / ${v.max_points} pts` : 'Data unavailable'}
        </span>
      </div>
    `).join('');

    return `
      <article class="route-card ${isSelected ? 'selected' : ''}" onclick="selectRoute(${i})">
        <div class="card-top-row">
          <div>
            <div class="card-badges">${badgeHtml}</div>
            <h3 style="margin-top:4px;">${r.name}</h3>
            <div style="font-size:11px; color:#94a3b8; margin-top:2px;">
              ${r.source === 'osrm' ? '✦ OpenStreetMap Routing' : 'OSM Parallel Corridor'}
            </div>
          </div>
          
          <!-- Circular SVG Gauge -->
          <div class="gauge-wrapper">
            <svg class="score-gauge" viewBox="0 0 100 100">
              <circle class="gauge-bg" cx="50" cy="50" r="42" />
              <circle class="gauge-fill ${scoreClass}" cx="50" cy="50" r="42" style="stroke-dashoffset: ${strokeDashoffset};" />
            </svg>
            <div class="gauge-text">
              <span class="gauge-score">${r.night_score}</span>
              <span class="gauge-max">/100</span>
            </div>
          </div>
        </div>

        <div class="metrics-grid">
          <div class="metric-item"><small>Duration</small><b>${durMin} min</b></div>
          <div class="metric-item"><small>Distance</small><b>${distKm} km</b></div>
          <div class="metric-item"><small>Open Venues</small><b>${r.metrics.open_places_count}</b></div>
          <div class="metric-item"><small>Cameras</small><b>${r.metrics.cameras_count}</b></div>
          <div class="metric-item"><small>Street Lamps</small><b>${r.metrics.street_lamps_count}</b></div>
          <div class="metric-item"><small>Dark Gap</small><b>${Math.round(r.metrics.longest_dark_gap_m)} m</b></div>
        </div>

        <!-- 9-Row Deterministic Breakdown -->
        <div class="breakdown-glass-card">
          <div class="breakdown-header-title">
            <span>What goes into this score</span>
            <small>Tap row to highlight</small>
          </div>
          <div class="breakdown-list">
            ${rowsHtml}
          </div>
        </div>
      </article>
    `;
  }).join('');
}

function selectRoute(index) {
  selectedRouteIndex = index;
  activeComponentFilter = null;
  renderRouteCards();
  updateMapDisplay();
}

function highlightComponent(compKey, routeIndex) {
  if (selectedRouteIndex !== routeIndex) {
    selectedRouteIndex = routeIndex;
  }
  activeComponentFilter = (activeComponentFilter === compKey) ? null : compKey;
  renderRouteCards();
  updateMapRouteHighlight();
}

// Toggle Trace (optional)
const toggleTraceBtn = document.getElementById('toggle-trace-btn');
if (toggleTraceBtn) {
  toggleTraceBtn.addEventListener('click', () => {
    const trace = document.getElementById('agent-trace-list');
    if (trace) {
      trace.classList.toggle('hidden');
      toggleTraceBtn.textContent = trace.classList.contains('hidden') ? 'View reasoning trace ▾' : 'Hide reasoning trace ▴';
    }
  });
}

// --- Map Update Helpers ---
function updateMapDisplay() {
  if (!map) return;
  if (!isMapReady && !map.isStyleLoaded()) {
    setTimeout(updateMapDisplay, 200);
    return;
  }
  try { map.resize(); } catch(e){}

  // Clear existing markers
  mapMarkers.forEach(m => m.remove());
  mapMarkers = [];

  // Remove existing route layers and sources
  ['route-alt-0', 'route-alt-1', 'route-alt-2', 'route-dark-gap'].forEach(id => {
    if (map.getLayer(id)) map.removeLayer(id);
    if (map.getSource(id)) map.removeSource(id);
  });

  if (!currentRoutes.length) return;

  // Add route polylines
  currentRoutes.forEach((r, idx) => {
    const geojson = {
      type: 'Feature',
      geometry: {
        type: 'LineString',
        coordinates: r.coordinates.map(pt => [pt[1], pt[0]])
      }
    };

    const isSelected = idx === selectedRouteIndex;
    const color = isSelected ? '#38bdf8' : (idx === 1 ? '#a855f7' : '#94a3b8');

    map.addSource(`route-alt-${idx}`, { type: 'geojson', data: geojson });
    map.addLayer({
      id: `route-alt-${idx}`,
      type: 'line',
      source: `route-alt-${idx}`,
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: {
        'line-color': color,
        'line-width': isSelected ? 6 : 4,
        'line-opacity': isSelected ? 1.0 : 0.4
      }
    });
  });

  // Fit bounds to selected route
  const selRoute = currentRoutes[selectedRouteIndex];
  if (selRoute && selRoute.coordinates && selRoute.coordinates.length) {
    const selCoords = selRoute.coordinates;
    const bounds = new maplibregl.LngLatBounds();
    selCoords.forEach(c => bounds.extend([c[1], c[0]]));
    try {
      map.fitBounds(bounds, { padding: 60, maxZoom: 16 });
    } catch(e) {}
  }

  // Add Place Pins with Arrival-Time Dimming
  currentPlaces.forEach(p => {
    // If filtering by component, filter appropriately
    if (activeComponentFilter === 'cameras') return;
    if (activeComponentFilter === 'help_points' && !p.is_help_point) return;
    if (activeComponentFilter === 'open_places' && !p.is_open_at_arrival) return;

    const el = document.createElement('div');
    el.className = 'place-marker-pin';
    const catColor = CATEGORY_COLORS[p.category] || "#eab308";
    el.style.backgroundColor = catColor;
    el.style.width = "12px";
    el.style.height = "12px";
    el.style.borderRadius = "50%";
    el.style.border = "2px solid #ffffff";
    el.style.boxShadow = "0 2px 6px rgba(0,0,0,0.6)";
    // Dim places closed at arrival time
    el.style.opacity = p.is_open_at_arrival !== false ? "1.0" : "0.35";

    const popupHtml = `
      <div style="color:#000; font-size:12px;">
        <strong>${p.name}</strong><br>
        <span style="color:#666;">${p.display_category}</span><br>
        <span>Hours: ${p.opening_hours || 'Not mapped (unknown)'}</span><br>
        <span>Status at arrival: <b>${p.is_open_at_arrival ? '🟢 Open' : (p.is_24x7 ? '🟢 24/7' : '⚪ Closed / Reduced weight')}</b></span>
      </div>
    `;

    const marker = new maplibregl.Marker({ element: el })
      .setLngLat([p.lon, p.lat])
      .setPopup(new maplibregl.Popup({ offset: 15 }).setHTML(popupHtml))
      .addTo(map);

    mapMarkers.push(marker);
  });

  // Add Camera Pins
  if (!activeComponentFilter || activeComponentFilter === 'cameras') {
    currentCameras.forEach(c => {
      const el = document.createElement('div');
      el.className = 'camera-marker-pin';
      el.innerHTML = "📹";
      el.style.fontSize = "14px";
      el.style.filter = "drop-shadow(0 2px 4px rgba(0,0,0,0.8))";

      const popupHtml = `
        <div style="color:#000; font-size:12px;">
          <strong>Surveillance Camera</strong><br>
          <span>Type: ${c.type || 'CCTV'}</span><br>
          <span>Operator: ${c.operator || 'Public / Safe City'}</span>
        </div>
      `;

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([c.lon, c.lat])
        .setPopup(new maplibregl.Popup({ offset: 15 }).setHTML(popupHtml))
        .addTo(map);

      mapMarkers.push(marker);
    });
  }
}

function updateMapRouteHighlight() {
  currentRoutes.forEach((_, idx) => {
    const layerId = `route-alt-${idx}`;
    if (map.getLayer(layerId)) {
      const isSelected = idx === selectedRouteIndex;
      let color = isSelected ? '#38bdf8' : (idx === 1 ? '#a855f7' : '#94a3b8');
      
      // If gaps component is active, highlight in alert amber/red
      if (isSelected && activeComponentFilter === 'gaps') {
        color = '#ef4444';
      }

      map.setPaintProperty(layerId, 'line-color', color);
      map.setPaintProperty(layerId, 'line-width', isSelected ? 6 : 4);
      map.setPaintProperty(layerId, 'line-opacity', isSelected ? 1.0 : 0.35);
    }
  });

  // Re-render markers based on active component filter
  updateMapDisplay();
}

// Initial Map Setup
window.addEventListener('load', () => {
  initMap();
  setupAutocomplete('origin-input', 'origin-autocomplete');
  setupAutocomplete('dest-input', 'dest-autocomplete');

  if (window.location.hash === '#attention' || window.location.hash === '#attn') {
    const tabBtn = document.getElementById('tab-attn-btn');
    if (tabBtn) tabBtn.click();
  }

  // Support preloading routes via URL query parameters
  const urlParams = new URLSearchParams(window.location.search);
  const qOrigin = urlParams.get('origin');
  const qDest = urlParams.get('dest') || urlParams.get('destination');
  const qMode = urlParams.get('mode');
  const qAgent = urlParams.get('q');

  if (qOrigin) document.getElementById('origin-input').value = qOrigin;
  if (qDest) document.getElementById('dest-input').value = qDest;
  if (qMode) {
    document.querySelectorAll('.mode-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.mode === qMode);
    });
  }

  if (qAgent) {
    document.getElementById('agent-input').value = qAgent;
    setTimeout(() => { triggerAgentQuery(); }, 1200);
  } else {
    // Run initial route calculation to populate dashboard
    setTimeout(() => {
      triggerStructuredRouting();
    }, 1000);
  }
});
