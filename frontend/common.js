// Common JavaScript functions shared across all role pages
console.log('=== COMMON.JS LOADED ===');
console.log('=== COMMON.JS: Keycloak library available?', typeof Keycloak !== 'undefined');
const API_BASE = 'http://localhost:8080/api';
const keycloak = new Keycloak({
  url: 'http://localhost:8081',
  realm: 'medihelp',
  clientId: 'medihelp-frontend',
});

let currentUserProfile = null;

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

// Load user profile
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
    return data;
  } catch (err) {
    console.error('Error loading user profile:', err);
    throw err;
  }
}

// Show alert
function showAlert(containerId, message, type = 'info') {
  const container = document.getElementById(containerId);
  if (!container) return;
  const alert = document.createElement('div');
  alert.className = `alert alert-${type}`;
  alert.textContent = message;
  container.innerHTML = '';
  container.appendChild(alert);
  setTimeout(() => alert.remove(), 5000);
}

// Initialize auth UI
function initAuthUI() {
  // Login button
  const btnLogin = document.getElementById('btn-login');
  if (btnLogin) {
    btnLogin.onclick = () => keycloak.login();
  }
  
  // Logout button
  const btnLogout = document.getElementById('btn-logout');
  if (btnLogout) {
    btnLogout.onclick = () => {
      keycloak.logout({ redirectUri: window.location.origin });
    };
  }
  
  // Profile link
  const profileLink = document.getElementById('profile-link');
  if (profileLink) {
    profileLink.onclick = (e) => {
      e.preventDefault();
      window.location.href = 'profile.html';
    };
  }
}

// Update auth status in header
function updateAuthStatus(authenticated) {
  const authStatus = document.getElementById('auth-status');
  if (authStatus) {
    authStatus.innerHTML = authenticated 
      ? 'Status: <strong style="color:green">autentificat</strong>'
      : 'Status: <strong style="color:red">neautentificat</strong>';
  }
  
  const btnLogin = document.getElementById('btn-login');
  const btnLogout = document.getElementById('btn-logout');
  const profileLink = document.getElementById('profile-link');
  
  if (btnLogin) btnLogin.disabled = authenticated;
  if (btnLogout) btnLogout.disabled = !authenticated;
  if (profileLink) {
    profileLink.style.display = authenticated ? 'inline-block' : 'none';
  }
}

// Check if user is authenticated and has correct role
async function checkRoleAndRedirect(expectedRole = null) {
  try {
    const authenticated = await keycloak.init({ onLoad: 'check-sso', checkLoginIframe: false });
    
    if (!authenticated) {
      updateAuthStatus(false);
      initAuthUI();
      return null;
    }
    
    updateAuthStatus(true);
    initAuthUI();
    
    const profile = await loadUserProfile();
    
    // If expected role is specified, check if user has it
    if (expectedRole && profile.role !== expectedRole) {
      // Redirect to correct page for this role
      redirectToRolePage(profile.role);
      return null;
    }
    
    return profile;
  } catch (err) {
    console.error('Error checking role:', err);
    updateAuthStatus(false);
    initAuthUI();
    return null;
  }
}

// Redirect to role-specific page
function redirectToRolePage(role) {
  const rolePages = {
    'DOCTOR': 'doctor.html',
    'PHARMACIST': 'pharmacist.html',
    'ADMIN': 'admin.html',
    'PATIENT': 'doctor.html', // Pacienții folosesc aceeași interfață ca doctorii (doar vizualizare)
  };
  
  const targetPage = rolePages[role];
  const currentPage = window.location.pathname.split('/').pop() || 'index.html';
  
  if (targetPage && currentPage !== targetPage) {
    console.log(`Redirecting ${role} from ${currentPage} to ${targetPage}`);
    window.location.replace(targetPage); // Use replace instead of href to prevent back button issues
  } else if (targetPage) {
    console.log(`Already on correct page: ${targetPage}`);
  } else {
    console.error(`No page mapping found for role: ${role}`);
  }
}

// Check role access for specific pages
async function checkRoleAccess(expectedRoles) {
  try {
    console.log('checkRoleAccess: Starting, expectedRoles:', expectedRoles);
    
    // Check if keycloak is already initialized
    let authenticated;
    if (keycloak.authenticated !== undefined) {
      // Already initialized, use current state
      authenticated = keycloak.authenticated;
      console.log('checkRoleAccess: Keycloak already initialized, authenticated:', authenticated);
    } else {
      // Not initialized yet, initialize it
      console.log('checkRoleAccess: Initializing Keycloak...');
      authenticated = await keycloak.init({ onLoad: 'check-sso', checkLoginIframe: false });
      console.log('checkRoleAccess: Keycloak init result:', authenticated);
    }
    
    if (!authenticated) {
      console.log('checkRoleAccess: Not authenticated, redirecting to login...');
      keycloak.login();
      return null;
    }
    
    updateAuthStatus(true);
    initAuthUI();
    
    console.log('checkRoleAccess: Loading user profile...');
    let profile;
    try {
      profile = await loadUserProfile();
      console.log('checkRoleAccess: Profile loaded:', profile);
    } catch (profileErr) {
      console.error('checkRoleAccess: Error loading profile:', profileErr);
      // Don't throw, return null so the page can show an error message
      updateAuthStatus(false);
      return null;
    }
    
    if (!profile || !profile.role) {
      console.error('checkRoleAccess: Profile missing or has no role');
      updateAuthStatus(false);
      return null;
    }
    
    const allowedRoles = Array.isArray(expectedRoles) ? expectedRoles : [expectedRoles];
    console.log('checkRoleAccess: Allowed roles:', allowedRoles, 'User role:', profile.role);
    
    // ADMIN can always access, or if role is in allowedRoles
    if (profile.role === 'ADMIN' || allowedRoles.includes(profile.role)) {
      console.log('checkRoleAccess: Access granted');
      return profile;
    }
    
    // Role not allowed, redirect to correct page
    console.log('checkRoleAccess: Access denied, redirecting to role page...');
    redirectToRolePage(profile.role);
    return null;
  } catch (err) {
    console.error('checkRoleAccess: Unexpected error:', err);
    updateAuthStatus(false);
    initAuthUI();
    return null; // Return null instead of throwing, so page can handle it
  }
}
