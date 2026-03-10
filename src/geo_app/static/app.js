const map = new maplibregl.Map({
    container: 'map',
    style: { version: 8, sources: {}, layers: [
        { id: 'bg', type: 'background', paint: { 'background-color': '#0a0a23' } }
    ]},
    center: [0, 20],
    zoom: 2,
});

map.addControl(new maplibregl.NavigationControl());

const activeLayers = new Set();
let popup = null;

function setStatus(msg) {
    document.getElementById('status').textContent = msg;
}

// Fetch and populate built-in datasets
async function loadBuiltinOptions() {
    try {
        const resp = await fetch('/api/builtins/available');
        const data = await resp.json();
        const select = document.getElementById('builtinSelect');
        select.innerHTML = '';
        data.forEach(d => {
            const opt = document.createElement('option');
            opt.value = d.id;
            opt.textContent = d.name;
            select.appendChild(opt);
        });
    } catch (e) {
        setStatus('Failed to load built-in list');
    }
}

async function loadBuiltin() {
    const select = document.getElementById('builtinSelect');
    const datasetId = select.value;
    if (!datasetId) return;

    const btn = document.getElementById('loadBuiltinBtn');
    btn.disabled = true;
    setStatus(`Loading ${datasetId}...`);

    try {
        const resp = await fetch('/api/builtins/load', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dataset: datasetId }),
        });
        if (!resp.ok) throw new Error((await resp.json()).detail || 'Load failed');
        const data = await resp.json();
        setStatus(`Loaded ${data.dataset_name} (${data.feature_count} features)`);
        await refreshDatasets();
        await loadDatasetOnMap(data.dataset_name);
    } catch (e) {
        setStatus(`Error: ${e.message}`);
    } finally {
        btn.disabled = false;
    }
}

async function uploadFile() {
    const input = document.getElementById('fileInput');
    if (!input.files.length) return;

    const btn = document.getElementById('uploadBtn');
    btn.disabled = true;
    setStatus('Uploading...');

    const form = new FormData();
    form.append('file', input.files[0]);

    try {
        const resp = await fetch('/api/ingest/upload', { method: 'POST', body: form });
        if (!resp.ok) throw new Error((await resp.json()).detail || 'Upload failed');
        const data = await resp.json();
        setStatus(`Uploaded ${data.dataset_name} (${data.feature_count} features)`);
        await refreshDatasets();
        await loadDatasetOnMap(data.dataset_name);
    } catch (e) {
        setStatus(`Error: ${e.message}`);
    } finally {
        btn.disabled = false;
    }
}

async function refreshDatasets() {
    try {
        const resp = await fetch('/api/datasets');
        const data = await resp.json();
        const list = document.getElementById('datasetList');

        if (data.count === 0) {
            list.innerHTML = '<em>No datasets loaded</em>';
            return;
        }

        list.innerHTML = '';
        data.datasets.forEach(ds => {
            const item = document.createElement('div');
            item.className = 'dataset-item';
            item.innerHTML = `
                <div>
                    <div class="name">${ds.name}</div>
                    <div class="meta">${ds.feature_count || '?'} features &middot; ${ds.geometry_type || 'unknown'}</div>
                </div>
                <button class="delete-btn" onclick="event.stopPropagation(); deleteDataset('${ds.name}')">&times;</button>
            `;
            item.onclick = () => loadDatasetOnMap(ds.name);
            list.appendChild(item);
        });
    } catch (e) {
        setStatus('Failed to refresh datasets');
    }
}

async function loadDatasetOnMap(name) {
    setStatus(`Loading ${name} on map...`);

    // Remove existing layer/source if present
    removeLayer(name);

    try {
        const resp = await fetch(`/api/datasets/${name}/geojson?limit=5000`);
        if (!resp.ok) throw new Error('Failed to fetch GeoJSON');
        const geojson = await resp.json();

        map.addSource(name, { type: 'geojson', data: geojson });

        // Detect geometry type from first feature
        const geomType = geojson.features[0]?.geometry?.type || 'Point';

        if (geomType.includes('Polygon')) {
            map.addLayer({
                id: `${name}-fill`, type: 'fill', source: name,
                paint: { 'fill-color': randomColor(), 'fill-opacity': 0.4 },
                filter: ['any', ['==', '$type', 'Polygon']],
            });
            map.addLayer({
                id: `${name}-line`, type: 'line', source: name,
                paint: { 'line-color': '#fff', 'line-width': 0.5 },
                filter: ['any', ['==', '$type', 'Polygon']],
            });
            activeLayers.add(`${name}-fill`);
            activeLayers.add(`${name}-line`);
        } else if (geomType.includes('Line')) {
            map.addLayer({
                id: `${name}-line`, type: 'line', source: name,
                paint: { 'line-color': randomColor(), 'line-width': 2 },
            });
            activeLayers.add(`${name}-line`);
        } else {
            map.addLayer({
                id: `${name}-circle`, type: 'circle', source: name,
                paint: {
                    'circle-radius': 5,
                    'circle-color': randomColor(),
                    'circle-stroke-color': '#fff',
                    'circle-stroke-width': 1,
                },
            });
            activeLayers.add(`${name}-circle`);
        }

        // Click handler for popups
        const layerId = [...activeLayers].filter(l => l.startsWith(name))[0];
        if (layerId) {
            map.on('click', layerId, (e) => {
                if (!e.features?.length) return;
                const props = e.features[0].properties;
                let html = '<table>';
                for (const [k, v] of Object.entries(props)) {
                    html += `<tr><th>${k}</th><td>${v}</td></tr>`;
                }
                html += '</table>';
                if (popup) popup.remove();
                popup = new maplibregl.Popup({ maxWidth: '300px' })
                    .setLngLat(e.lngLat).setHTML(html).addTo(map);
            });
            map.on('mouseenter', layerId, () => map.getCanvas().style.cursor = 'pointer');
            map.on('mouseleave', layerId, () => map.getCanvas().style.cursor = '');
        }

        setStatus(`${name} loaded on map`);
    } catch (e) {
        setStatus(`Error: ${e.message}`);
    }
}

function removeLayer(name) {
    const prefixes = [`${name}-fill`, `${name}-line`, `${name}-circle`];
    prefixes.forEach(id => {
        if (map.getLayer(id)) {
            map.removeLayer(id);
            activeLayers.delete(id);
        }
    });
    if (map.getSource(name)) map.removeSource(name);
}

async function deleteDataset(name) {
    try {
        await fetch(`/api/datasets/${name}`, { method: 'DELETE' });
        removeLayer(name);
        setStatus(`Deleted ${name}`);
        await refreshDatasets();
    } catch (e) {
        setStatus(`Error deleting: ${e.message}`);
    }
}

function randomColor() {
    const colors = ['#e94560', '#0f3460', '#7ec8e3', '#f5a623', '#50c878', '#ff6b6b', '#4ecdc4', '#ffe66d'];
    return colors[Math.floor(Math.random() * colors.length)];
}

// Initialize
map.on('load', () => {
    loadBuiltinOptions();
    refreshDatasets();
});
