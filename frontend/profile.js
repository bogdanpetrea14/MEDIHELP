const API_BASE = 'http://localhost:8080/api';
const keycloak = new Keycloak({
  url: 'http://localhost:8081',
  realm: 'medihelp',
  clientId: 'medihelp-frontend',
});

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
  keycloak.logout({ redirectUri: window.location.origin + '/profile.html' });
};

function updateUIAuthenticated() {
  document.getElementById('auth-status').innerHTML = 'Status: <strong style="color:green">autentificat</strong>';
  document.getElementById('btn-login').disabled = true;
  document.getElementById('btn-logout').disabled = false;
  document.getElementById('unauthenticated-view').classList.add('hidden');
  document.getElementById('authenticated-view').classList.remove('hidden');
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
    
    // Update profile display
    updateProfileDisplay(data);
  } catch (err) {
    console.error('Error loading user profile:', err);
    document.getElementById('profile-content').innerHTML = `
      <div class="error">
        <strong>Eroare la încărcarea profilului:</strong> ${err.message || err}
        <br><br>
        <button onclick="loadUserProfile()" class="btn btn-primary">Reîncearcă</button>
      </div>
    `;
  }
}

function updateProfileDisplay(profile) {
  // Avatar initial
  const initial = profile.username ? profile.username.charAt(0).toUpperCase() : 'U';
  
  // Role colors and icons
  const roleConfig = {
    'DOCTOR': { bg: '#dbeafe', color: '#1e40af', icon: '👨‍⚕️', label: 'Doctor' },
    'PHARMACIST': { bg: '#dcfce7', color: '#166534', icon: '👩‍⚕️', label: 'Farmacist' },
    'ADMIN': { bg: '#fef3c7', color: '#92400e', icon: '👑', label: 'Administrator' },
    'PATIENT': { bg: '#e0e7ff', color: '#3730a3', icon: '👤', label: 'Pacient' },
  };
  
  const roleInfo = roleConfig[profile.role] || { 
    bg: '#e5e7eb', 
    color: '#374151', 
    icon: '👤', 
    label: profile.role || 'Utilizator' 
  };
  
  // Permissions
  const permissions = getRolePermissions(profile.role);
  
  document.getElementById('profile-content').innerHTML = `
    <div class="profile-header">
      <div class="avatar-container">
        <span id="profile-avatar">${initial}</span>
      </div>
      <h2 id="profile-username">${profile.username || '-'}</h2>
      <div class="role-badge" style="background: ${roleInfo.bg}; color: ${roleInfo.color};">
        ${roleInfo.icon} ${roleInfo.label}
      </div>
    </div>
    
    <div class="info-section">
      <h3>Informații Personale</h3>
      <div class="info-grid">
        <div class="info-label">ID Utilizator:</div>
        <div class="info-value">${profile.id || '-'}</div>
        
        <div class="info-label">Username:</div>
        <div class="info-value">${profile.username || '-'}</div>
        
        <div class="info-label">Rol:</div>
        <div class="info-value">
          <span class="role-badge" style="background: ${roleInfo.bg}; color: ${roleInfo.color}; font-size: 12px;">
            ${roleInfo.icon} ${profile.role || 'USER'}
          </span>
        </div>
      </div>
    </div>

    <div class="permissions-section">
      <h3>Drepturi de Acces</h3>
      <ul class="permissions-list">
        ${permissions.map(p => `<li>${p}</li>`).join('')}
      </ul>
    </div>

    <div class="action-buttons">
      <button onclick="loadUserProfile()" class="btn btn-secondary">🔄 Actualizează Profil</button>
      <a href="index.html" class="btn btn-primary" style="margin-left: 10px;">🏠 Mergi la Acasă</a>
    </div>
  `;
}

function getRolePermissions(role) {
  const permissions = {
    'DOCTOR': [
      'Creare prescripții medicale',
      'Vizualizare prescripții create',
      'Vizualizare lista medicamente',
      'Gestionare pacienți',
    ],
    'PHARMACIST': [
      'Onorare prescripții',
      'Gestionare stocuri farmacie',
      'Vizualizare alertă stoc scăzut',
      'Vizualizare lista medicamente',
      'Actualizare cantități medicamente',
    ],
    'ADMIN': [
      'Acces complet la sistem',
      'Gestionare medicamente',
      'Gestionare farmacii',
      'Gestionare farmaciști',
      'Vizualizare toate prescripțiile',
      'Gestionare stocuri',
      'Administrare utilizatori',
    ],
    'PATIENT': [
      'Vizualizare prescripții personale',
      'Vizualizare lista medicamente',
      'Istoric tratamente',
    ],
  };
  return permissions[role] || ['Vizualizare informații de bază'];
}
