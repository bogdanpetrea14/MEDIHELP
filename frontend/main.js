const API_BASE = 'http://localhost:8080/api';
const keycloak = new Keycloak({
  url: 'http://localhost:8081',
  realm: 'medihelp',
  clientId: 'medihelp-frontend',
});

let currentUser = null;
let currentUserProfile = null;

// Initialize Keycloak
keycloak
  .init({ onLoad: 'check-sso', checkLoginIframe: false })
  .then(authenticated => {
    if (authenticated) {
      updateUIAuthenticated();
      loadUserProfile();
    } else {
      updateUINotAuthenticated();
    }
  })
  .catch(err => {
    console.error('Eroare init Keycloak:', err);
    updateUINotAuthenticated();
  });

// Auth buttons
document.getElementById('btn-login').onclick = () => keycloak.login();
document.getElementById('btn-logout').onclick = () => {
  keycloak.logout({ redirectUri: window.location.origin });
};

// Tab switching
document.querySelectorAll('.tab').forEach(tab => {
  tab.onclick = () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(`tab-${tab.dataset.tab}`).classList.add('active');
    
    // Load data when switching tabs
    if (tab.dataset.tab === 'prescriptions') loadPrescriptions();
    else if (tab.dataset.tab === 'medications') loadMedications();
    else if (tab.dataset.tab === 'pharmacies') loadPharmacies();
    else if (tab.dataset.tab === 'inventory') {
      loadPharmaciesForSelect();
      if (document.getElementById('inventory-pharmacy-select').value) {
        loadInventory();
      }
    }
    else if (tab.dataset.tab === 'pharmacists') {
      loadPharmacists();
      loadPharmaciesForSelect();
    }
  };
});

// User profile
document.getElementById('btn-me').onclick = loadUserProfile;

async function loadUserProfile() {
  try {
    await keycloak.updateToken(30);
    const resp = await fetch(`${API_BASE}/user/me`, {
      headers: { Authorization: 'Bearer ' + keycloak.token },
    });
    const data = await resp.json();
    currentUserProfile = data;
    document.getElementById('me-response').textContent = JSON.stringify(data, null, 2);
    
    const roles = (keycloak.tokenParsed?.realm_access?.roles) || [];
    document.getElementById('userinfo').innerHTML = `
      <p><strong>ID:</strong> ${data.id}</p>
      <p><strong>Username:</strong> ${data.username}</p>
      <p><strong>Rol:</strong> ${data.role}</p>
      <p><strong>Roluri Keycloak:</strong> ${roles.map(r => `<span class="badge badge-info">${r}</span>`).join(' ')}</p>
    `;
  } catch (err) {
    showAlert('me-response', 'Eroare: ' + err, 'error');
  }
}

function updateUIAuthenticated() {
  document.getElementById('auth-status').innerHTML = 'Status: <strong style="color:green">autentificat</strong>';
  document.getElementById('btn-login').disabled = true;
  document.getElementById('btn-logout').disabled = false;
  document.getElementById('unauthenticated-view').classList.add('hidden');
  document.getElementById('authenticated-view').classList.remove('hidden');
  
  const roles = (keycloak.tokenParsed?.realm_access?.roles) || [];
  currentUser = {
    username: keycloak.tokenParsed?.preferred_username || keycloak.tokenParsed?.sub,
    roles: roles
  };
  
  // Load initial data
  loadPrescriptions();
  loadMedications();
  loadPharmacies();
}

function updateUINotAuthenticated() {
  document.getElementById('auth-status').innerHTML = 'Status: <strong style="color:red">neautentificat</strong>';
  document.getElementById('btn-login').disabled = false;
  document.getElementById('btn-logout').disabled = true;
  document.getElementById('unauthenticated-view').classList.remove('hidden');
  document.getElementById('authenticated-view').classList.add('hidden');
}

// API helper
async function apiCall(endpoint, options = {}) {
  await keycloak.updateToken(30);
  const headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + keycloak.token,
    ...options.headers
  };
  const resp = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.error || 'Request failed');
  return data;
}

function showAlert(containerId, message, type = 'info') {
  const container = document.getElementById(containerId);
  const alert = document.createElement('div');
  alert.className = `alert alert-${type}`;
  alert.textContent = message;
  container.innerHTML = '';
  container.appendChild(alert);
  setTimeout(() => alert.remove(), 5000);
}

// Prescriptions
document.getElementById('btn-create-prescription').onclick = () => {
  if (!currentUser?.roles.includes('DOCTOR')) {
    alert('Doar doctorii pot crea prescripții!');
    return;
  }
  document.getElementById('create-prescription-form').classList.remove('hidden');
};

