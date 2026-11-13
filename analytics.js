/* One event vocabulary is sent to every configured analytics provider. */
(() => {
  const CONSENT_KEY = 'voyage_analytics_consent';
  const isVersionB = window.location.pathname === '/version-b';
  const variant = isVersionB ? 'B' : 'A';
  const experimentId = 'voyage_ab_v1';
  const assignedVariant = document.cookie.split('; ').find(part => part.startsWith('voyage_ab_v1='))?.split('=')[1];
  const isAssignedVisit = new URLSearchParams(window.location.search).get('experiment') === experimentId
    && assignedVariant === variant;
  const configPromise = fetch('/analytics-config').then(r => r.ok ? r.json() : {}).catch(() => ({}));
  let enabled = false;
  const providers = [];

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = src;
      script.async = true;
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }

  function track(name, properties = {}) {
    if (!enabled) return;
    // Only callers' predefined fields are sent. Never send prompts or itinerary text.
    const data = { ...properties, app: 'voyage', schema_version: 1, experiment_variant: variant,
      ...(isAssignedVisit ? { experiment_id: experimentId, assignment_type: 'randomized' } : {}) };
    for (const provider of providers) {
      try { provider(name, data); } catch (error) { console.warn('Analytics event failed', error); }
    }
  }

  async function initialize() {
    if (enabled) return;
    enabled = true;
    const config = await configPromise;

    if (config.ga_measurement_id) {
      window.dataLayer = window.dataLayer || [];
      window.gtag = function () { window.dataLayer.push(arguments); };
      window.gtag('js', new Date());
      window.gtag('config', config.ga_measurement_id, { send_page_view: false });
      providers.push((name, data) => window.gtag('event', name, data));
      loadScript(`https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(config.ga_measurement_id)}`).catch(console.warn);
    }
    if (config.mixpanel_token) {
      // The CDN bundle expects Mixpanel's queue/bootstrap object to exist first.
      const mixpanel = window.mixpanel = window.mixpanel || [];
      mixpanel._i = [];
      mixpanel.__SV = 1.2;
      mixpanel.init = (token, options) => {
        mixpanel.track = (...args) => mixpanel.push(['track', ...args]);
        mixpanel._i.push([token, options, 'mixpanel']);
      };
      const mixpanelOptions = {
        autocapture: false,
        track_pageview: false,
      };
      if (config.mixpanel_api_host) mixpanelOptions.api_host = config.mixpanel_api_host;
      mixpanel.init(config.mixpanel_token, mixpanelOptions);
      providers.push((name, data) => window.mixpanel.track(name, data));
      loadScript('https://cdn.mxpnl.com/libs/mixpanel-2-latest.min.js').catch(console.warn);
    }
    if (config.amplitude_api_key) {
      loadScript('https://cdn.amplitude.com/libs/analytics-browser-2.48.1-min.js.gz').then(() => {
        window.amplitude.init(config.amplitude_api_key, { autocapture: false });
        providers.push((name, data) => window.amplitude.track(name, data));
        window.amplitude.track('page_view', { page_name: isVersionB ? 'version_b' : 'planner', app: 'voyage', schema_version: 1,
          experiment_variant: variant, ...(isAssignedVisit ? {experiment_id: experimentId, assignment_type:'randomized'} : {}) });
        if (isAssignedVisit) window.amplitude.track('experiment_exposure', {
          app:'voyage', schema_version:1, experiment_variant:variant, experiment_id:experimentId, assignment_type:'randomized'
        });
      }).catch(console.warn);
    }
    if (config.posthog_project_token) {
      // PostHog's browser snippet queues events until its SDK is ready.
      !function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split('.');2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement('script')).type='text/javascript',p.crossOrigin='anonymous',p.async=!0,p.src=s.api_host.replace('.i.posthog.com','-assets.i.posthog.com')+'/static/array.js',(r=t.getElementsByTagName('script')[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a='posthog',u.people=u.people||[],o='init capture opt_out_capturing'.split(' '),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);
      window.posthog.init(config.posthog_project_token, {
        api_host: config.posthog_host,
        defaults: '2026-05-30',
        autocapture: false,
        capture_pageview: false,
        capture_pageleave: false,
        disable_session_recording: true,
      });
      providers.push((name, data) => window.posthog.capture(name, data));
    }
    track('page_view', { page_name: isVersionB ? 'version_b' : 'planner' });
    if (isAssignedVisit) track('experiment_exposure');
  }

  function choose(value) {
    const wasEnabled = enabled;
    localStorage.setItem(CONSENT_KEY, value);
    document.getElementById('analyticsConsent').hidden = true;
    if (value === 'yes') initialize();
    if (value === 'no' && wasEnabled) window.location.reload();
  }

  window.analyticsTrack = track;
  window.setAnalyticsConsent = choose;
  window.openAnalyticsSettings = () => { document.getElementById('analyticsConsent').hidden = false; };
  if (localStorage.getItem(CONSENT_KEY) === 'yes') initialize();
  else if (!localStorage.getItem(CONSENT_KEY)) document.getElementById('analyticsConsent').hidden = false;
})();
