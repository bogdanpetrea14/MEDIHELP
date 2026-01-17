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

// Tab switching - initialize after DOM is ready
function initializeTabSwitching() {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.onclick = () => {
      // Don't switch if tab is hidden
      if (tab.style.display === 'none') {
        return;
      }
      
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      tab.classList.add('active');
      const tabName = tab.dataset.tab;
      const tabContent = document.getElementById(`tab-${tabName}`);
      if (tabContent) {
        tabContent.classList.add('active');
      }
      
    // Load data when switching tabs
    if (tabName === 'prescriptions') {
      loadPrescriptions();
    } else if (tabName === 'medications') {
      loadMedications();
    } else if (tabName === 'pharmacies') {
      if (currentUserProfile && (currentUserProfile.role === 'ADMIN' || currentUserProfile.role === 'PHARMACIST')) {
        loadPharmacies();
      }
    } else if (tabName === 'inventory') {
      if (currentUserProfile && (currentUserProfile.role === 'PHARMACIST' || currentUserProfile.role === 'ADMIN')) {
        loadPharmaciesForSelect();
        loadMedications(); // Load medications for the select dropdown
        if (document.getElementById('inventory-pharmacy-select').value) {
          loadInventory();
        }
      }
    } else if (tabName === 'pharmacists') {
      if (currentUserProfile && currentUserProfile.role === 'ADMIN') {
        loadPharmacists();
        loadPharmaciesForSelect();
      }
    }
    };
  });
}

// Initialize tab switching when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeTabSwitching);
} else {
  initializeTabSwitching();
}

// Profile refresh button removed - handled in profile.html

async function loadUserProfile() {
  try {
    await keycloak.updateToken(30);
    const resp = await fetch(`${API_BASE}/user/me`, {
      headers: { Authorization: 'Bearer ' + keycloak.token },
    });
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
    }
    const data = await resp.json();
    currentUserProfile = data;
    
    // Update tabs based on role - this must happen after profile is loaded
    updateTabsForRole(data.role);
    
    return data;
  } catch (err) {
    console.error('Error loading user profile:', err);
    throw err;
  }
}

// Profile display functions removed - now handled in profile.html/profile.js