document.getElementById('btn-refresh-prescriptions').onclick = loadPrescriptions;

document.getElementById('prescription-form').onsubmit = async (e) => {
  e.preventDefault();
  try {
    if (!currentUserProfile) await loadUserProfile();
    
    await apiCall('/prescriptions', {
      method: 'POST',
      body: JSON.stringify({
        doctor_id: currentUserProfile.id,
        patient_id: parseInt(document.getElementById('prescription-patient-id').value),
        medication_name: document.getElementById('prescription-medication').value,
        dosage: document.getElementById('prescription-dosage').value,
        quantity: parseInt(document.getElementById('prescription-quantity').value),
        instructions: document.getElementById('prescription-instructions').value,
      })
    });
    
    showAlert('prescription-alerts', 'Prescripție creată cu succes!', 'success');
    document.getElementById('prescription-form').reset();
    document.getElementById('create-prescription-form').classList.add('hidden');
    loadPrescriptions();
  } catch (err) {
    showAlert('prescription-alerts', 'Eroare: ' + err.message, 'error');
  }
};

async function loadPrescriptions() {
  try {
    const filter = currentUser?.roles.includes('DOCTOR') 
      ? `?doctor_id=${currentUserProfile?.id || ''}` 
      : '';
    const prescriptions = await apiCall(`/prescriptions${filter}`);
    
    const tbody = document.getElementById('prescriptions-tbody');
    if (prescriptions.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9">Nu există prescripții</td></tr>';
      return;
    }
    
    tbody.innerHTML = prescriptions.map(p => `
      <tr>
        <td>${p.id}</td>
        <td>${p.patient_id}</td>
        <td>${p.medication_name}</td>
        <td>${p.dosage}</td>
        <td>${p.quantity}</td>
        <td><span class="badge badge-${getStatusBadgeClass(p.status)}">${p.status}</span></td>
        <td>${p.pharmacy_id || '-'}</td>
        <td>${new Date(p.created_at).toLocaleDateString('ro-RO')}</td>
        <td>
          ${p.status === 'PENDING' && currentUser?.roles.includes('PHARMACIST') 
            ? `<button class="btn-success" onclick="fulfillPrescription(${p.id})">Onorează</button>` 
            : ''}
        </td>
      </tr>
    `).join('');
  } catch (err) {
    document.getElementById('prescriptions-tbody').innerHTML = 
      `<tr><td colspan="9">Eroare: ${err.message}</td></tr>`;
  }
}

async function fulfillPrescription(id) {
  if (!confirm('Ești sigur că vrei să onorezi această prescripție?')) return;
  
  try {
    const pharmacyId = prompt('Introdu ID-ul farmaciei:');
    if (!pharmacyId) return;
    
    if (!currentUserProfile) await loadUserProfile();
    
    await apiCall(`/prescriptions/${id}/fulfill`, {
      method: 'POST',
      body: JSON.stringify({
        pharmacy_id: parseInt(pharmacyId),
        pharmacist_id: currentUserProfile.id,
      })
    });
    
    showAlert('prescription-alerts', 'Prescripție onorată cu succes!', 'success');
    loadPrescriptions();
  } catch (err) {
    showAlert('prescription-alerts', 'Eroare: ' + err.message, 'error');
  }
}

function getStatusBadgeClass(status) {
  const map = {
    'PENDING': 'warning',
    'FULFILLED': 'success',
    'CANCELLED': 'danger',
    'EXPIRED': 'danger'
  };
  return map[status] || 'info';
}

// Medications
document.getElementById('btn-create-medication').onclick = () => {
  if (!currentUser?.roles.includes('ADMIN')) {
    alert('Doar administratorii pot adăuga medicamente!');
    return;
  }
  document.getElementById('create-medication-form').classList.remove('hidden');
};

document.getElementById('btn-refresh-medications').onclick = loadMedications;

document.getElementById('medication-form').onsubmit = async (e) => {
  e.preventDefault();
  try {
    await apiCall('/medications', {
      method: 'POST',
      body: JSON.stringify({
        name: document.getElementById('medication-name').value,
        description: document.getElementById('medication-description').value,
        unit_price: parseFloat(document.getElementById('medication-price').value),
      })
    });
    
    showAlert('medication-alerts', 'Medicament adăugat cu succes!', 'success');
    document.getElementById('medication-form').reset();
    document.getElementById('create-medication-form').classList.add('hidden');
    loadMedications();
  } catch (err) {
    showAlert('medication-alerts', 'Eroare: ' + err.message, 'error');
  }
};

