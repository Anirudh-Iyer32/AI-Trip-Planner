/* Evidence-led travel offer check. No listing details are sent to analytics. */
(() => {
  const safe = value => String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
  const link = (url, label) => /^https:\/\/[^\s]+$/i.test(url || '') ? `<a href="${safe(url)}" target="_blank" rel="noopener noreferrer">${safe(label)} ↗</a>` : '';
  const form = document.querySelector('#offer-form');
  const results = document.querySelector('#offer-results');
  const status = document.querySelector('#offer-status');
  function render(data) {
    const counts = {match:0,review:0,unknown:0};
    data.evidence.forEach(item => {if (counts[item.status] !== undefined) counts[item.status] += 1;});
    const findings = data.evidence.map(item => `<article class="offer-finding offer-${safe(item.status)}"><div><span class="offer-status-label">${item.status === 'match' ? 'Found' : item.status === 'review' ? 'Check before paying' : 'Unconfirmed'}</span><h3>${safe(item.title)}</h3><p>${safe(item.detail)}</p>${link(item.source_url,item.source_label || 'View source')}</div></article>`).join('');
    const sources = data.independent_sources?.length ? data.independent_sources.map(item => `<li><strong>${safe(item.title)}</strong><p>${safe(item.snippet)}</p>${link(item.url, 'Open independent page')}</li>`).join('') : '<li>Independent web pages were not available for this search. Try another name or check the operator directly.</li>';
    results.innerHTML = `<div class="offer-results-head"><div><h2>What we found</h2><p>Checked ${safe(data.checked_on)} · ${safe(data.offer.name)} in ${safe(data.offer.destination)}</p></div><div class="offer-result-count"><strong>${counts.review + counts.unknown}</strong><span>open questions</span></div></div><div class="offer-result-intro"><p>${safe(data.summary)}</p></div><div class="offer-evidence-list">${findings}</div><section class="offer-sources"><h2>Independent pages to review</h2><p>Search results are leads for your own verification; their appearance does not endorse the seller.</p><ul>${sources}</ul></section><div class="offer-next"><h2>Before sending money</h2><ol><li>Call the property or operator using a number you found independently.</li><li>Confirm the exact dates, total price, cancellation terms and who receives payment.</li><li>Keep copies of the offer and payment terms.</li></ol><div class="offer-feedback"><span>Was this check useful?</span><button type="button" data-offer-feedback="yes">Yes</button><button type="button" data-offer-feedback="no">Not yet</button></div></div>`;
    results.querySelectorAll('.offer-finding a,.offer-sources a').forEach(anchor => anchor.addEventListener('click', () => track('offer_evidence_opened', {area:anchor.closest('.offer-sources') ? 'independent' : 'finding'})));
    results.querySelectorAll('[data-offer-feedback]').forEach(button => button.addEventListener('click', () => {track('offer_feedback_submitted', {helpful:button.dataset.offerFeedback === 'yes'});results.querySelector('.offer-feedback').textContent='Thanks. Your feedback helps us improve these checks.';}));
    track('offer_check_completed', {findings:counts.match, needs_review:counts.review, unknown:counts.unknown, had_maps_data:!!data.sources_used?.maps, had_web_data:!!data.sources_used?.web});
  }
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const payload = {name:document.querySelector('#offer-name').value.trim(),destination:document.querySelector('#offer-destination').value.trim(),listing_url:document.querySelector('#offer-url').value.trim(),advertised_price:document.querySelector('#offer-price').value.trim(),contact:document.querySelector('#offer-contact').value.trim(),payment_method:document.querySelector('#offer-payment').value,offer_notes:document.querySelector('#offer-notes').value.trim()};
    const button = document.querySelector('#offer-check');button.disabled=true;button.textContent='Checking independent sources…';status.textContent='Comparing the listing with independent information…';results.innerHTML='';
    track('offer_check_started', {has_listing_url:!!payload.listing_url, has_contact:!!payload.contact, payment_method:payload.payment_method});
    try {
      const response = await window.voyageFetch('/api/v2/offers/check', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not check this offer. Try again.');
      status.textContent='';render(data);
    } catch(error) {status.textContent=error.message;track('offer_check_failed');}
    finally {button.disabled=false;button.innerHTML='Check this offer <span aria-hidden="true">↗</span>';}
  });
  document.addEventListener('click', event => {if (event.target.closest('[data-view="offer"]')) track('offer_workspace_viewed');});
})();