function updateTabsForRole(role) {
  console.log('Updating tabs for role:', role);
  
  if (!role) {
    console.error('No role provided to updateTabsForRole');
    return;
  }
  
  // Ensure profile link is visible
  const profileLink = document.getElementById('profile-link');
  if (profileLink) {
    profileLink.classList.remove('hidden');
  }
  
  // Show tabs container - make sure it's visible
  const tabsContainer = document.getElementById('main-tabs');
  if (tabsContainer) {
    tabsContainer.style.display = 'flex';
    tabsContainer.classList.remove('hidden');
  }
  
  // FIRST: Hide ALL tabs and their contents by default
  const allTabs = document.querySelectorAll('.tab[data-role]');
  allTabs.forEach(tab => {
    tab.style.display = 'none';
    tab.classList.remove('active');
  });
  
  // Hide all tab contents
  document.querySelectorAll('.tab-content').forEach(content => {
    content.classList.remove('active');
    content.style.display = 'none';
  });
  
  // SECOND: Show only tabs allowed for this role
  let visibleTabsCount = 0;
  allTabs.forEach(tab => {
    const allowedRoles = tab.dataset.role.split(',').map(r => r.trim());
    if (allowedRoles.includes(role) || role === 'ADMIN') {
      tab.style.display = 'inline-block';
      visibleTabsCount++;
      console.log('✓ Showing tab:', tab.dataset.tab, 'for role:', role);
    } else {
      tab.style.display = 'none';
      console.log('✗ Hiding tab:', tab.dataset.tab, 'for role:', role, '(allowed:', allowedRoles, ')');
    }
  });
  
  console.log(`Total visible tabs for ${role}: ${visibleTabsCount}`);
  
  // Hide/show action buttons based on role
  updateActionButtons(role);
  
  // THIRD: Activate first visible tab and its content
  const visibleTabs = Array.from(allTabs).filter(tab => tab.style.display === 'inline-block');
  
  if (visibleTabs.length > 0) {
    // Remove active from all tabs
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    
    // Hide all tab contents
    document.querySelectorAll('.tab-content').forEach(c => {
      c.classList.remove('active');
      c.style.display = 'none';
    });
    
    // Activate first visible tab
    const firstTab = visibleTabs[0];
    firstTab.classList.add('active');
    
    const tabName = firstTab.dataset.tab;
    const firstTabContent = document.getElementById(`tab-${tabName}`);
    if (firstTabContent) {
      firstTabContent.style.display = 'block';
      firstTabContent.classList.add('active');
      
      // Load data for first tab
      console.log('Loading data for first tab:', tabName);
      setTimeout(() => {
        if (tabName === 'prescriptions') {
          loadPrescriptions();
        } else if (tabName === 'medications') {
          loadMedications();
        } else if (tabName === 'pharmacies') {
          loadPharmacies();
        } else if (tabName === 'inventory') {
          loadPharmaciesForSelect();
          if (document.getElementById('inventory-pharmacy-select').value) {
            loadInventory();
          }
        } else if (tabName === 'pharmacists') {
          loadPharmacists();
          loadPharmaciesForSelect();
        }
      }, 100);
    } else {
      console.error('Tab content not found for:', tabName);
    }
  } else {
    console.warn('No visible tabs found for role:', role);
    // Show a message if no tabs are available
    const tabsContainer = document.getElementById('main-tabs');
    if (tabsContainer) {
      tabsContainer.innerHTML = '<div class="alert alert-info">Nu aveți acces la nicio secțiune pentru acest rol.</div>';
    }
  }
}

function updateActionButtons(role) {
  // Prescriptions tab buttons
  const btnCreatePrescription = document.getElementById('btn-create-prescription');
  if (btnCreatePrescription) {
    btnCreatePrescription.style.display = (role === 'DOCTOR' || role === 'ADMIN') ? 'inline-block' : 'none';
  }
  
  // Medications tab buttons
  const btnCreateMedication = document.getElementById('btn-create-medication');
  if (btnCreateMedication) {
    btnCreateMedication.style.display = (role === 'ADMIN') ? 'inline-block' : 'none';
  }
  
  // Pharmacies tab buttons
  const btnCreatePharmacy = document.getElementById('btn-create-pharmacy');
  if (btnCreatePharmacy) {
    btnCreatePharmacy.style.display = (role === 'ADMIN') ? 'inline-block' : 'none';
  }
  
  // Pharmacists tab buttons
  const btnCreatePharmacist = document.getElementById('btn-create-pharmacist');
  if (btnCreatePharmacist) {
    btnCreatePharmacist.style.display = (role === 'ADMIN') ? 'inline-block' : 'none';
  }
  
  // Inventory buttons
  const addStockForm = document.getElementById('add-stock-form');
  if (addStockForm && role !== 'PHARMACIST' && role !== 'ADMIN') {
    addStockForm.style.display = 'none';
  }
}

function loadInitialDataForRole(role) {
  // Always load medications (read-only for most roles)
  loadMedications();
  
  if (role === 'DOCTOR' || role === 'ADMIN') {
    loadPrescriptions();
  } else if (role === 'PHARMACIST' || role === 'ADMIN') {
    loadPrescriptions(); // Farmaciștii văd prescripțiile pentru a le onora
    loadPharmacies();
    loadPharmaciesForSelect();
  } else if (role === 'PATIENT') {
    // Pacienții văd doar propriile prescripții - ar trebui filtrate după patient_id
    loadPrescriptions();
  }
  
  if (role === 'ADMIN') {
    loadPharmacies();
    loadPharmacists();
  }
}

