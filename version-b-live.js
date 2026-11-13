/* Live Version B flows. The original design script supplies navigation and layout. */
(() => {
  const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const api = async (path, body) => {
    if (location.protocol === 'file:') throw new Error('Open this page through the app server to use live planning.');
    const response = await window.voyageFetch(`/api/v2/${path}`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'The request failed. Please try again.');
    return data;
  };
  const busy = (button, label) => {
    const original = button.innerHTML;
    button.disabled = true;
    button.textContent = label;
    return () => { button.disabled = false; button.innerHTML = original; };
  };
  const showError = (message, inDrawer = false) => {
    if (inDrawer) {
      let box = document.querySelector('#drawer-error');
      if (!box) { box = document.createElement('p'); box.id = 'drawer-error'; box.className = 'form-error'; box.setAttribute('role', 'alert'); document.querySelector('#drawer-content').append(box); }
      box.textContent = message;
    } else { const box = document.querySelector('#form-error'); box.textContent = message; box.hidden = false; }
  };
  let enrichmentPromise = Promise.resolve();
  function startEnrichment(plan) {
    enrichmentPromise = api('enrich', {plan}).then(enriched => {
      if (!trip?.plan) return;
      enriched.days.forEach((day, dayIndex) => day.activities.forEach((detail, activityIndex) => {
        const current = trip.plan.days[dayIndex]?.activities[activityIndex];
        if (current?.title !== detail.title) return;
        Object.assign(current, {
          place_name: detail.place_name,
          why_famous: detail.why_famous,
          image_url: detail.image_url,
          image_credit: detail.image_credit,
          image_page_url: detail.image_page_url
        });
      }));
      renderTrip();
      if (trip.saved) window.persistSavedTrip?.(trip);
    }).catch(() => {});
  }
  function commitPlan(plan, brief, isNew = false) {
    if (isNew) trip = {...brief, id:Date.now(), createdAt:new Date().toISOString(), reviewed:false, saved:false, shared:false};
    trip.plan = plan;
    delete trip.pdfPayment;
    if (isNew) trip.budgetScenario = null;
    trip.activities = plan.days.map(day => day.activities.map(a => ({...a})));
    selectedDay = Math.min(selectedDay, plan.days.length - 1);
    renderTrip();
    if (isNew) { trip.saved = true; window.saveVoyageTrip?.(trip).then(() => renderTrip()).catch(() => { trip.saved = false; renderTrip(); toast("Trip created, but could not be saved. Use Save trip to retry."); }); }
    else if (trip.saved) window.persistSavedTrip?.(trip);
  }
  const baseRenderTrip = renderTrip;
  renderTrip = function () {
    if (trip?.plan) {
      const originalActivities = trip.activities;
      const originalDestination = trip.destination;
      trip.destination = escapeHTML(originalDestination);
      trip.activities = originalActivities.map(day => day.map(a => ({...a, time:escapeHTML(a.time), title:escapeHTML(a.title), description:escapeHTML(a.description)})));
      try {baseRenderTrip();} finally {trip.activities = originalActivities; trip.destination = originalDestination;}
    } else baseRenderTrip();
    if (!trip?.plan) return;
    document.querySelector('#download-trip').textContent = trip.pdfPayment ? 'Download unlocked PDF' : 'Get PDF · ₹49 test';
    const day = trip.plan.days[selectedDay];
    const content = document.querySelector('#day-content');
    content.querySelector('.day-title').textContent = `Day ${selectedDay + 1}: ${day.title.replace(/^Day\s*\d+\s*[:–—-]\s*/i, '')}`;
    content.querySelector('.day-intro').textContent = day.intro;
    const weatherNote = content.querySelector('.weather-note');
    weatherNote.innerHTML = '<button type="button" id="check-weather" class="text-button">Check the next five days of weather ↗</button><span> Weather can affect outdoor plans.</span>';
    content.querySelectorAll('.activity').forEach((row, index) => {
      const activity = day.activities[index];
      if (!activity) {row.remove(); return;}
      row.querySelector('.activity-time').textContent = activity.time;
      row.querySelector('h3').textContent = activity.title;
      row.querySelector('p').textContent = activity.description + (activity.estimated_cost_inr != null ? ` · Est. ₹${activity.estimated_cost_inr.toLocaleString('en-IN')}` : '');
    });
    // The generated plan can contain more than the three prototype activity slots.
    for (let index = content.querySelectorAll('.activity').length; index < day.activities.length; index++) {
      const a = day.activities[index];
      const row = document.createElement('div'); row.className = 'activity';
      row.innerHTML = `<div class="activity-time">${escapeHTML(a.time)}</div><div><h3>${escapeHTML(a.title)}</h3><p>${escapeHTML(a.description)}</p><button data-change-activity="${index}">Change this activity</button></div>`;
      content.querySelector('.day-footer').before(row);
    }
    content.querySelectorAll('.activity').forEach((row, index) => {
      const activity = day.activities[index];
      if (!activity) return;
      const detail = row.children[1];
      const logistics = [activity.duration ? `Allow ${activity.duration}` : '', activity.getting_there, activity.practical_tip].filter(Boolean);
      if (logistics.length) {
        const list = document.createElement('ul');
        list.className = 'activity-logistics';
        logistics.forEach(item => {const li=document.createElement('li');li.textContent=item;list.append(li)});
        detail.querySelector('p').after(list);
      }
      if (activity.image_url?.startsWith('https://upload.wikimedia.org/') || activity.image_url?.startsWith('https://thumb.wikimedia.org/')) {
        const figure = document.createElement('figure');
        figure.className = 'place-photo';
        const photo = document.createElement('img');
        photo.src = activity.image_url;
        photo.alt = activity.place_name ? `Photo of ${activity.place_name}` : activity.title;
        photo.loading = 'lazy';
        const caption = document.createElement('figcaption');
        const source = document.createElement('a');
        source.href = activity.image_page_url;
        source.target = '_blank';
        source.rel = 'noopener noreferrer';
        source.textContent = `Photo: ${activity.image_credit} · Wikimedia Commons`;
        caption.append(source);
        figure.append(photo, caption);
        detail.querySelector('p').after(figure);
      }
      if (activity.why_famous) {
        const fact = document.createElement('p');
        fact.className = 'place-fact';
        const label = document.createElement('strong');
        label.textContent = 'Why it matters: ';
        fact.append(label, document.createTextNode(activity.why_famous));
        detail.querySelector('p').after(fact);
      }
    });
    document.querySelector('#summary-budget').textContent = `From ₹${trip.plan.estimated_total_inr.toLocaleString('en-IN')}`;
    document.querySelector('#saved-scenario-summary')?.remove();
    if (trip.budgetScenario) {
      const delta = Object.values(trip.budgetScenario).reduce((sum, value) => sum + (Number(value) || 0), 0);
      const summary = document.createElement('p'); summary.id = 'saved-scenario-summary'; summary.className = 'estimate-basis';
      summary.textContent = `Your budget scenario: ${rupees(Math.max(0, trip.plan.estimated_total_inr + delta))}. This is your adjustment to the trip estimate.`;
      document.querySelector('#summary-budget').closest('.summary-row').after(summary);
    }
    document.querySelector('#estimate-basis')?.remove();
    if (trip.plan.estimate_basis) {
      const basis = document.createElement('p');
      basis.id = 'estimate-basis';
      basis.className = 'estimate-basis';
      basis.textContent = trip.plan.estimate_basis;
      document.querySelector('#summary-budget').closest('.summary-row').after(basis);
    }
    document.querySelector('#research-summary')?.remove();
    if (trip.plan.hotels?.length || trip.plan.restaurants?.length) {
      const panel = document.createElement('div');
      panel.id = 'research-summary';
      panel.className = 'research-summary';
      const heading = document.createElement('h3');
      heading.textContent = 'Places to stay & eat';
      panel.append(heading);
      const addOption = (label, name, note, url) => {
        const section = document.createElement('div');
        section.className = 'research-option';
        const title = document.createElement('strong');
        title.textContent = `${label}: ${name}`;
        const info = document.createElement('p');
        info.textContent = note;
        section.append(title, info);
        if (url?.startsWith('https://')) {
          const link = document.createElement('a');
          link.href = url;
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          link.textContent = 'View source ↗';
          link.addEventListener('click', () => track('travel_source_opened', {source_type:label === 'Stay' ? 'hotel' : 'restaurant'}));
          section.append(link);
        }
        panel.append(section);
      };
      trip.plan.hotels?.forEach(h => addOption('Stay', h.name,
        `${h.area ? h.area + ' · ' : ''}${h.why_stay}${h.nightly_price_inr ? ' · Listed from ₹' + h.nightly_price_inr.toLocaleString('en-IN') + '/night (checked ' + h.price_checked_on + '; confirm for your dates)' : ' · Check rate for your dates'}`,
        h.price_source_url || h.source_url));
      trip.plan.restaurants?.forEach(r => addOption('Eat', r.name,
        `${r.area ? r.area + ' · ' : ''}${r.what_to_try}`, r.source_url));
      document.querySelector('.trip-sidebar .summary-content').append(panel);
    }
    if (trip.plan.practical_notes.length) {
      const notes = document.createElement('div'); notes.className = 'practical-notes';
      notes.innerHTML = '<h3>Before you go</h3><ul>' + trip.plan.practical_notes.map(n => `<li>${escapeHTML(n)}</li>`).join('') + '</ul>';
      content.querySelector('.day-footer').before(notes);
    }
  };
  async function generate(button) {
    const brief = tripData();
    const restore = busy(button, 'Researching places and building days…');
    document.querySelector('#trip-form').setAttribute('aria-busy', 'true');
    try {
      const plan = await api('plan', {brief});
      selectedDay = 0;
      commitPlan(plan, brief, true);
      navigate('trip');
      startEnrichment(plan);
      track('plan_generated', {source:'guided_setup', duration_days:brief.days, budget_tier:brief.budget<20000?'low':brief.budget<50000?'mid':'high'});
      toast('Your itinerary is ready. Review and refine it below.');
    } catch(error) {showError(error.message); track('plan_failed',{source:'guided_setup',reason:'v2_request'});}
    finally {restore(); document.querySelector('#trip-form').removeAttribute('aria-busy');}
  }
  async function propose(action, dayIndex = null, activityIndex = null, instruction = '') {
    if (!trip?.plan) {toast('Create an itinerary first.'); return;}
    const labels = {alternate:'Alternative itinerary',day:'Change this day',activity:'Change this activity',cost:'Lower-cost trip',weather:'Indoor alternatives'};
    drawer(labels[action], '<p>We’re preparing a suggested change. Your current trip stays as it is until you accept it.</p><p id="drawer-loading" role="status">Working on your alternative…</p>');
    try {
      const result = await api('edit', {brief:tripDataFromSaved(), plan:trip.plan, action, day_index:dayIndex, activity_index:activityIndex, instruction});
      const proposed = result;
      const targetDay = dayIndex == null ? 0 : dayIndex;
      const changedActivity = action === 'activity' ? proposed.days[targetDay].activities[activityIndex] : null;
      const summary = changedActivity ? `${changedActivity.title}. ${changedActivity.description}` : action === 'day' || action === 'weather' ? `${proposed.days[targetDay].title}: ${proposed.days[targetDay].activities.map(a=>a.title).join(', ')}` : proposed.overview;
      const change = action === 'cost' ? `<p>Estimated total: ₹${trip.plan.estimated_total_inr.toLocaleString('en-IN')} → ₹${proposed.estimated_total_inr.toLocaleString('en-IN')}</p>` : '';
      document.querySelector('#drawer-content').innerHTML = `<h2 id="drawer-title">${escapeHTML(labels[action])}</h2><p>${escapeHTML(summary)}</p>${change}<p>Review the revised itinerary after applying. Estimates should be checked before booking.</p><button class="button button-dark" id="accept-proposal">Use this version</button><button class="button button-quiet" id="reject-proposal">Keep my trip</button>`;
      document.querySelector('#accept-proposal').onclick = () => {commitPlan(proposed, null); startEnrichment(proposed); closeDrawer(); toast('Your itinerary has been updated.'); track('plan_refined',{action,day_number:dayIndex == null ? undefined : dayIndex+1});};
      document.querySelector('#reject-proposal').onclick = closeDrawer;
      track('plan_refinement_proposed',{action});
    } catch(error) {document.querySelector('#drawer-content').innerHTML = `<h2 id="drawer-title">Couldn't create a change</h2><p role="alert">${escapeHTML(error.message)}</p><button class="button button-quiet" id="dismiss-proposal">Keep my trip</button>`;document.querySelector('#dismiss-proposal').onclick=closeDrawer;}
  }
  const rupees = amount => `₹${Math.round(amount).toLocaleString('en-IN')}`;
  function comparisonCard(plan, label) {
    return `<article class="compare-card"><p class="small-label">${label}</p><h3>${rupees(plan.estimated_total_inr)} estimated</h3><p>${escapeHTML(plan.overview)}</p><ol>${plan.days.map((day, index) => `<li><strong>Day ${index + 1}: ${escapeHTML(day.title)}</strong><span>${escapeHTML(day.activities.map(activity => activity.title).join(' · '))}</span></li>`).join('')}</ol></article>`;
  }
  async function compareTrips() {
    if (!trip?.plan) return;
    track('trip_comparison_started');
    drawer('Compare two journeys', '<p id="compare-status" role="status">Creating a second route from your trip preferences…</p>');
    const original = trip.plan;
    try {
      const alternative = await api('edit', {brief:tripDataFromSaved(), plan:original, action:'alternate', instruction:'Create a meaningfully different route with different activities and day themes while keeping the same destination, duration and budget.'});
      const changed = alternative.days.some((day, index) => day.activities.some((activity, activityIndex) => activity.title !== original.days[index]?.activities[activityIndex]?.title));
      if (!changed) throw new Error('The alternative is too similar to compare. Please try again.');
      document.querySelector('#drawer-content').innerHTML = `<h2 id="drawer-title">Compare two journeys</h2><p>Both totals are estimates. Compare each day before choosing.</p><div class="compare-grid">${comparisonCard(original, 'Your current plan')}${comparisonCard(alternative, 'New alternative')}</div><div class="compare-actions"><button class="button button-dark" id="choose-alternative">Use alternative</button><button class="button button-quiet" id="keep-original">Keep current plan</button></div>`;
      document.querySelector('#choose-alternative').onclick = () => {commitPlan(alternative, null); startEnrichment(alternative); closeDrawer(); track('trip_comparison_choice', {choice:'alternative', estimated_delta_inr:alternative.estimated_total_inr-original.estimated_total_inr}); toast('Alternative itinerary selected.');};
      document.querySelector('#keep-original').onclick = () => {closeDrawer(); track('trip_comparison_choice', {choice:'current', estimated_delta_inr:alternative.estimated_total_inr-original.estimated_total_inr});};
      track('trip_comparison_viewed', {estimated_delta_inr:alternative.estimated_total_inr-original.estimated_total_inr});
    } catch (error) {showError(error.message, true); document.querySelector('#compare-status')?.remove(); track('trip_comparison_failed');}
  }
  function budgetScenario() {
    if (!trip?.plan) return;
    const total = trip.plan.estimated_total_inr;
    const knownActivities = trip.plan.days.flatMap(day => day.activities).reduce((sum, activity) => sum + (Number(activity.estimated_cost_inr) || 0), 0);
    const hotel = trip.plan.hotels?.find(option => Number(option.nightly_price_inr) > 0);
    const nights = Math.max(1, trip.days - 1);
    const hotelCost = hotel ? hotel.nightly_price_inr * nights : null;
    const base = trip.budgetScenario || {stay:0, meals:0, activities:0, localTravel:0};
    const categories = [['stay','Stay'],['meals','Meals'],['activities','Activities'],['localTravel','Local travel']];
    drawer('Shape your budget', `<p>Explore how spending choices could affect your trip. The starting total is Voyage’s estimate, not a live quote.</p><div class="budget-total"><span>Original estimate</span><strong>${rupees(total)}</strong></div>${hotelCost ? `<p class="fine-print">Research reference: ${escapeHTML(hotel.name)} listed from ${rupees(hotel.nightly_price_inr)}/night when checked. Confirm availability for your dates.</p>` : ''}${knownActivities ? `<p class="fine-print">Named activities with cost estimates total ${rupees(knownActivities)}. Other costs are included in the overall trip estimate.</p>` : ''}<p class="fine-print">Adjustments below are your own scenario amounts, added to or subtracted from the overall estimate. They do not change bookings or the itinerary.</p><div class="scenario-inputs">${categories.map(([key,label]) => `<label class="drawer-field">${label} change (₹)<input type="number" id="scenario-${key}" step="500" value="${Number(base[key]) || 0}" aria-label="${label} change in rupees"></label>`).join('')}</div><div class="budget-total budget-result"><span>Scenario total</span><strong id="scenario-total">${rupees(total)}</strong></div><p id="scenario-difference" role="status"></p><button class="button button-dark" id="save-scenario">Save this scenario</button>`);
    const update = () => {
      const values = Object.fromEntries(categories.map(([key]) => [key, Number(document.querySelector(`#scenario-${key}`).value) || 0]));
      const delta = Object.values(values).reduce((sum, value) => sum + value, 0);
      const scenarioTotal = Math.max(0, total + delta);
      document.querySelector('#scenario-total').textContent = rupees(scenarioTotal);
      document.querySelector('#scenario-difference').textContent = delta < 0 ? `${rupees(-delta)} below the original estimate` : delta > 0 ? `${rupees(delta)} above the original estimate` : 'Matches the original estimate';
      return {values, delta, scenarioTotal};
    };
    document.querySelectorAll('.scenario-inputs input').forEach(input => input.addEventListener('input', update));
    update();
    document.querySelector('#save-scenario').onclick = () => {
      const {values, delta, scenarioTotal} = update();
      trip.budgetScenario = values;
      if (trip.saved) window.persistSavedTrip?.(trip);
      closeDrawer(); toast(`Scenario saved: ${rupees(scenarioTotal)} estimated.`);
      track('budget_scenario_saved', {delta_inr:delta, scenario_total_inr:scenarioTotal, within_target:scenarioTotal <= trip.budget});
    };
    track('budget_scenario_opened', {estimated_total_inr:total});
  }
  function tripDataFromSaved() {return {destination:trip.destination,date:trip.date||'',days:trip.days,origin:trip.origin||'',interests:trip.interests||[],pace:trip.pace||'Balanced',budget:trip.budget,travelers:trip.travelers,notes:trip.notes||''};}
  function ask() {
    if (!trip?.plan) {toast('Create an itinerary first.');return;}
    drawer('Ask about your trip','<p>Ask a practical question about your itinerary.</p><label class="drawer-field">Your question<input id="assistant-question" maxlength="500" placeholder="Could we make day 2 less busy?"></label><button class="button button-dark" id="assistant-send">Ask Voyage</button><div id="assistant-answer" aria-live="polite"></div>');
    document.querySelector('#assistant-send').onclick = async () => {
      const question = document.querySelector('#assistant-question').value.trim();
      if (question.length < 3) {showError('Enter a question of at least three characters.',true);return;}
      const button = document.querySelector('#assistant-send'), restore=busy(button,'Finding an answer…');
      try {const result=await api('ask',{brief:tripDataFromSaved(),plan:trip.plan,question});document.querySelector('#assistant-answer').textContent=result.answer;track('trip_assistant_asked');}
      catch(error){showError(error.message,true)}finally{restore()}
    };
  }
  async function showForecast() {
    drawer('Weather outlook', '<p id="weather-result" role="status">Checking the next five days…</p>');
    try {
      const response = await window.voyageFetch(`/api/v2/weather?city=${encodeURIComponent(trip.destination)}`);
      const data = await response.json(); if(!response.ok) throw new Error(data.detail||'Weather is unavailable.');
      if (!data.available) throw new Error(data.reason);
      const entries = [...new Map(data.forecast.map(x=>[x.date.slice(0,10),x])).values()].slice(0,5);
      document.querySelector('#weather-result').outerHTML = '<p>Forecast for the next five days, not necessarily your travel dates.</p><ul class="forecast-list">'+entries.map(x=>`<li><strong>${escapeHTML(x.date.slice(0,16))}</strong> ${escapeHTML(x.temperature_c)}°C, ${escapeHTML(x.description)}</li>`).join('')+'</ul><button class="button button-dark" id="weather-alternative">Suggest indoor options for this day</button>';
      document.querySelector('#weather-alternative').onclick=()=>propose('weather',selectedDay,null,'Suggest indoor options if rain or poor weather affects outdoor activities.');
      track('weather_checked');
    } catch(error){showError(error.message,true)}
  }
  function nearby() {
    const destination=destinations.find(d=>d.name.toLowerCase()===trip.destination.toLowerCase());
    if (!destination) {drawer('Places nearby','<p>Nearby suggestions are available for the featured destinations. Ask the assistant for this location.</p>');return;}
    drawer('Places nearby',`<p>Places to research near ${escapeHTML(destination.name)}:</p><p>${escapeHTML(destination.nearby)}</p><p class="fine-print">Check travel time and opening details before adding a stop.</p><button class="button button-dark" id="ask-nearby">Ask about adding one</button>`);
    document.querySelector('#ask-nearby').onclick=ask;
    track('nearby_attractions_viewed',{destination:destination.name.toLowerCase()});
  }
  let checkoutLoader;
  function loadCheckout() {
    if (window.Razorpay) return Promise.resolve();
    if (!checkoutLoader) checkoutLoader = new Promise((resolve,reject) => {
      const script=document.createElement('script');
      script.src='https://checkout.razorpay.com/v1/checkout.js';
      script.onload=resolve;
      script.onerror=()=>{checkoutLoader=null;reject(new Error('Payment checkout could not load. Check your connection and try again.'))};
      document.head.append(script);
    });
    return checkoutLoader;
  }
  async function deliverPdf(payment) {
    await enrichmentPromise;
    const response=await window.voyageFetch('/api/v2/pdf',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({destination:trip.destination,plan:trip.plan,...payment})
    });
    if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(data.detail||'Could not prepare your PDF. Try again.');}
    const url=URL.createObjectURL(await response.blob());
    const link=document.createElement('a');
    link.href=url;link.download=`Voyage-${trip.destination.replace(/[^a-z0-9]/gi,'-')}.pdf`;
    document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
    track('plan_downloaded',{format:'pdf',payment_mode:'razorpay_test'});
    toast('Your PDF is downloading.');
  }
  async function download(button) {
    if (!trip?.plan) {toast('Create an itinerary first.');return;}
    if(trip.pdfPayment){
      const restore=busy(button,'Preparing PDF…');
      try{await deliverPdf(trip.pdfPayment);return;}
      catch(error){if(!/unlock|verification/i.test(error.message)){toast(error.message);return;}delete trip.pdfPayment;renderTrip();if(trip.saved)window.persistSavedTrip?.(trip);}
      finally{restore()}
    }
    drawer('Get your itinerary PDF',`<div class="pdf-checkout"><p>Your complete ${escapeHTML(trip.destination)} itinerary, ready to keep offline.</p><div class="pdf-checkout-price"><span>PDF download</span><strong>₹49</strong></div><p class="pdf-test-note">Razorpay test checkout · No real money will be charged.</p><button class="button button-dark" id="pay-for-pdf" type="button">Continue to test payment</button><p class="fine-print">Your plan stays available in My trips. A successful test payment unlocks this PDF for the current plan.</p></div>`);
    track('pdf_checkout_viewed',{price_inr:49,payment_mode:'razorpay_test'});
    document.querySelector('#pay-for-pdf').onclick=async()=>{
      const payButton=document.querySelector('#pay-for-pdf');
      const restore=busy(payButton,'Opening checkout…');
      try{
        await enrichmentPromise;
        const order=await api('pdf/order',{destination:trip.destination,plan:trip.plan});
        await loadCheckout();
        track('pdf_payment_started',{price_inr:49,payment_mode:'razorpay_test'});
        let paymentCompleted=false;
        const checkout=new window.Razorpay({
          key:order.key_id,amount:order.amount,currency:order.currency,order_id:order.order_id,
          name:'VOYAGE',description:'Itinerary PDF · test payment',
          theme:{color:'#193c49'},
          handler:async response=>{
            paymentCompleted=true;
            payButton.textContent='Verifying payment…';payButton.disabled=true;
            try{
              const payment={razorpay_order_id:response.razorpay_order_id,
                razorpay_payment_id:response.razorpay_payment_id,
                razorpay_signature:response.razorpay_signature};
              trip.pdfPayment=payment;
              if(trip.saved) window.persistSavedTrip?.(trip);
              await deliverPdf(payment);
              renderTrip();
              track('pdf_payment_verified',{price_inr:49,payment_mode:'razorpay_test'});
              closeDrawer();
            }catch(error){
              showError(`${error.message} Your test payment is saved; retry the PDF without paying again.`,true);
              payButton.disabled=false;payButton.textContent='Retry PDF download';
              payButton.onclick=async()=>{const reset=busy(payButton,'Preparing PDF…');try{await deliverPdf(trip.pdfPayment);closeDrawer()}catch(retryError){showError(retryError.message,true)}finally{reset()}};
            }
          },
          modal:{ondismiss:()=>{if(!paymentCompleted)track('pdf_checkout_cancelled');restore()}},
        });
        checkout.on('payment.failed',()=>{showError('Test payment failed. Please retry checkout.',true);restore();track('pdf_payment_failed')});
        checkout.open();
      }catch(error){showError(error.message,true);restore()}
    };
  }
  async function share() {
    if(!trip?.plan){toast('Create an itinerary first.');return;}
    const text=`My ${trip.days}-day ${trip.destination} itinerary with Voyage\n\n${trip.plan.overview}\n\n`+trip.plan.days.map((d,i)=>`Day ${i+1}: ${d.title}\n${d.activities.map(a=>'- '+a.title).join('\n')}`).join('\n\n');
    try {if(navigator.share) await navigator.share({title:`${trip.destination} itinerary`,text});else {await navigator.clipboard.writeText(text);toast('Itinerary copied for sharing.')}trip.shared=true;renderTrip();track('plan_shared',{method:navigator.share?'native':'copy'});}catch(error){if(error.name!=='AbortError')toast('Could not share this trip. Try again.')}
  }
  document.addEventListener('click', async event => {
    const target=event.target.closest('button');if(!target)return;
    const id=target.id;
    if (id==='step-next' && step===3) {event.preventDefault();event.stopImmediatePropagation();await generate(target);return;}
    const activity=target.closest('[data-change-activity]');
    if(activity){event.preventDefault();event.stopImmediatePropagation();propose('activity',selectedDay,Number(activity.dataset.changeActivity));return;}
    const actions={
      'change-day':()=>propose('day',selectedDay),
      'alternate-trip':compareTrips,
      'optimize-budget':()=>propose('cost'),
      'budget-scenario':budgetScenario,
      'ask-assistant':ask,
      'nearby-attractions':nearby,
      'check-weather':showForecast,
      'download-trip':()=>download(target),
      'share-trip':share,
      'recommend-open':recommend,
      'planner-match':recommend,
    };
    if(actions[id]){event.preventDefault();event.stopImmediatePropagation();actions[id]();}
  },true);
  function recommend() {
    drawer('Find your kind of place','<p>Tell us what you want most, and we’ll suggest one of our featured destinations.</p><label class="drawer-field">Your interest<select id="match-interest"><option value="nature">Nature and slow days</option><option value="culture">History and culture</option><option value="adventure">Adventure</option></select></label><label class="drawer-field">Total budget (₹)<input id="match-budget" type="number" min="1000" value="25000"></label><label class="drawer-field">Trip length<select id="match-days"><option value="3">3 days</option><option value="4" selected>4 days</option><option value="5">5 days</option><option value="6">6 days</option></select></label><button class="button button-dark" id="find-live-match">Find my match</button>');
    document.querySelector('#find-live-match').onclick=async()=>{const button=document.querySelector('#find-live-match'),restore=busy(button,'Finding your match…');try{const result=await api('recommend',{interest:document.querySelector('#match-interest').value,budget:Number(document.querySelector('#match-budget').value),days:Number(document.querySelector('#match-days').value)});document.querySelector('#drawer-content').innerHTML=`<h2 id="drawer-title">${escapeHTML(result.destination)} feels right.</h2><p>${escapeHTML(result.reason)}</p><button class="button button-dark" id="view-match">Explore ${escapeHTML(result.destination)}</button>`;document.querySelector('#view-match').onclick=()=>{closeDrawer();openDestination(result.destination)};track('destination_recommended',{destination:result.destination.toLowerCase()});}catch(error){showError(error.message,true)}finally{if(button.isConnected)restore()}};
  }
  // Forecast is time-limited to the next five days.
  document.querySelector('.hero-image').style.backgroundImage="url('assets/destinations/hampi.jpg')";
})();
