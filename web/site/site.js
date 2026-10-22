import { renderQr } from './qr.js';

const companion = new URL('./site/wallet-mockup/', document.baseURI);
const link = document.querySelector('#companion-link');
link.href = companion.href;
link.textContent = companion.host + companion.pathname.replace(/\/$/, '');
renderQr(document.querySelector('#companion-qr'), companion.href, 'Scan to use your phone as a demo wallet');

const narrowLayout = matchMedia('(max-width: 767px), (max-width: 999px) and (max-height: 500px)');
const scene = document.querySelector('.scene');
const expandButton = document.querySelector('#expand-demo');
const exitButton = document.querySelector('#demo-exit');
const demoWarning = document.querySelector('#demo-warning');
const background = document.querySelectorAll('.skip-link, .site-header, .site-intro, .demo-heading, .companion-card, #details, .site-footer');
let pageScroll = 0;

const screen = document.querySelector('#screen');
const keyboardReminder = document.querySelector('#keyboard-reminder');
let reminderTimer;

function hideKeyboardReminder() {
  clearTimeout(reminderTimer);
  keyboardReminder.hidden = true;
}
screen.addEventListener('pointerdown', event => {
  // A click that captures the keyboard is expected. Further clicks may mean the
  // user is trying to select a guest menu with the mouse.
  if (event.button !== 0 || !event.isPrimary || screen.inert || screen.dataset.ready !== 'true'
    || screen.dataset.keyboard !== 'active' || !document.hasFocus()) return;
  if (!keyboardReminder.hidden) {
    hideKeyboardReminder();
    return;
  }
  keyboardReminder.hidden = false;
  keyboardReminder.dataset.fading = 'false';
  reminderTimer = setTimeout(() => {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) hideKeyboardReminder();
    else {
      keyboardReminder.dataset.fading = 'true';
      reminderTimer = setTimeout(hideKeyboardReminder, 160);
    }
  }, 6000);
});
keyboardReminder.addEventListener('pointerdown', event => {
  // Keep keyboard capture when dismissing the notice with the mouse.
  event.preventDefault();
  event.stopPropagation();
});
keyboardReminder.addEventListener('click', event => {
  event.stopPropagation();
  hideKeyboardReminder();
});
screen.addEventListener('keydown', hideKeyboardReminder);
screen.addEventListener('blur', hideKeyboardReminder);
window.addEventListener('blur', hideKeyboardReminder);
window.addEventListener('thunderden-demo-hidden', hideKeyboardReminder);

function setExpanded(expanded, restoreFocus = true) {
  if (expanded && narrowLayout.matches) return;
  if (expanded === (document.body.dataset.demoExpanded === 'true')) return;
  if (expanded) pageScroll = window.scrollY;
  document.querySelector('#screen').blur();
  document.body.dataset.demoExpanded = String(expanded);
  expandButton.setAttribute('aria-expanded', String(expanded));
  document.querySelector('.expanded-controls').hidden = !expanded;
  document.querySelector(expanded ? '.expanded-controls' : '#device').prepend(demoWarning);
  for (const element of background) element.inert = expanded;
  if (expanded) {
    scene.setAttribute('role', 'dialog');
    scene.setAttribute('aria-modal', 'true');
    scene.setAttribute('aria-owns', 'camera-panel');
    const target = screen.dataset.ready === 'true' && !screen.inert ? screen : exitButton;
    target.focus({ preventScroll: true });
  } else {
    scene.removeAttribute('role');
    scene.removeAttribute('aria-modal');
    scene.removeAttribute('aria-owns');
    window.scrollTo({ top: pageScroll, behavior: 'instant' });
    if (restoreFocus) expandButton.focus({ preventScroll: true });
  }
}
expandButton.addEventListener('click', () => setExpanded(true));
exitButton.addEventListener('click', () => setExpanded(false));
window.addEventListener('keydown', event => {
  if (document.body.dataset.demoExpanded !== 'true') return;
  if (event.code === 'F8') {
    event.preventDefault();
    event.stopImmediatePropagation();
    setExpanded(false);
    return;
  }
  // Tab belongs to the guest while its screen has focus. F8 always provides a
  // keyboard exit; outside the screen, keep navigation within the visible UI.
  if (event.key !== 'Tab' || event.target.id === 'screen' || document.querySelector('dialog[open]')) return;
  const controls = [...scene.querySelectorAll('button, [tabindex]'), ...document.querySelectorAll('#camera-panel button')]
    .filter(element => !element.disabled && element.tabIndex >= 0 && element.getClientRects().length && !element.closest('[hidden], [inert]'));
  const first = controls[0], last = controls.at(-1);
  if ((event.shiftKey && event.target === first) || (!event.shiftKey && event.target === last)) {
    event.preventDefault();
    (event.shiftKey ? last : first).focus();
  }
}, true);

// Match the product-only CSS layout. Short laptop windows still have enough
// width for the demo; narrow or cramped phone-shaped windows do not.
async function updateLayout() {
  if (narrowLayout.matches) {
    setExpanded(false, false);
    window.dispatchEvent(new Event('thunderden-demo-hidden'));
    if (document.body.dataset.demoState !== 'running') {
      document.body.dataset.demoState = 'narrow';
      document.querySelector('#status').textContent = 'Live demo available on a computer.';
    }
    return;
  }
  // Preserve an already running guest when moving between layouts.
  if (document.body.dataset.demoState === 'running') return;
  document.body.dataset.demoState = 'running';
  await import('../app.js');
}
narrowLayout.addEventListener('change', updateLayout);
await updateLayout();
