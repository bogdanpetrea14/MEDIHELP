const keycloak = new Keycloak({
  url: 'http://localhost:8081', 
  realm: 'medihelp',
  clientId: 'medihelp-frontend',
});

const btnLogin = document.getElementById('btn-login');
const btnLogout = document.getElementById('btn-logout');
const btnRegister = document.getElementById('btn-register');
const btnMe = document.getElementById('btn-me');

const authStatus = document.getElementById('auth-status');
const tokenPreview = document.getElementById('token-preview');
const userinfoDiv = document.getElementById('userinfo');
const meResponse = document.getElementById('me-response');

function updateUIAuthenticated() {
  authStatus.innerHTML = 'Status: <strong style="color:green">autentificat</strong>';
  btnLogin.disabled = true;
  btnLogout.disabled = false;
  btnMe.disabled = false;

  const token = keycloak.token || '';
  tokenPreview.textContent =
    token.length > 60 ? token.slice(0, 60) + '...' : (token || 'n/a');

  const tokenParsed = keycloak.tokenParsed || {};
  const username = tokenParsed.preferred_username || tokenParsed.sub || 'n/a';
  const roles = (tokenParsed.realm_access && tokenParsed.realm_access.roles) || [];

  userinfoDiv.innerHTML = `
    <p><strong>Username:</strong> ${username}</p>
    <p><strong>Roluri (realm):</strong> ${
      roles.length ? roles.map(r => `<span class="badge">${r}</span>`).join(' ') : 'n/a'
    }</p>
  `;
}

function updateUINotAuthenticated() {
  authStatus.innerHTML = 'Status: <strong style="color:red">neautentificat</strong>';
  btnLogin.disabled = false;
  btnLogout.disabled = true;
  btnMe.disabled = true;
  tokenPreview.textContent = 'n/a';
  userinfoDiv.innerHTML = '';
  meResponse.textContent = 'n/a';
}

btnLogin.onclick = () => {
  keycloak.login();
};

btnLogout.onclick = () => {
  keycloak.logout({ redirectUri: window.location.origin });
};

btnRegister.onclick = () => {
  keycloak.register();
};

btnMe.onclick = async () => {
  try {
    await keycloak.updateToken(30);
    const resp = await fetch('http://localhost:8080/api/user/me', {
      headers: {
        Authorization: 'Bearer ' + keycloak.token,
      },
    });
    const data = await resp.json();
    meResponse.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    meResponse.textContent = 'Eroare la apel /api/user/me:\n' + err;
  }
};

keycloak
  .init({ onLoad: 'check-sso', checkLoginIframe: false })
  .then(authenticated => {
    if (authenticated) {
      updateUIAuthenticated();
    } else {
      updateUINotAuthenticated();
    }
  })
  .catch(err => {
    console.error('Eroare init Keycloak:', err);
    updateUINotAuthenticated();
  });
