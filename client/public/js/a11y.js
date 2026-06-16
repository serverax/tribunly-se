/* lawapp accessibility preferences  -  large text, high contrast, easy-read.
   Loaded in <head> so saved prefs apply before first paint (no flash).
   Prefs persist per-browser in localStorage; no backend, no PII. */
(function () {
  var KEY = 'lawapp_a11y';
  var root = document.documentElement;

  function load() {
    try { return JSON.parse(localStorage.getItem(KEY)) || {}; }
    catch (e) { return {}; }
  }
  function save(s) {
    try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) {}
  }

  var state = load();

  function apply() {
    root.classList.toggle('a11y-lg', !!state.lg);
    root.classList.toggle('a11y-hc', !!state.hc);
    root.classList.toggle('a11y-er', !!state.er);
  }
  apply(); // run immediately during head parse  -  before body paints

  function sync() {
    var btns = document.querySelectorAll('[data-a11y]');
    for (var i = 0; i < btns.length; i++) {
      var k = btns[i].getAttribute('data-a11y');
      btns[i].setAttribute('aria-pressed', state[k] ? 'true' : 'false');
    }
  }

  window.LAWAPP_A11Y = {
    toggle: function (k) { state[k] = !state[k]; save(state); apply(); sync(); },
    get: function () { return Object.assign({}, state); }
  };

  function wire() {
    var btns = document.querySelectorAll('[data-a11y]');
    for (var i = 0; i < btns.length; i++) {
      btns[i].addEventListener('click', function () {
        window.LAWAPP_A11Y.toggle(this.getAttribute('data-a11y'));
      });
    }
    sync();
  }

  if (document.readyState !== 'loading') wire();
  else document.addEventListener('DOMContentLoaded', wire);
})();
