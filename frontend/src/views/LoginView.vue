<!-- frontend/src/views/LoginView.vue -->
<template>
  <div class="login-wrapper">
    <div class="login-card">
      <!-- Branding -->
      <div class="brand">
        <span class="shield">🛡️</span>
        <h1>PGCC</h1>
        <p>Plateforme de Gouvernance Cyber CTF</p>
      </div>

      <!-- ÉTAPE 1 : IDENTIFIANTS -->
      <form v-if="step === 'credentials'" @submit.prevent="handleLogin" class="auth-form">
        <label for="email">Email professionnel</label>
        <input 
          id="email"
          v-model="email" 
          type="email" 
          required 
          placeholder="prenom.nom@ctf.com.tn" 
          autocomplete="username"
          :disabled="isLoading"
        />

        <label for="password">Mot de passe</label>
        <input 
          id="password"
          v-model="password" 
          type="password" 
          required 
          placeholder="••••••••" 
          autocomplete="current-password"
          :disabled="isLoading"
        />

        <button type="submit" :disabled="isLoading || !email || !password" class="primary-btn">
          {{ isLoading ? 'Connexion...' : 'Se connecter' }}
        </button>

        <p v-if="errorMessage" class="error-msg">{{ errorMessage }}</p>
      </form>

      <!-- ÉTAPE 2 : ENRÔLEMENT MFA (Nouveau compte ou réinitialisation) -->
      <div v-else-if="step === 'setup-mfa'" class="mfa-setup">
        <h2>Sécurisez votre compte</h2>
        <p>Scannez ce QR code avec Google Authenticator, Authy ou FreeOTP :</p>

        <!-- Affichage QR Code via lib qrcode.vue -->
        <div class="qr-container">
          <QrcodeVue 
            :value="provisioningUri" 
            :size="200" 
            level="H" 
            render-as="svg" 
          />
        </div>

        <p class="secret-text">
          Clé manuelle : <code>{{ mfaSecret }}</code>
        </p>

        <label for="totp-code">Entrez le code à 6 chiffres généré</label>
        <input 
          id="totp-code"
          v-model="totpCode" 
          maxlength="32" 
          placeholder="123456 ou code de secours" 
          inputmode="numeric"
          autofocus
          :disabled="isLoading"
          @keyup.enter="confirmMfaEnrollment"
        />

        <button 
          @click="confirmMfaEnrollment" 
          :disabled="!totpCode || totpCode.length !== 6 || isLoading" 
          class="primary-btn"
        >
          {{ isLoading ? 'Activation...' : 'Activer MFA et continuer' }}
        </button>

        <p v-if="errorMessage" class="error-msg">{{ errorMessage }}</p>
        
        <a href="#" @click.prevent="goBackToCredentials" class="back-link">← Retour</a>
      </div>

      <!-- ÉTAPE 3 : VÉRIFICATION MFA (Compte déjà configuré) -->
      <div v-else-if="step === 'verify-mfa'" class="mfa-verify">
        <h2>Vérification en deux étapes</h2>
        <p>Votre compte est sécurisé par MFA.<br/>Entrez le code depuis votre application :</p>

        <label for="verify-totp">Code TOTP ou code de secours</label>
        <input 
          id="totp-code"
          v-model="totpCode" 
          maxlength="32" 
          placeholder="123456 ou code de secours" 
          inputmode="numeric"
          autofocus
          :disabled="isLoading"
          @keyup.enter="confirmMfaEnrollment"
        />

        <button 
          @click="confirmMfaEnrollment" 
          :disabled="!totpCode || totpCode.length !== 6 || isLoading" 
          class="primary-btn"
        >
          {{ isLoading ? 'Activation...' : 'Activer MFA et continuer' }}
        </button>

        <p v-if="errorMessage" class="error-msg">{{ errorMessage }}</p>
        
        <a href="#" @click.prevent="goBackToCredentials" class="back-link">← Retour</a>
      </div>

      <!-- ÉTAPE 3 : VÉRIFICATION MFA (Compte déjà configuré) -->
      <div v-else-if="step === 'verify-mfa'" class="mfa-verify">
        <h2>Vérification en deux étapes</h2>
        <p>Votre compte est sécurisé par MFA.<br/>Entrez le code depuis votre application :</p>

        <label for="verify-totp">Code TOTP ou code de secours</label>
        <input 
          id="verify-totp"
          v-model="totpCode" 
          maxlength="6" 
          pattern="\d{6}" 
          placeholder="123456" 
          inputmode="numeric"
          autofocus
          :disabled="isLoading"
          @keyup.enter="verifyExistingMfa"
        />

        <button 
          @click="verifyExistingMfa" 
          :disabled="!totpCode || totpCode.length < 6 || isLoading" 
          class="primary-btn"
        >
          {{ isLoading ? 'Vérification...' : 'Valider et se connecter' }}
        </button>

        <p v-if="errorMessage" class="error-msg">{{ errorMessage }}</p>
        
        <a href="#" @click.prevent="goBackToCredentials" class="back-link">← Changer d'email</a>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import QrcodeVue from 'qrcode.vue'; // Assure-toi que npm install qrcode.vue a été fait
