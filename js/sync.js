// Sign-in (Google, or email and password) and sync of the reader's place, bookmarks, saved verses
// and reading plan via Firebase.
import { firebaseConfig } from './firebase-config.js';
import {
  initializeApp, getAuth, GoogleAuthProvider, signInWithPopup, signOut, onAuthStateChanged,
  createUserWithEmailAndPassword, signInWithEmailAndPassword, sendPasswordResetEmail, sendEmailVerification,
  getFirestore, doc, getDoc, setDoc,
} from '../vendor/firebase.js';

const K = window.KJV;
const $ = (s) => document.querySelector(s);
const statusEl = $('#sync-status');
const summaryEl = $('#account-summary');

let user = null;
let pushTimer = 0;
let lastSynced = null;
let message = '';

// Email accounts must confirm their address before they can sync (Google accounts already are).
const canSync = () => user && (user.emailVerified || user.providerData.some((p) => p.providerId === 'google.com'));

function render() {
  $('#acct-out').hidden = !!user;
  $('#acct-in').hidden = !user;
  $('#acct-verify').hidden = !user || canSync();
  if (message) statusEl.textContent = message;
  else if (user) {
    const when = lastSynced ? ` · synced ${lastSynced.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}` : '';
    statusEl.textContent = `Signed in as ${user.email}${canSync() ? when : ''}`;
  } else {
    statusEl.textContent = 'Sign in to save your progress and keep it in step on all your devices.';
  }
  summaryEl.textContent = user ? `Signed in · ${user.email}` : 'Sign in to save your progress';
}

const friendly = (e) => ({
  'auth/invalid-credential': 'That email and password don’t match.',
  'auth/wrong-password': 'That email and password don’t match.',
  'auth/user-not-found': 'There’s no account with that email. Tap “Create account”.',
  'auth/email-already-in-use': 'There’s already an account with that email. Tap “Sign in”.',
  'auth/weak-password': 'Please use a password of at least 6 characters.',
  'auth/invalid-email': 'That doesn’t look like an email address.',
  'auth/too-many-requests': 'Too many tries. Please wait a minute and try again.',
  'auth/network-request-failed': 'No connection. Please try again when you’re online.',
  'auth/operation-not-allowed': 'This sign-in method isn’t switched on yet.',
}[e && e.code] || 'That didn’t work. Please try again.');

if (!firebaseConfig.apiKey) {
  statusEl.textContent = 'Sign-in isn’t set up yet.';
  summaryEl.textContent = 'Sign-in coming soon';
  K.releaseHold();
} else {
  const app = initializeApp(firebaseConfig);
  const auth = getAuth(app);
  const db = getFirestore(app);
  const userDoc = () => doc(db, 'users', user.uid);

  async function push() {
    clearTimeout(pushTimer);
    pushTimer = 0;
    if (!canSync()) return;
    await setDoc(userDoc(), K.syncData());
    lastSynced = new Date();
    message = '';
    render();
  }

  async function pull() {
    if (!canSync()) return;
    try {
      const snap = await getDoc(userDoc());
      const local = K.syncData();
      if (!snap.exists()) {
        K.setUid(user.uid);
        await push();
      } else {
        const remote = snap.data();
        if (K.uid !== user.uid) {
          K.applyRemote(remote, user.uid);   // first sync on this device: merge
          await push();
        } else if ((remote.updatedAt || 0) > local.updatedAt) {
          K.applyRemote(remote, user.uid);
        } else if (local.updatedAt > (remote.updatedAt || 0)) {
          await push();
        }
      }
      lastSynced = new Date();
      message = '';
      render();
    } catch (e) {
      handleError(e);
    }
  }

  function handleError(e) {
    if (e && e.code === 'permission-denied') {
      message = `${user ? user.email : 'This account'} can’t sync yet. Ask the owner of the app to approve it.`;
    } else {
      message = user ? `Signed in as ${user.email} · offline, will sync when connected` : '';
    }
    render();
  }

  onAuthStateChanged(auth, async (u) => {
    user = u;
    message = '';
    render();
    if (u) await pull();
    K.releaseHold();
  });

  const busy = async (fn) => {
    message = '';
    try { await fn(); } catch (e) { K.toast(friendly(e)); message = friendly(e); }
    render();
  };
  const creds = () => [$('#acct-email').value.trim(), $('#acct-pass').value];

  $('#btn-google').addEventListener('click', () => busy(async () => {
    const provider = new GoogleAuthProvider();
    provider.setCustomParameters({ prompt: 'select_account' });
    try {
      await signInWithPopup(auth, provider);
    } catch (e) {
      if (e && (e.code === 'auth/popup-closed-by-user' || e.code === 'auth/cancelled-popup-request')) return;
      throw e;
    }
  }));
  $('#acct-form').addEventListener('submit', (e) => {
    e.preventDefault();
    busy(() => signInWithEmailAndPassword(auth, ...creds()));
  });
  $('#btn-signup').addEventListener('click', () => busy(async () => {
    const [email, pass] = creds();
    if (!email || pass.length < 6) throw { code: !email ? 'auth/invalid-email' : 'auth/weak-password' };
    const cred = await createUserWithEmailAndPassword(auth, email, pass);
    await sendEmailVerification(cred.user);
    K.toast('Account created. Check your inbox to confirm your email.');
  }));
  $('#btn-forgot').addEventListener('click', () => busy(async () => {
    const [email] = creds();
    if (!email) throw { code: 'auth/invalid-email' };
    await sendPasswordResetEmail(auth, email);
    K.toast('Password reset email sent.');
  }));
  $('#btn-resend').addEventListener('click', () => busy(async () => {
    await sendEmailVerification(user);
    K.toast('Confirmation email sent again.');
  }));
  $('#btn-recheck').addEventListener('click', () => busy(async () => {
    await user.reload();
    await user.getIdToken(true);   // refresh so the database sees the confirmed email
    user = auth.currentUser;
    if (canSync()) { K.toast('Email confirmed. Syncing…'); await pull(); } else K.toast('Not confirmed yet. Please use the link in the email.');
  }));
  $('#btn-signout').addEventListener('click', async () => {
    if (pushTimer) await push().catch(() => {});
    await signOut(auth);
    K.setUid(null);
    message = '';
    render();
  });

  // Send changes a few seconds after they happen; check for newer data when the app comes back.
  document.addEventListener('kjv:changed', () => {
    if (!canSync()) return;
    clearTimeout(pushTimer);
    pushTimer = setTimeout(() => push().catch(handleError), 3000);
  });
  document.addEventListener('visibilitychange', () => {
    if (!canSync()) return;
    if (document.visibilityState === 'visible') pull();
    else if (pushTimer) push().catch(() => {});
  });
  window.addEventListener('online', pull);
}
