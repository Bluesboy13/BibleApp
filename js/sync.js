// Google sign-in and sync of ribbon, bookmarks and reading plan via Firebase.
import { firebaseConfig } from './firebase-config.js';
import {
  initializeApp, getAuth, GoogleAuthProvider, signInWithPopup, signOut, onAuthStateChanged,
  getFirestore, doc, getDoc, setDoc,
} from '../vendor/firebase.js';

const K = window.KJV;
const statusEl = document.getElementById('sync-status');
const btn = document.getElementById('sync-btn');

let user = null;
let pushTimer = 0;
let lastSynced = null;
let message = '';

function render() {
  btn.hidden = false;
  btn.textContent = user ? 'Sign out' : 'Sign in with Google';
  if (message) statusEl.textContent = message;
  else if (user) {
    const when = lastSynced ? ` · synced ${lastSynced.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}` : '';
    statusEl.textContent = `Signed in as ${user.email}${when}`;
  } else {
    statusEl.textContent = 'Sign in to keep your ribbon, bookmarks and reading plan in step on all your devices.';
  }
}

if (!firebaseConfig.apiKey) {
  statusEl.textContent = 'Sync is not set up yet.';
  K.releaseHold();
} else {
  const app = initializeApp(firebaseConfig);
  const auth = getAuth(app);
  const db = getFirestore(app);
  const userDoc = () => doc(db, 'users', user.uid);

  async function push() {
    clearTimeout(pushTimer);
    pushTimer = 0;
    if (!user) return;
    await setDoc(userDoc(), K.syncData());
    lastSynced = new Date();
    message = '';
    render();
  }

  async function pull() {
    if (!user) return;
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
      K.toast('This Google account is not on the approved list.');
      message = `${user ? user.email : 'That account'} is not approved for sync. Ask the owner to add it.`;
      signOut(auth);
    } else {
      message = user ? `Signed in as ${user.email} · offline, will sync when connected` : '';
    }
    render();
  }

  onAuthStateChanged(auth, async (u) => {
    user = u;
    render();
    if (u) await pull();
    K.releaseHold();
  });

  btn.addEventListener('click', async () => {
    if (user) {
      if (pushTimer) await push().catch(() => {});
      await signOut(auth);
      K.setUid(null);
      message = '';
      render();
      return;
    }
    message = '';
    try {
      const provider = new GoogleAuthProvider();
      provider.setCustomParameters({ prompt: 'select_account' });
      await signInWithPopup(auth, provider);
    } catch (e) {
      if (e && e.code !== 'auth/popup-closed-by-user' && e.code !== 'auth/cancelled-popup-request') {
        K.toast('Sign-in did not complete. Please try again.');
      }
    }
  });

  // Send changes a few seconds after they happen; check for newer data when the app comes back.
  document.addEventListener('kjv:changed', () => {
    if (!user) return;
    clearTimeout(pushTimer);
    pushTimer = setTimeout(() => push().catch(handleError), 3000);
  });
  document.addEventListener('visibilitychange', () => {
    if (!user) return;
    if (document.visibilityState === 'visible') pull();
    else if (pushTimer) push().catch(() => {});
  });
  window.addEventListener('online', pull);
}