import { useAuthStore } from '@/stores/auth';
import apiClient from '@/services/api';

const authStore = useAuthStore();
const router = useRouter();
const route = useRoute();

// État local UI
const step = ref('credentials'); // 'credentials' | 'setup-mfa' | 'verify-mfa'
const email = ref('');
const password = ref('');
const totpCode = ref('');
const provisioningUri = ref('');
const mfaSecret = ref('');
const isLoading = ref(false);
const errorMessage = ref(null);

// Token intermédiaire pour la validation MFA
let currentPreAuthToken = null;

onMounted(() => {
  // Si déjà connecté, rediriger vers dashboard
  if (authStore.isAuthenticated) {
    router.replace(route.query.redirect || '/dashboard');
  }
});

/**
 * ÉTAPE 1 : Tentative de login
 */
async function handleLogin() {
  isLoading.value = true;
  errorMessage.value = null;
  totpCode.value = '';

  try {
    // Appel API /auth/login
    const { data } = await apiClient.post('/auth/login', {
      email: email.value,
      password: password.value,
    });

    currentPreAuthToken = data.pre_auth_token;

    // Logique métier : Comment savoir si l'utilisateur doit faire l'enrollment ou juste la vérif ?
    // Option A (Simple/Dev) : On suppose que si c'est un admin connu, il est déjà enrolled.
    // Option B (Robuste) : L'API devrait retourner un flag `mfa_status`. 
    
    // Pour la Phase 5, on utilise une heuristique rapide :
    // Si tu as déjà activé MFA via CLI (comme ton RSSI), on va directement en 'verify-mfa'.
    // Sinon, on irait en 'setup-mfa'. 
    
    // ⚠️ ATTENTION : Actuellement, notre backend ne distingue pas encore ces cas dans la réponse /login.
    // Donc on force 'verify-mfa' pour tester le flow principal du RSSI.
    // Pour un vrai nouvel utilisateur, il faudrait appeler /start-enrollment ici.
    
    if (data.mfa_enabled) {
      step.value = 'verify-mfa';
    } else {
      const enrollRes = await apiClient.post('/auth/start-enrollment', {}, {
        headers: { Authorization: `Bearer ${currentPreAuthToken}` },
      });
      provisioningUri.value = enrollRes.data.provisioning_uri;
      mfaSecret.value = enrollRes.data.secret;
      step.value = 'setup-mfa';
    }

  } catch (err) {
    errorMessage.value = err.response?.data?.detail || 'Erreur de connexion. Vérifiez vos identifiants.';
  } finally {
    isLoading.value = false;
  }
}

/**
 * ÉTAPE 2 : Confirmation Enrôlement MFA (Pour nouveaux utilisateurs)
 * NOTE : Cette fonction n'est appelée que si on décide de passer par /start-enrollment
 */
