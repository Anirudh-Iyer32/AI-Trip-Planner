/* Booking verification workspace. Uploaded documents are never written to localStorage. */
(() => {
  let key = null;
  let resolvedKey = null;
  const safe = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  let bookings = [];
  let issues = [];
  let resolved = [];
  window.setBookingAccount = id => {
    key = id ? `voyage_b_bookings_${id}` : null;
    resolvedKey = id ? `voyage_b_booking_resolved_${id}` : null;
    try {bookings = key ? JSON.parse(localStorage.getItem(key) || '[]') : []; if (!Array.isArray(bookings)) bookings = [];} catch {bookings = [];}
    try {resolved = resolvedKey ? JSON.parse(localStorage.getItem(resolvedKey) || '[]') : []; if (!Array.isArray(resolved)) resolved = [];} catch {resolved = [];}
    issues = [];
    render();
    if (id) check();
  };
  const save = () => {if (key) localStorage.setItem(key, JSON.stringify(bookings));};
  const format = value => value ? new Date(value).toLocaleString('en-IN', {dateStyle:'medium', timeStyle:value.includes('T')?'short':undefined}) : 'Date not set';
  function render() {
    const list = [...bookings].sort((a,b) => (a.start_at || '9999').localeCompare(b.start_at || '9999'));
    document.querySelector('#booking-count').textContent = `${bookings.length} ${bookings.length === 1 ? 'booking' : 'bookings'} on this device`;
    document.querySelector('#booking-timeline').innerHTML = list.length ? list.map(booking => {
      const count = issues.filter(issue => issue.booking_id === booking.id && !resolved.includes(`${booking.id}:${issue.message}`)).length;
      return `<article class="booking-row"><div class="booking-date"><strong>${safe(booking.start_at ? format(booking.start_at) : 'Date needed')}</strong><span>${safe(booking.kind)}</span></div><div class="booking-entry"><div class="booking-entry-top"><h3>${safe(booking.provider || booking.destination || 'Untitled booking')}</h3><span class="booking-pill ${count ? 'needs-review' : ''}">${count ? `${count} to review` : 'Details saved'}</span></div><p>${safe([booking.origin && booking.destination ? `${booking.origin} → ${booking.destination}` : booking.destination || booking.origin, booking.reference && `Ref ${booking.reference}`].filter(Boolean).join(' · ') || 'Add route or booking details')}</p><p class="booking-source">${booking.source_name ? `From ${safe(booking.source_name)} · ` : ''}${booking.confidence === 'review' ? 'Check extracted details against your confirmation' : 'Entered or confirmed by you'}</p><button class="text-button" data-booking-edit="${safe(booking.id)}">Review details ↗</button></div></article>`;
    }).join('') : `<div class="booking-empty"><h3>Your journey starts with one confirmation.</h3><p>Add a flight, train, stay, or activity booking. VOYAGE will place it on a timeline and help you check the details.</p><button class="button button-dark" id="booking-empty-add">Add your first booking</button></div>`;
    const active = issues.filter(issue => !resolved.includes(`${issue.booking_id}:${issue.message}`));
    document.querySelector('#booking-issues').innerHTML = active.length ? `<div class="booking-alert"><strong>${active.length} ${active.length === 1 ? 'detail needs' : 'details need'} review</strong><p>These are possible issues based on saved details. Check the original confirmations before changing travel plans.</p><ul>${active.map(issue => `<li>${safe(issue.message)} <button data-issue-resolve="${safe(issue.booking_id)}" data-issue-message="${safe(issue.message)}">Mark reviewed</button></li>`).join('')}</ul></div>` : '';
  }
  async function check() {
    if (!bookings.length) {issues = []; render(); return;}
    try {
      const response = await window.voyageFetch('/api/v2/bookings/check', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({bookings})});
      if (!response.ok) throw new Error('Check unavailable');
      issues = (await response.json()).issues || [];
      track('booking_check_completed', {booking_count:bookings.length, issue_count:issues.length});
    } catch {issues = []; toast('Bookings saved. The cross-booking check is temporarily unavailable.');}
    render();
  }
  function form(booking = {}) {
    const editing = Boolean(booking.id);
    drawer(editing ? 'Review booking' : 'Add a booking', `${editing ? '<p>Check each detail against your original confirmation before saving.</p>' : '<p>Upload a confirmation to fill the form, or enter the details yourself.</p><label class="booking-upload">Choose a PDF or image<input id="booking-file" type="file" accept="application/pdf,image/jpeg,image/png,image/webp"></label><p class="fine-print">PDF, PNG, JPEG, or WebP · up to 8 MB. Files are sent to the configured AI provider for extraction and are not saved in this browser.</p><p id="booking-upload-status" role="status"></p>'}<form id="booking-form"><div class="booking-form-grid"><label>Booking type<select name="kind"><option value="flight">Flight</option><option value="train">Train</option><option value="hotel">Hotel</option><option value="activity">Activity</option><option value="other">Other</option></select></label><label>Provider or property<input name="provider" maxlength="120" placeholder="Airline, hotel, or operator"></label><label>Booking reference<input name="reference" maxlength="100" placeholder="As shown on confirmation"></label><label>Traveler name<input name="traveler" maxlength="120" placeholder="As shown on confirmation"></label><label>Starts<input name="start_at" type="datetime-local"></label><label>Ends<input name="end_at" type="datetime-local"></label><label>From / location<input name="origin" maxlength="120" placeholder="Airport, station, or area"></label><label>To / destination<input name="destination" maxlength="120" placeholder="Airport, city, or property"></label></div><p class="fine-print" id="booking-source-label">${booking.source_name ? `Source: ${safe(booking.source_name)}` : 'Manually entered details'}</p><div class="booking-form-actions"><button class="button button-dark" type="submit">${editing ? 'Save corrections' : 'Save booking'}</button>${editing ? '<button class="button button-quiet" type="button" id="booking-delete">Delete booking</button>' : ''}</div><p id="booking-form-error" class="form-error" role="alert" hidden></p></form>`);
    const element = document.querySelector('#booking-form');
    const fill = data => {for (const field of element.elements) if (field.name && data[field.name] != null) field.value = data[field.name];};
    fill(booking);
    let sourceName = booking.source_name || '';
    let extracted = booking.confidence === 'review';
    document.querySelector('#booking-file')?.addEventListener('change', async event => {
      const file = event.target.files?.[0]; if (!file) return;
      const status = document.querySelector('#booking-upload-status');
      if (file.size > 8_000_000) {status.textContent = 'Choose a file smaller than 8 MB.';return;}
      if (!['application/pdf','image/jpeg','image/png','image/webp'].includes(file.type)) {status.textContent = 'Choose a PDF, PNG, JPEG, or WebP file.';return;}
      status.textContent = 'Reading confirmation…';
      track('booking_upload_started', {file_type:file.type});
      try {
        const dataUrl = await new Promise((resolve,reject) => {const reader = new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file);});
        const response = await window.voyageFetch('/api/v2/bookings/extract', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({filename:file.name,mime_type:file.type,data_base64:String(dataUrl).split(',')[1]})});
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Could not read this confirmation.');
        fill(data);sourceName=file.name;extracted=true;
        document.querySelector('#booking-source-label').textContent = `Source: ${file.name} · verify the extracted fields`;
        status.textContent = 'Details extracted. Review every field, then save.';
        track('booking_extraction_completed', {booking_type:data.kind, file_type:file.type});
      } catch (error) {status.textContent = error.message;track('booking_extraction_failed', {file_type:file.type});}
    });
    element.addEventListener('submit', event => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(element));
      if (!data.provider.trim() && !data.destination.trim()) {const error=document.querySelector('#booking-form-error');error.textContent='Enter a provider or destination to save this booking.';error.hidden=false;return;}
      if (data.start_at && data.end_at && data.end_at < data.start_at) {const error=document.querySelector('#booking-form-error');error.textContent='The end time must be after the start time.';error.hidden=false;return;}
      const entry = {...booking, ...data, id:booking.id || crypto.randomUUID(), source_name:sourceName, confidence:extracted && !editing ? 'review' : 'high'};
      const index = bookings.findIndex(item => item.id === entry.id);
      if (index < 0) bookings.push(entry); else bookings[index] = entry;
      save();closeDrawer();check();track(editing ? 'booking_corrected' : 'booking_saved', {booking_type:entry.kind, source:sourceName ? 'upload' : 'manual'});toast('Booking saved to your timeline.');
    });
    document.querySelector('#booking-delete')?.addEventListener('click', () => {bookings=bookings.filter(item => item.id !== booking.id);save();closeDrawer();check();track('booking_deleted',{booking_type:booking.kind});toast('Booking removed.');});
  }
  document.addEventListener('click', event => {
    const target = event.target.closest('#booking-add,#booking-add-secondary,#booking-empty-add,[data-booking-edit],[data-issue-resolve]');
    if (!target) return;
    if (target.dataset.bookingEdit) {form(bookings.find(item => item.id === target.dataset.bookingEdit));track('booking_review_opened');}
    else if (target.dataset.issueResolve) {resolved.push(`${target.dataset.issueResolve}:${target.dataset.issueMessage}`);resolvedKey && localStorage.setItem(resolvedKey,JSON.stringify(resolved));render();track('booking_issue_reviewed');}
    else {form();track('booking_add_started');}
  });
  render();
})();