function updateUIAuthenticated() {
  document.getElementById('auth-status').innerHTML = 'Status: <strong style="color:green">autentificat</strong>';
  document.getElementById('btn-login').disabled = true;
  document.getElementById('btn-logout').disabled = false;
  document.getElementById('unauthenticated-view').classList.add('hidden');
  document.getElementById('authenticated-view').classList.remove('hidden');
  
  // Show profile link immediately when authenticated
  const profileLink = document.getElementById('profile-link');
  if (profileLink) {
    profileLink.classList.remove('hidden');
  }
  
  // Show tabs container
  const tabsContainer = document.getElementById('main-tabs');
  if (tabsContainer) {
    tabsContainer.style.display = 'flex';
  }
  
  const roles = (keycloak.tokenParsed?.realm_access?.roles) || [];
  currentUser = {
    username: keycloak.tokenParsed?.preferred_username || keycloak.tokenParsed?.sub,
    roles: roles
  };
  
  // Initialize tab switching
  initializeTabSwitching();
  
  // Load user profile first, which will trigger role-based UI updates
  loadUserProfile().catch(err => {
    console.error('Failed to load user profile:', err);
    // Even if profile fails, try to show tabs based on Keycloak roles
    if (roles.length > 0) {
      // Try to infer role from Keycloak roles
      let inferredRole = 'PATIENT'; // default
      if (roles.includes('DOCTOR')) inferredRole = 'DOCTOR';
      else if (roles.includes('PHARMACIST')) inferredRole = 'PHARMACIST';
      else if (roles.includes('ADMIN')) inferredRole = 'ADMIN';
      updateTabsForRole(inferredRole);
    }
  });
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
  if (!currentUserProfile) {
    alert('Te rugăm să aștepți încărcarea profilului...');
    return;
  }
  const role = currentUserProfile.role;
  if (role !== 'DOCTOR' && role !== 'ADMIN') {
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
    if (!currentUserProfile) {
      await loadUserProfile();
    }
    
    let filter = '';
    const role = currentUserProfile?.role;
    
    // Filter based on role
    if (role === 'DOCTOR') {
      filter = `?doctor_id=${currentUserProfile.id}`;
    } else if (role === 'PATIENT') {
      filter = `?patient_id=${currentUserProfile.id}`;
    } else if (role === 'PHARMACIST') {
      // Farmaciștii văd prescripțiile PENDING pentru a le onora
      filter = '?status=PENDING';
    }
    // ADMIN văd toate prescripțiile (fără filtru)
    
    const prescriptions = await apiCall(`/prescriptions${filter}`);
    
    const tbody = document.getElementById('prescriptions-tbody');
    if (prescriptions.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9">Nu există prescripții</td></tr>';
      return;
    }
    
    tbody.innerHTML = prescriptions.map(p => {
      const canFulfill = p.status === 'PENDING' && (role === 'PHARMACIST' || role === 'ADMIN');
      const canCancel = p.status === 'PENDING' && role === 'ADMIN';
      const buttons = [];
      
      if (canFulfill) {
        buttons.push(`<button class="btn-success" onclick="fulfillPrescription(${p.id})">Onorează</button>`);
      }
      if (canCancel) {
        buttons.push(`<button class="btn-danger" onclick="cancelPrescription(${p.id})">Anulează</button>`);
      }
      
      return `
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
            ${buttons.length > 0 ? buttons.join(' ') : '-'}
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    document.getElementById('prescriptions-tbody').innerHTML = 
      `<tr><td colspan="9">Eroare: ${err.message}</td></tr>`;
  }
}

async function fulfillPrescription(id) {
  if (!currentUserProfile) {
    await loadUserProfile();
  }
  
  const role = currentUserProfile?.role;
  if (role !== 'PHARMACIST' && role !== 'ADMIN') {
    alert('Doar farmaciștii pot onora prescripții!');
    return;
  }
  
  if (!confirm('Ești sigur că vrei să onorezi această prescripție?')) return;
  
  try {
    // Try to get pharmacy_id from pharmacist record
    let pharmacyId = null;
    if (role === 'PHARMACIST') {
      try {
        const pharmacists = await apiCall(`/pharmacists?user_id=${currentUserProfile.id}`);
        if (pharmacists && pharmacists.length > 0) {
          pharmacyId = pharmacists[0].pharmacy_id;
        }
      } catch (e) {
        console.log('Could not get pharmacy from pharmacist record');
      }
    }
    
    if (!pharmacyId) {
      const input = prompt('Introdu ID-ul farmaciei:');
      if (!input) return;
      pharmacyId = parseInt(input);
    }
    
    await apiCall(`/prescriptions/${id}/fulfill`, {
      method: 'POST',
      body: JSON.stringify({
        pharmacy_id: pharmacyId,
        pharmacist_id: currentUserProfile.id,
      })
    });
    
    showAlert('prescription-alerts', 'Prescripție onorată cu succes!', 'success');
    loadPrescriptions();
    
    // Refresh inventory if on that tab
    const inventorySelect = document.getElementById('inventory-pharmacy-select');
    if (inventorySelect && inventorySelect.value == pharmacyId) {
      loadInventory();
    }
  } catch (err) {
    showAlert('prescription-alerts', 'Eroare: ' + err.message, 'error');
  }
}

async function cancelPrescription(id) {
  if (!currentUserProfile) {
    await loadUserProfile();
  }
  
  const role = currentUserProfile?.role;
  if (role !== 'ADMIN') {
    alert('Doar administratorii pot anula prescripții!');
    return;
  }
  
  if (!confirm('Ești sigur că vrei să anulezi această prescripție?')) return;
  
  try {
    await apiCall(`/prescriptions/${id}/cancel`, {
      method: 'POST'
    });
    
    showAlert('prescription-alerts', 'Prescripție anulată cu succes!', 'success');
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
  if (!currentUserProfile || currentUserProfile.role !== 'ADMIN') {
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
  if (!currentUserProfile || currentUserProfile.role !== 'ADMIN') {
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
document.getElementById('inventory-pharmacy-select').onchange = async () => {
  const pharmacyId = document.getElementById('inventory-pharmacy-select').value;
  if (pharmacyId) {
    loadInventory();
    
    // Show add stock form only for PHARMACIST and ADMIN
    if (currentUserProfile) {
      const role = currentUserProfile.role;
      if (role === 'PHARMACIST' || role === 'ADMIN') {
        document.getElementById('add-stock-form').classList.remove('hidden');
      } else {
        document.getElementById('add-stock-form').classList.add('hidden');
      }
    }
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
    if (!currentUserProfile) {
      await loadUserProfile();
    }
    
    const role = currentUserProfile?.role;
    if (role !== 'PHARMACIST' && role !== 'ADMIN') {
      alert('Doar farmaciștii pot gestiona stocuri!');
      return;
    }
    
    const pharmacyId = document.getElementById('inventory-pharmacy-select').value;
    if (!pharmacyId) {
      alert('Selectează o farmacie!');
      return;
    }
    
    // If pharmacist, verify they belong to this pharmacy
    if (role === 'PHARMACIST') {
      try {
        const pharmacists = await apiCall(`/pharmacists?user_id=${currentUserProfile.id}`);
        const belongsToPharmacy = pharmacists.some(p => p.pharmacy_id == pharmacyId);
        if (!belongsToPharmacy) {
          alert('Nu aparții acestei farmacii! Poți gestiona doar stocul farmaciei tale.');
          return;
        }
      } catch (e) {
        console.error('Error checking pharmacist pharmacy:', e);
      }
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
  if (!pharmacyId) {
    document.getElementById('inventory-tbody').innerHTML = 
      '<tr><td colspan="5">Selectează o farmacie...</td></tr>';
    return;
  }
  
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
  if (!currentUserProfile || currentUserProfile.role !== 'ADMIN') {
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