async function loadMedications() {
  try {
    const medications = await apiCall('/medications');
    const tbody = document.getElementById('medications-tbody');
    
    if (medications.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4">Nu există medicamente</td></tr>';
      return;
    }
    
    tbody.innerHTML = medications.map(m => `
      <tr>
        <td>${m.id}</td>
        <td>${m.name}</td>
        <td>${m.description || '-'}</td>
        <td>${m.unit_price.toFixed(2)} RON</td>
      </tr>
    `).join('');
    
    // Update medication select for inventory
    const select = document.getElementById('stock-medication-select');
    select.innerHTML = '<option value="">Selectează medicament...</option>' +
      medications.map(m => `<option value="${m.id}">${m.name}</option>`).join('');
  } catch (err) {
    document.getElementById('medications-tbody').innerHTML = 
      `<tr><td colspan="4">Eroare: ${err.message}</td></tr>`;
  }
}

// Pharmacies
document.getElementById('btn-create-pharmacy').onclick = () => {
  if (!currentUser?.roles.includes('ADMIN')) {
    alert('Doar administratorii pot adăuga farmacii!');
    return;
  }
  document.getElementById('create-pharmacy-form').classList.remove('hidden');
};

document.getElementById('btn-refresh-pharmacies').onclick = loadPharmacies;

document.getElementById('pharmacy-form').onsubmit = async (e) => {
  e.preventDefault();
  try {
    await apiCall('/pharmacies', {
      method: 'POST',
      body: JSON.stringify({
        name: document.getElementById('pharmacy-name').value,
        address: document.getElementById('pharmacy-address').value,
        phone: document.getElementById('pharmacy-phone').value,
        email: document.getElementById('pharmacy-email').value,
      })
    });
    
    showAlert('pharmacy-alerts', 'Farmacie adăugată cu succes!', 'success');
    document.getElementById('pharmacy-form').reset();
    document.getElementById('create-pharmacy-form').classList.add('hidden');
    loadPharmacies();
    loadPharmaciesForSelect();
  } catch (err) {
    showAlert('pharmacy-alerts', 'Eroare: ' + err.message, 'error');
  }
};

async function loadPharmacies() {
  try {
    const pharmacies = await apiCall('/pharmacies?active_only=true');
    const tbody = document.getElementById('pharmacies-tbody');
    
    if (pharmacies.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7">Nu există farmacii</td></tr>';
      return;
    }
    
    tbody.innerHTML = pharmacies.map(p => `
      <tr>
        <td>${p.id}</td>
        <td>${p.name}</td>
        <td>${p.address}</td>
        <td>${p.phone || '-'}</td>
        <td>${p.email || '-'}</td>
        <td><span class="badge badge-${p.is_active ? 'success' : 'danger'}">${p.is_active ? 'Activă' : 'Inactivă'}</span></td>
        <td><button class="btn-secondary" onclick="viewPharmacyStock(${p.id})">Vezi Stoc</button></td>
      </tr>
    `).join('');
  } catch (err) {
    document.getElementById('pharmacies-tbody').innerHTML = 
      `<tr><td colspan="7">Eroare: ${err.message}</td></tr>`;
  }
}

async function loadPharmaciesForSelect() {
  try {
    const pharmacies = await apiCall('/pharmacies?active_only=true');
    const selects = [
      document.getElementById('inventory-pharmacy-select'),
      document.getElementById('pharmacist-pharmacy-select')
    ];
    
    selects.forEach(select => {
      if (!select) return;
      const currentValue = select.value;
      select.innerHTML = '<option value="">Selectează o farmacie...</option>' +
        pharmacies.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
      if (currentValue) select.value = currentValue;
    });
  } catch (err) {
    console.error('Error loading pharmacies for select:', err);
  }
}

function viewPharmacyStock(pharmacyId) {
  document.getElementById('inventory-pharmacy-select').value = pharmacyId;
  document.querySelector('.tab[data-tab="inventory"]').click();
  loadInventory();
}

// Inventory
document.getElementById('inventory-pharmacy-select').onchange = () => {
  const pharmacyId = document.getElementById('inventory-pharmacy-select').value;
  if (pharmacyId) {
    loadInventory();
    document.getElementById('add-stock-form').classList.remove('hidden');
  } else {
    document.getElementById('inventory-tbody').innerHTML = 
      '<tr><td colspan="5">Selectează o farmacie...</td></tr>';
    document.getElementById('add-stock-form').classList.add('hidden');
  }
};

document.getElementById('btn-refresh-inventory').onclick = loadInventory;

