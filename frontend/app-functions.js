// Application functions - shared across all role pages
// Note: This file expects common.js to be loaded first
console.log('=== APP-FUNCTIONS.JS LOADED ===');

// Tab switching initialization
function initializeTabSwitching() {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.onclick = () => {
      // Switch tabs
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => {
        c.classList.remove('active');
        c.style.display = 'none';
      });
      
      tab.classList.add('active');
      const tabName = tab.dataset.tab;
      const tabContent = document.getElementById(`tab-${tabName}`);
      if (tabContent) {
        tabContent.style.display = 'block';
        tabContent.classList.add('active');
      }
      
      // Load data when switching tabs
      if (tabName === 'prescriptions') {
        loadPrescriptions();
      } else if (tabName === 'medications') {
        loadMedications();
      } else if (tabName === 'pharmacies') {
        loadPharmacies();
      } else if (tabName === 'inventory') {
        loadPharmaciesForSelect();
        loadMedications();
        if (document.getElementById('inventory-pharmacy-select')?.value) {
          loadInventory();
        }
      } else if (tabName === 'pharmacists') {
        loadPharmacists();
        loadPharmaciesForSelect();
      }
    };
  });
}

// Helper function for status badge classes
function getStatusBadgeClass(status) {
  const map = {
    'PENDING': 'warning',
    'FULFILLED': 'success',
    'CANCELLED': 'danger',
    'EXPIRED': 'danger'
  };
  return map[status] || 'info';
}

// Prescriptions functions
async function loadPrescriptions() {
  try {
    if (!currentUserProfile) {
      await loadUserProfile();
    }
    
    let filter = '';
    const role = currentUserProfile?.role;
    
    if (role === 'DOCTOR') {
      filter = `?doctor_id=${currentUserProfile.id}`;
    } else if (role === 'PATIENT') {
      filter = `?patient_id=${currentUserProfile.id}`;
    } else if (role === 'PHARMACIST') {
      filter = '?status=PENDING';
    }
    // ADMIN sees all
    
    const prescriptions = await apiCall(`/prescriptions${filter}`);
    const tbody = document.getElementById('prescriptions-tbody');
    
    if (!tbody) return;
    
    if (prescriptions.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9">Nu există prescripții</td></tr>';
      return;
    }
    
    tbody.innerHTML = prescriptions.map(p => {
      const canFulfill = p.status === 'PENDING' && (role === 'PHARMACIST' || role === 'ADMIN');
      const canCancel = (p.status === 'PENDING' || p.status === 'CANCELLED') && role === 'ADMIN';
      const buttons = [];
      
      if (canFulfill) {
        buttons.push(`<button class="btn-success" onclick="fulfillPrescription(${p.id})">Onorează</button>`);
      }
      if (canCancel && p.status === 'PENDING') {
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
    const tbody = document.getElementById('prescriptions-tbody');
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="9">Eroare: ${err.message}</td></tr>`;
    }
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
    
    const inventorySelect = document.getElementById('inventory-pharmacy-select');
    if (inventorySelect && inventorySelect.value == pharmacyId) {
      loadInventory();
    }
  } catch (err) {
    showAlert('prescription-alerts', 'Eroare: ' + err.message, 'error');
  }
}

// Populate medication dropdown for prescription form
async function populateMedicationDropdown() {
  try {
    const medications = await apiCall('/medications');
    const select = document.getElementById('prescription-medication');
    if (select) {
      select.innerHTML = '<option value="">Selectează medicament...</option>' +
        medications.map(m => `<option value="${m.name}">${m.name}</option>`).join('');
    }
  } catch (err) {
    console.error('Error loading medications for dropdown:', err);
  }
}

// Medications functions
async function loadMedications() {
  try {
    const medications = await apiCall('/medications');
    const tbody = document.getElementById('medications-tbody');
    
    if (!tbody) return;
    
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
    
    // Update medication select for inventory if it exists
    const select = document.getElementById('stock-medication-select');
    if (select) {
      select.innerHTML = '<option value="">Selectează medicament...</option>' +
        medications.map(m => `<option value="${m.id}">${m.name}</option>`).join('');
    }
    
    // Update medication select for prescription form if it exists
    const prescriptionSelect = document.getElementById('prescription-medication');
    if (prescriptionSelect) {
      prescriptionSelect.innerHTML = '<option value="">Selectează medicament...</option>' +
        medications.map(m => `<option value="${m.name}">${m.name}</option>`).join('');
    }
  } catch (err) {
    const tbody = document.getElementById('medications-tbody');
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="4">Eroare: ${err.message}</td></tr>`;
    }
  }
}

// Pharmacies functions
async function loadPharmacies() {
  try {
    const pharmacies = await apiCall('/pharmacies?active_only=true');
    const tbody = document.getElementById('pharmacies-tbody');
    
    if (!tbody) return;
    
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
    const tbody = document.getElementById('pharmacies-tbody');
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="7">Eroare: ${err.message}</td></tr>`;
    }
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
  const inventorySelect = document.getElementById('inventory-pharmacy-select');
  if (inventorySelect) {
    inventorySelect.value = pharmacyId;
    const inventoryTab = document.querySelector('.tab[data-tab="inventory"]');
    if (inventoryTab) {
      inventoryTab.click();
      loadInventory();
    }
  }
}

// Inventory functions
async function loadInventory() {
  const pharmacyId = document.getElementById('inventory-pharmacy-select')?.value;
  if (!pharmacyId) {
    const tbody = document.getElementById('inventory-tbody');
    if (tbody) {
      tbody.innerHTML = '<tr><td colspan="5">Selectează o farmacie...</td></tr>';
    }
    return;
  }
  
  try {
    const stock = await apiCall(`/pharmacies/${pharmacyId}/stock`);
    const lowStock = await apiCall(`/pharmacies/${pharmacyId}/stock/low`);
    const tbody = document.getElementById('inventory-tbody');
    
    if (!tbody) return;
    
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
    
    const alertDiv = document.getElementById('low-stock-alert');
    if (alertDiv) {
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
    }
  } catch (err) {
    const tbody = document.getElementById('inventory-tbody');
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="5">Eroare: ${err.message}</td></tr>`;
    }
  }
}

// Pharmacists functions
async function loadPharmacists() {
  try {
    const pharmacists = await apiCall('/pharmacists');
    const pharmacies = await apiCall('/pharmacies');
    const pharmacyMap = {};
    pharmacies.forEach(p => pharmacyMap[p.id] = p.name);
    
    const tbody = document.getElementById('pharmacists-tbody');
    if (!tbody) return;
    
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
    const tbody = document.getElementById('pharmacists-tbody');
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="5">Eroare: ${err.message}</td></tr>`;
    }
  }
}