async function confirmMfaEnrollment() {
  if (!totpCode.value || totpCode.value.length !== 6) return;
  
  isLoading.value = true;
  errorMessage.value = null;

  try {
    // Le secret/QR est déjà obtenu au passage login pour un compte non enrôlé.
    // Confirmer avec le code saisi.
    const confirmRes = await apiClient.post('/auth/confirm-mfa', {
      pre_auth_token: currentPreAuthToken,
      mfa_code: totpCode.value,
    });

    // Succès -> Sauvegarde session & redirection
    authStore.setSession(confirmRes.data);
    await authStore.fetchPermissions();
    
    router.replace(route.query.redirect || '/dashboard');

  } catch (err) {
    errorMessage.value = err.response?.data?.detail || 'Échec activation MFA.';
  } finally {
    isLoading.value = false;
  }
}

/**
 * ÉTAPE 3 : Vérification MFA Existante (Pour comptes déjà configurés)
 * Utilise l'endpoint /auth/confirm-mfa mais sans passer par start-enrollment
 * car le secret est déjà en base.
 */
async function verifyExistingMfa() {
  if (!totpCode.value || totpCode.value.trim().length < 6) return;

  isLoading.value = true;
  errorMessage.value = null;

  try {
    // On appelle directement confirm-mfa avec le pre_auth_token obtenu au login
    // Le backend vérifiera le code contre le mfa_secret stocké en DB pour cet email.
    const res = await apiClient.post('/auth/confirm-mfa', {
      pre_auth_token: currentPreAuthToken,
      mfa_code: totpCode.value,
    });

    // Succès -> Sauvegarde session & redirection
    authStore.setSession(res.data);
    await authStore.fetchPermissions();
    
    router.replace(route.query.redirect || '/dashboard');

  } catch (err) {
    errorMessage.value = err.response?.data?.detail || 'Code MFA invalide ou expiré.';
  } finally {
    isLoading.value = false;
  }
}

function goBackToCredentials() {
  step.value = 'credentials';
  totpCode.value = '';
  errorMessage.value = null;
  provisioningUri.value = '';
  mfaSecret.value = '';
  currentPreAuthToken = null;
}
</script>

<style scoped>
.login-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  padding: 1rem;
}

.login-card {
  width: 100%;
  max-width: 420px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 40px rgba(0,0,0,0.3);
  padding: 2rem;
}

.brand {
  text-align: center;
  margin-bottom: 2rem;
}

.shield {
  font-size: 3rem;
  display: block;
  margin-bottom: 0.5rem;
}

.brand h1 {
  font-size: 1.8rem;
  color: #0f172a;
  margin: 0;
}

.brand p {
  color: #64748b;
  font-size: 0.9rem;
  margin-top: 0.25rem;
}

.auth-form, .mfa-setup, .mfa-verify {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

label {
  font-size: 0.85rem;
  font-weight: 600;
  color: #334155;
}

input {
  padding: 0.75rem;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 1rem;
  outline: none;
  transition: border-color 0.2s;
}

input:focus {
  border-color: #0ea5e9;
}

.primary-btn {
  padding: 0.85rem;
  background: #0ea5e9;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
  margin-top: 0.5rem;
}

.primary-btn:hover:not(:disabled) {
  background: #0284c7;
}

.primary-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error-msg {
  color: #dc2626;
  font-size: 0.85rem;
  text-align: center;
  margin-top: 0.5rem;
  background: #fef2f2;
  padding: 0.5rem;
  border-radius: 4px;
}

.qr-container {
  display: flex;
  justify-content: center;
  padding: 1rem;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px dashed #cbd5e1;
}

.secret-text {
  font-size: 0.8rem;
  color: #64748b;
  word-break: break-all;
  text-align: center;
}

.secret-text code {
  background: #f1f5f9;
  padding: 0.2rem 0.4rem;
  border-radius: 3px;
  font-family: monospace;
  color: #0f172a;
}

.back-link {
  display: block;
  text-align: center;
  margin-top: 1rem;
  color: #64748b;
  text-decoration: none;
  font-size: 0.85rem;
}

.back-link:hover {
  color: #0ea5e9;
  text-decoration: underline;
}
</style>