document.getElementById('stock-form').onsubmit = async (e) => {
  e.preventDefault();
  try {
    const pharmacyId = document.getElementById('inventory-pharmacy-select').value;
    if (!pharmacyId) {
      alert('Selectează o farmacie!');
      return;
    }
    
    await apiCall(`/pharmacies/${pharmacyId}/stock`, {
      method: 'POST',
      body: JSON.stringify({
        medication_id: parseInt(document.getElementById('stock-medication-select').value),
        quantity: parseInt(document.getElementById('stock-quantity').value),
        min_threshold: parseInt(document.getElementById('stock-threshold').value),
      })
    });
    
    showAlert('inventory-alerts', 'Stoc adăugat cu succes!', 'success');
    document.getElementById('stock-form').reset();
    loadInventory();
  } catch (err) {
    showAlert('inventory-alerts', 'Eroare: ' + err.message, 'error');
  }
};

async function loadInventory() {
  const pharmacyId = document.getElementById('inventory-pharmacy-select').value;
  if (!pharmacyId) return;
  
  try {
    const stock = await apiCall(`/pharmacies/${pharmacyId}/stock`);
    const lowStock = await apiCall(`/pharmacies/${pharmacyId}/stock/low`);
    
    const tbody = document.getElementById('inventory-tbody');
    if (stock.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5">Nu există stoc pentru această farmacie</td></tr>';
      return;
    }
    
    tbody.innerHTML = stock.map(s => `
      <tr>
        <td>${s.medication_name || s.medication_id}</td>
        <td>${s.quantity}</td>
        <td>${s.min_threshold}</td>
        <td><span class="badge badge-${s.low_stock ? 'danger' : 'success'}">${s.low_stock ? 'Stoc Scăzut' : 'OK'}</span></td>
        <td>${new Date(s.last_updated).toLocaleString('ro-RO')}</td>
      </tr>
    `).join('');
    
    // Show low stock alert
    const alertDiv = document.getElementById('low-stock-alert');
    if (lowStock.length > 0) {
      alertDiv.classList.remove('hidden');
      alertDiv.innerHTML = `
        <div class="alert alert-warning">
          <strong>⚠ Atenție!</strong> ${lowStock.length} medicamente au stoc scăzut:
          ${lowStock.map(s => s.medication_name || s.medication_id).join(', ')}
        </div>
      `;
    } else {
      alertDiv.classList.add('hidden');
    }
  } catch (err) {
    document.getElementById('inventory-tbody').innerHTML = 
      `<tr><td colspan="5">Eroare: ${err.message}</td></tr>`;
  }
}

// Pharmacists
document.getElementById('btn-create-pharmacist').onclick = () => {
  if (!currentUser?.roles.includes('ADMIN')) {
    alert('Doar administratorii pot adăuga farmaciști!');
    return;
  }
  document.getElementById('create-pharmacist-form').classList.remove('hidden');
};

document.getElementById('btn-refresh-pharmacists').onclick = loadPharmacists;

document.getElementById('pharmacist-form').onsubmit = async (e) => {
  e.preventDefault();
  try {
    await apiCall('/pharmacists', {
      method: 'POST',
      body: JSON.stringify({
        user_id: parseInt(document.getElementById('pharmacist-user-id').value),
        pharmacy_id: parseInt(document.getElementById('pharmacist-pharmacy-select').value),
        license_number: document.getElementById('pharmacist-license').value,
      })
    });
    
    showAlert('pharmacist-alerts', 'Farmacist adăugat cu succes!', 'success');
    document.getElementById('pharmacist-form').reset();
    document.getElementById('create-pharmacist-form').classList.add('hidden');
    loadPharmacists();
  } catch (err) {
    showAlert('pharmacist-alerts', 'Eroare: ' + err.message, 'error');
  }
};

async function loadPharmacists() {
  try {
    const pharmacists = await apiCall('/pharmacists');
    const pharmacies = await apiCall('/pharmacies');
    const pharmacyMap = {};
    pharmacies.forEach(p => pharmacyMap[p.id] = p.name);
    
    const tbody = document.getElementById('pharmacists-tbody');
    if (pharmacists.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5">Nu există farmaciști</td></tr>';
      return;
    }
    
    tbody.innerHTML = pharmacists.map(p => `
      <tr>
        <td>${p.id}</td>
        <td>${p.user_id}</td>
        <td>${pharmacyMap[p.pharmacy_id] || p.pharmacy_id}</td>
        <td>${p.license_number}</td>
        <td><span class="badge badge-${p.is_active ? 'success' : 'danger'}">${p.is_active ? 'Activ' : 'Inactiv'}</span></td>
      </tr>
    `).join('');
  } catch (err) {
    document.getElementById('pharmacists-tbody').innerHTML = 
      `<tr><td colspan="5">Eroare: ${err.message}</td></tr>`;
  }
}
