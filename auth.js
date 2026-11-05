/* Account and cloud trip persistence for Version B. */
(() => {
  const gate = document.querySelector('#auth-gate');
  const message = document.querySelector('#auth-message');
  const form = document.querySelector('#auth-form');
  const submit = document.querySelector('#auth-submit');
  let client = null;
  let user = null;
  let mode = 'signin';
  let trips = [];
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function status(text, isError = false) {
    message.textContent = text;
    message.classList.toggle('is-error', isError);
  }
  function showGate() {
    document.body.classList.add('auth-pending');
    gate.hidden = false;
    document.querySelector('#account-button').hidden = true;
    document.querySelector('#account-menu').hidden = true;
    trips = [];
    window.setBookingAccount?.(null);
    if (typeof trip !== 'undefined') trip = null;
    document.querySelector('#saved-trips').innerHTML = '';
  }
  async function showApp(session) {
    user = session.user;
    gate.hidden = true;
    document.body.classList.remove('auth-pending');
    const button = document.querySelector('#account-button');
    button.hidden = false;
    button.textContent = user.email || 'Account';
    document.querySelector('#account-email').textContent = user.email || 'Signed in';
    window.setBookingAccount?.(user.id);
    await loadTrips();
    window.track?.('account_signed_in', {method:user.app_metadata?.provider || 'email'});
  }
  window.voyageFetch = async (url, options = {}) => {
    if (!client) throw new Error('Account sign-in is not configured.');
    const {data:{session}} = await client.auth.getSession();
    if (!session?.access_token) { showGate(); throw new Error('Sign in to continue.'); }
    const headers = new Headers(options.headers || {});
    headers.set('Authorization', `Bearer ${session.access_token}`);
    const response = await fetch(url, {...options, headers});
    if (response.status === 401) showGate();
    return response;
  };
  async function loadTrips() {
    const {data, error} = await client.from('trips').select('id,trip,updated_at').order('updated_at', {ascending:false});
    if (error) { document.querySelector('#saved-trips').textContent = 'Could not load your trips. Refresh the page to try again.'; return; }
    trips = data || [];
    window.renderAccountTrips();
  }
  window.getSavedTrip = id => trips.find(row => row.id === id)?.trip || null;
  window.renderAccountTrips = () => {
    const el = document.querySelector('#saved-trips');
    if (!user) return;
    if (!trips.length) {
      el.innerHTML = '<div class="empty-trips"><h2>Your next journey starts here.</h2><p>Create a trip and it will be saved to your account automatically.</p><button class="button button-dark" data-view="plan">Plan a trip</button></div>';
      return;
    }
    el.innerHTML = trips.map(({id, trip: saved}) => {
      const destination = String(saved.destination || 'Your trip');
      const photo = (typeof destinations !== 'undefined' ? destinations.find(d => d.name.toLowerCase() === destination.toLowerCase()) : null)?.image;
      return `<button class="saved-card" data-saved-id="${escape(id)}">${photo ? `<img src="${escape(photo)}" alt="">` : ''}<div><p>${Number(saved.days)||1} days · ${Number(saved.travelers)||1} travellers</p><h2>${escape(destination)}</h2><p>Open your itinerary ↗</p></div></button>`;
    }).join('');
  };
  window.saveVoyageTrip = async current => {
    if (!client || !user) throw new Error('Sign in to save this trip.');
    if (!current.cloudId) current.cloudId = crypto.randomUUID();
    const copy = JSON.parse(JSON.stringify({...current, saved:true}));
    const {data, error} = await client.from('trips').upsert({id:current.cloudId,user_id:user.id,trip:copy,updated_at:new Date().toISOString()}).select('id,trip,updated_at').single();
    if (error) throw new Error('Could not save this trip. Try again.');
    current.saved = true;
    trips = [data, ...trips.filter(row => row.id !== data.id)].sort((a,b) => b.updated_at.localeCompare(a.updated_at));
    window.renderAccountTrips();
    return data;
  };
  window.persistSavedTrip = current => { if (current?.saved) window.saveVoyageTrip(current).catch(() => window.toast?.('Could not sync your latest trip changes. Try Save trip again.')); };

  document.querySelector('#auth-mode').addEventListener('click', () => {
    mode = mode === 'signin' ? 'signup' : 'signin';
    document.querySelector('#auth-title').textContent = mode === 'signup' ? 'Make room for every journey.' : 'Your journey starts here.';
    submit.textContent = mode === 'signup' ? 'Create account' : 'Sign in';
    document.querySelector('#auth-mode').textContent = mode === 'signup' ? 'Already have an account? Sign in' : 'New to Voyage? Create an account';
    document.querySelector('#auth-password').autocomplete = mode === 'signup' ? 'new-password' : 'current-password';
    status('');
  });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (!client) return status('Account sign-in is not configured yet.', true);
    submit.disabled = true;
    const email = document.querySelector('#auth-email').value.trim();
    const password = document.querySelector('#auth-password').value;
    const result = mode === 'signup'
      ? await client.auth.signUp({email,password,options:{emailRedirectTo:location.origin+'/version-b'}})
      : await client.auth.signInWithPassword({email,password});
    submit.disabled = false;
    if (result.error) return status(result.error.message, true);
    if (mode === 'signup' && !result.data.session) status('Check your email to confirm your account, then sign in.');
    else if (result.data.session) await showApp(result.data.session);
  });
  document.querySelector('#auth-google').addEventListener('click', async () => {
    if (!client) return status('Account sign-in is not configured yet.', true);
    const {error} = await client.auth.signInWithOAuth({provider:'google',options:{redirectTo:location.origin+'/version-b'}});
    if (error) status(error.message, true);
  });
  document.querySelector('#account-button').addEventListener('click', () => {
    const menu = document.querySelector('#account-menu');
    menu.hidden = !menu.hidden;
  });
  document.querySelector('#account-signout').addEventListener('click', async () => {
    await client.auth.signOut();
    user = null;
    showGate();
    window.track?.('account_signed_out');
  });
  (async () => {
    try {
      const response = await fetch('/auth-config');
      const config = await response.json();
      if (!config.url || !config.anon_key || !window.supabase?.createClient) {
        status('Account setup is pending. Add your Supabase URL and publishable key to start using Voyage.', true);
        return;
      }
      client = window.supabase.createClient(config.url, config.anon_key, {auth:{detectSessionInUrl:true,persistSession:true,autoRefreshToken:true}});
      const {data:{session}} = await client.auth.getSession();
      if (session) await showApp(session);
      else showGate();
      client.auth.onAuthStateChange((event, session) => {
        if (event === 'SIGNED_OUT') {user = null; showGate();}
        if (event === 'SIGNED_IN' && session && user?.id !== session.user.id) showApp(session);
      });
    } catch { status('Could not load account sign-in. Refresh the page to try again.', true); }
  })();
})();
