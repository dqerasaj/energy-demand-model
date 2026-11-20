// Slide navigation for the decks in docs/decks/: arrow keys, Space, Home/End, T for light/dark.
(function () {
  var slides = Array.prototype.slice.call(document.querySelectorAll('.slide'));
  var i = 0;
  function show(n) {
    i = Math.max(0, Math.min(slides.length - 1, n));
    slides.forEach(function (s, k) { s.classList.toggle('active', k === i); });
    slides[i].scrollTop = 0;
    document.getElementById('count').textContent = (i + 1) + ' / ' + slides.length;
    document.getElementById('title').textContent = slides[i].getAttribute('data-title');
    document.getElementById('progress').style.width = ((i + 1) / slides.length * 100) + '%';
    if (location.hash !== '#' + (i + 1)) history.replaceState(null, '', '#' + (i + 1));
  }
  function theme() {
    var root = document.documentElement;
    var dark = root.getAttribute('data-theme') ? root.getAttribute('data-theme') === 'dark'
      : window.matchMedia('(prefers-color-scheme: dark)').matches;
    root.setAttribute('data-theme', dark ? 'light' : 'dark');
    try { localStorage.setItem('edm-theme', root.getAttribute('data-theme')); } catch (e) {}
  }
  try { var t = localStorage.getItem('edm-theme'); if (t) document.documentElement.setAttribute('data-theme', t); } catch (e) {}
  document.getElementById('prev').onclick = function () { show(i - 1); };
  document.getElementById('next').onclick = function () { show(i + 1); };
  document.getElementById('theme').onclick = theme;
  document.addEventListener('keydown', function (e) {
    if (['ArrowRight', 'PageDown', ' '].indexOf(e.key) >= 0) { e.preventDefault(); show(i + 1); }
    else if (['ArrowLeft', 'PageUp'].indexOf(e.key) >= 0) { e.preventDefault(); show(i - 1); }
    else if (e.key === 'Home') show(0);
    else if (e.key === 'End') show(slides.length - 1);
    else if (e.key === 't' || e.key === 'T') theme();
  });
  var start = parseInt(location.hash.slice(1), 10);
  show(isNaN(start) ? 0 : start - 1);
})();
