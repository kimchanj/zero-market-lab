// Run against a local research server: ZML_BROWSER_URL=http://127.0.0.1:8085/asset_discovery/ node tests/browser/comparison_stability.cjs
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const path = require('node:path');
const url = process.env.ZML_BROWSER_URL || 'http://127.0.0.1:8085/asset_discovery/';
const chromePath = process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const port = Number(process.env.ZML_CDP_PORT || 9246);
const browser = spawn(chromePath, ['--headless=new', '--no-first-run', '--disable-gpu',
  `--user-data-dir=${path.resolve(__dirname, '..', '..', 'artifacts', 'chrome-stability')}`,
  `--remote-debugging-port=${port}`, '--window-size=1440,900', 'about:blank'],
  {windowsHide: true, stdio: 'ignore'});
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function main() {
  let target;
  for (let i = 0; i < 80; i++) {
    try { target = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json())
      .find(tab => tab.url === 'about:blank'); if (target) break; } catch {}
    await delay(200);
  }
  assert(target, 'Chrome DevTools target missing');
  const socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {socket.onopen = resolve; socket.onerror = reject;});
  let serial = 0;
  const pending = new Map(), errors = [], failures = [], allHttpFailures = [], unhandled = [], checkpoints = [];
  globalThis.zmlBrowserDiagnostics = {errors, failures, allHttpFailures, unhandled, checkpoints};
  socket.onmessage = event => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const {resolve, reject} = pending.get(message.id); pending.delete(message.id);
      message.error ? reject(Error(message.error.message)) : resolve(message.result);
      return;
    }
    if (message.method === 'Runtime.exceptionThrown') {
      const description = message.params.exceptionDetails.exception?.description || message.params.exceptionDetails.text;
      errors.push(description);
      if (/unhandled|in promise/i.test(description)) unhandled.push(description);
    }
    if (message.method === 'Runtime.consoleAPICalled' && message.params.type === 'error')
      errors.push(message.params.args.map(arg => arg.value || arg.description).join(' '));
    if (message.method === 'Log.entryAdded' && message.params.entry.level === 'error')
      errors.push(message.params.entry.text);
    if (message.method === 'Network.responseReceived' && message.params.response.status >= 400) {
      const record = `${message.params.response.status} ${message.params.response.url}`;
      allHttpFailures.push(record);
      if (message.params.response.url.includes('/api/')) failures.push(record);
    }
    if (message.method === 'Network.loadingFailed' && !message.params.canceled)
      failures.push(message.params.errorText);
  };
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++serial; pending.set(id, {resolve, reject}); socket.send(JSON.stringify({id, method, params}));
  });
  const evaluate = async expression => {
    const result = await send('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
    if (result.exceptionDetails) throw Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
    return result.result.value;
  };
  const js = expression => evaluate(expression);
  const ready = async () => {
    for (let i = 0; i < 100; i++) {
      const status = await js(`document.querySelector('#cmp-status')?.textContent||''`);
      if (status.includes('실제 관측')) return status;
      if (status.includes('비교 실행 실패') || status.includes('초기화 실패')) throw Error(status);
      await delay(100);
    }
    throw Error('Comparison response timeout');
  };
  const click = selector => js(`document.querySelector(${JSON.stringify(selector)}).click()`);
  const snapshot = () => js(`(()=>({status:document.querySelector('#cmp-status').textContent,
    date:document.querySelector('#cmp-date').textContent,tooltip:document.querySelector('#cmp-context-body').innerText,
    hidden:document.querySelector('#cmp-context').hidden,mode:document.querySelector('#cmp-hover-mode').textContent,
    markers:document.querySelectorAll('#cmp-quarter-markers .turning').length,
    gateTiles:document.querySelectorAll('#cmp-transit-band button').length,
    chips:[...document.querySelectorAll('#cmp-layers .comparison-chip')].map(e=>e.innerText),
    canvas:document.querySelectorAll('#cmp-chart canvas').length}))()`);
  const move = async fraction => {
    const rect = await js(`(()=>{const r=document.querySelector('#cmp-chart').getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}})()`);
    await send('Input.dispatchMouseEvent', {type:'mouseMoved', x:Math.round(rect.x+rect.w*fraction),
      y:Math.round(rect.y+rect.h*.55)});
    await delay(80);
    return snapshot();
  };
  const keyEscape = async () => {
    await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
  };
  const add = async term => {
    await click('#cmp-add');
    const found = await js(`(()=>{const input=document.querySelector('#cmp-search');input.value=${JSON.stringify(term)};
      input.dispatchEvent(new Event('input'));const button=[...document.querySelectorAll('#cmp-catalog button')]
      .find(e=>e.textContent.includes(${JSON.stringify(term)}));if(!button)return false;button.click();return true})()`);
    assert(found, `layer unavailable: ${term}`);
    await ready();
  };
  const remove = async term => {
    const found = await js(`(()=>{const chip=[...document.querySelectorAll('#cmp-layers .comparison-chip')]
      .find(e=>e.textContent.includes(${JSON.stringify(term)}));if(!chip)return false;chip.querySelector('button')?.click();return true})()`);
    assert(found, `layer not active: ${term}`);
    await ready();
  };
  const mark = async label => {await delay(120); const state=await snapshot();
    checkpoints.push({label, status:state.status, markers:state.markers, gateTiles:state.gateTiles, canvas:state.canvas});
    console.log(`checked ${label}`);
    assert(!state.status.includes('실패'), `${label}: ${state.status}`);
    assert(state.canvas>0, `${label}: chart canvas missing`);
  };
  for (const method of ['Page.enable','Runtime.enable','Log.enable','Network.enable']) await send(method);
  await send('Page.navigate',{url});
  await ready();
  let initial = await snapshot();
  for(let i=0;i<70&&initial.gateTiles===0;i++){await delay(100);initial=await snapshot();}
  assert(initial.hidden && initial.canvas > 0 && initial.gateTiles > 0,
    'Initial chart/Transit/tooltip invalid: '+JSON.stringify(initial));
  await mark('initial');
  if (process.env.ZML_SMOKE_ONLY) {console.log(JSON.stringify(globalThis.zmlBrowserDiagnostics));socket.close();return;}
  const hover = [await move(.2), await move(.5), await move(.8)];
  assert(new Set(hover.map(item=>item.date)).size === 3 && hover.every(item=>!item.hidden), 'Hover A/B/C invalid');
  for(let i=0;i<30;i++)await move(i%2?.18:.82);
  assert(!(await snapshot()).tooltip.includes('NaN'), 'Fast hover produced NaN');
  for(let i=0;i<10;i++){
    await move(.2+i*.05);await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:3,y:3});
    assert((await snapshot()).hidden,'mouseleave failed');
  }
  const a=await move(.25);
  const rect=await js(`(()=>{const r=document.querySelector('#cmp-chart').getBoundingClientRect();return{x:r.x,y:r.y,w:r.width,h:r.height}})()`);
  const point={x:Math.round(rect.x+rect.w*.25),y:Math.round(rect.y+rect.h*.55)};
  await send('Input.dispatchMouseEvent',{type:'mousePressed',...point,button:'left',clickCount:1});
  await send('Input.dispatchMouseEvent',{type:'mouseReleased',...point,button:'left',clickCount:1});
  assert((await move(.75)).date===a.date,'Date lock failed');
  await keyEscape();assert((await move(.7)).date!==a.date,'Escape unlock failed');
  await mark('hover-lock');
  for(let i=0;i<10;i++){
    await click('#cmp-add');assert(!(await js(`document.querySelector('#cmp-picker').hidden`)),'Popover did not open');
    await js(`document.body.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}))`);
    assert(await js(`document.querySelector('#cmp-picker').hidden`),'Outside click did not close picker');
  }
  for(const term of ['VIX','미국 10년물','원/달러','미 달러 광의지수']){
    for(let i=0;i<5;i++){await add(term);await move(.5);await remove(term);}
    await mark(`cycle-${term}`);
  }
  for(let i=0;i<3;i++){
    await add('S&P 500');await click('#cmp-display');
    await js(`document.querySelector('#cmp-display').value='NORMALIZE_100';document.querySelector('#cmp-display').dispatchEvent(new Event('change'))`);await ready();
    await js(`document.querySelector('#cmp-display').value='ACTUAL';document.querySelector('#cmp-display').dispatchEvent(new Event('change'))`);await ready();
    await remove('S&P 500');
  }
  await mark('asset-layer-normalize');
  for(let i=0;i<3;i++){await remove('휴먼디자인 트랜짓');assert((await snapshot()).gateTiles===0,'Transit band remained');
    await add('휴먼디자인 트랜짓');assert((await snapshot()).gateTiles>0,'Transit band missing');}
  await mark('transit-lifecycle');
  const zoomRect=await js(`(()=>{const r=document.querySelector('#cmp-chart').getBoundingClientRect();return{x:r.x,y:r.y,w:r.width,h:r.height}})()`);
  const zx=Math.round(zoomRect.x+zoomRect.w*.5),zy=Math.round(zoomRect.y+zoomRect.h*.5);
  await send('Input.dispatchMouseEvent',{type:'mouseWheel',x:zx,y:zy,deltaX:0,deltaY:-280});
  await send('Input.dispatchMouseEvent',{type:'mousePressed',x:zx,y:zy,button:'left',clickCount:1});
  await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:zx+130,y:zy,button:'left',buttons:1});
  await send('Input.dispatchMouseEvent',{type:'mouseReleased',x:zx+130,y:zy,button:'left',clickCount:1});
  await move(.4);await mark('zoom-pan');
  for(const key of ['1M','3M','6M','1Y','3Y','ALL'])for(let i=0;i<3;i++){
    await click(`[data-cmp-range="${key}"]`);await ready();
  }
  await mark('period-buttons');
  await click('[data-cmp-range="SIM"]');
  await js(`window.dispatchEvent(new CustomEvent('zml:investment-period',{detail:['2026-08-25','2026-10-08']}))`);
  for(let i=0;i<3;i++){await click('[data-cmp-range="SIM"]');await ready();}
  await mark('sim');
  for(const symbol of ['000660','035420','005930','000660','035420','005930']){
    await js(`document.querySelector('#cmp-base').value=${JSON.stringify(symbol)};document.querySelector('#cmp-base').dispatchEvent(new Event('change'))`);
    await ready();assert((await snapshot()).status.includes(symbol),'Old base response visible');
  }
  await mark('asset-switch');
  await js(`document.querySelector('#cmp-base').value='000660';document.querySelector('#cmp-base').dispatchEvent(new Event('change'))`);
  await js(`document.querySelector('#cmp-base').value='005930';document.querySelector('#cmp-base').dispatchEvent(new Event('change'))`);
  await ready();assert((await snapshot()).status.includes('005930'),'Async request race replaced latest asset');
  await mark('asset-race');
  for(const [start,end] of [['2026-01-01','2026-03-31'],['2026-05-01','2026-08-31'],['2026-07-01','2026-10-08']]){
    await js(`document.querySelector('#cmp-start').value='${start}';document.querySelector('#cmp-end').value='${end}'`);
    await click('#cmp-run');await ready();assert((await snapshot()).status.includes(start.slice(0,7)),'Range stale');
  }
  await mark('date-range');
  await send('Page.reload',{ignoreCache:true});await ready();
  assert((await snapshot()).chips.length===3,'Reload did not reset active layers');
  await mark('reload');
  await send('Emulation.setDeviceMetricsOverride',{width:600,height:900,deviceScaleFactor:1,mobile:false});
  await click('#cmp-add');
  const narrow=await js(`(()=>{const r=document.querySelector('#cmp-picker').getBoundingClientRect();return {left:r.left,right:r.right,viewport:innerWidth}})()`);
  assert(narrow.left>=0&&narrow.right<=narrow.viewport,'Popover clipped on narrow screen: '+JSON.stringify(narrow));
  await keyEscape();
  await mark('narrow');
  await send('Emulation.clearDeviceMetricsOverride');
  await add('VIX');await move(.6);
  assert(!/(?:undefined|NaN|null)/.test((await snapshot()).tooltip),'Invalid tooltip literal');
  const lastKnown=await snapshot();
  assert(/관측 20\d\d-\d\d-\d\d/.test(lastKnown.tooltip),'Last-known observation date missing');
  await mark('last-known-macro');
  await add('S&P 500');
  await js(`document.querySelector('#cmp-start').value='2026-07-01';document.querySelector('#cmp-end').value='2026-07-10'`);
  await click('#cmp-run');await ready();
  let missingDate;
  for(let x=.1;x<=.9;x+=.02){const item=await move(x);if(item.date.includes('7월 3일')){missingDate=item;break;}}
  assert(missingDate,'US holiday / Korean trading date was not reachable on chart');
  assert(missingDate.tooltip.includes('관측 없음')&&!/(?:undefined|NaN|null)/.test(missingDate.tooltip),
    'Cross-market missing observation rendered incorrectly');
  await mark('cross-market-missing-day');
  // Simulate an old open tab whose optional technical detail element predates the script.
  await js(`document.querySelector('#cmp-data-status')?.remove()`);
  await click('#cmp-run');await ready();
  await mark('optional-old-dom');
  await move(.25);assert(!(await snapshot()).hidden,'Chart stopped responding');
  const stressDurationMs = Number(process.env.ZML_STRESS_DURATION_MS || 0);
  let stressCycles = 0;
  if (stressDurationMs > 0) {
    const deadline = Date.now() + stressDurationMs;
    while (Date.now() < deadline) {
      await click('[data-cmp-range="1M"]');await ready();await move(.3);
      await click('[data-cmp-range="ALL"]');await ready();await move(.7);
      await add('미국 10년물');await move(.5);await remove('미국 10년물');
      await click('#cmp-add');await js(`document.body.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}))`);
      assert((await snapshot()).canvas>0,'Chart froze during sustained stress');
      stressCycles++;
      if (stressCycles%10===0) console.log(`stress cycles ${stressCycles}`);
    }
    await mark(`sustained-stress-${stressCycles}`);
  }
  await delay(300);
  console.log(JSON.stringify({checkpoints,initialErrors:errors.length,consoleErrors:errors,
    networkFailures:failures,unhandledPromises:unhandled,hover: hover.map(item=>item.date),narrow}));
  assert.equal(errors.length,0,'Browser console/runtime errors');
  assert.equal(failures.length,0,'Project network failures');
  assert.equal(unhandled.length,0,'Unhandled promises');
  socket.close();
}
main().catch(error=>{console.error(error);console.error(JSON.stringify(globalThis.zmlBrowserDiagnostics));process.exitCode=1;}).finally(()=>browser.kill());
