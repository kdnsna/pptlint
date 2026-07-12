/* PPTLint 站点交互：滚动渐入 + 数字滚动 + 复制提示 */
(function () {
  // 启用 JS 增强（无脚本时内容保持可见）
  document.documentElement.classList.add('js');

  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function ready(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  ready(function () {
    var revealEls = Array.prototype.slice.call(document.querySelectorAll('.reveal'));

    // 为同一容器内的兄弟节点自动生成错落延迟
    revealEls.forEach(function (el) {
      if (el.style.transitionDelay) return;
      var parent = el.parentElement;
      if (!parent) return;
      var siblings = Array.prototype.filter.call(parent.children, function (c) {
        return c.classList.contains('reveal');
      });
      if (siblings.length > 1) {
        var idx = siblings.indexOf(el);
        el.style.transitionDelay = Math.min(idx * 90, 540) + 'ms';
      }
    });

    if (reduceMotion || !('IntersectionObserver' in window)) {
      revealEls.forEach(function (el) { el.classList.add('in'); });
    } else {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('in');
            io.unobserve(entry.target);
          }
        });
      }, { threshold: 0.14, rootMargin: '0px 0px -8% 0px' });
      revealEls.forEach(function (el) { io.observe(el); });
    }

    // 数字滚动：<span data-count="100"> 或 data-count="49-100"
    function animateCount(el) {
      var raw = el.getAttribute('data-count');
      if (!raw) return;
      var parts = raw.split('-');
      var from = parts.length > 1 ? parseFloat(parts[0]) : 0;
      var to = parseFloat(parts[parts.length - 1]);
      var prefix = el.getAttribute('data-prefix') || '';
      var suffix = el.getAttribute('data-suffix') || '';
      if (reduceMotion) { el.textContent = prefix + to + suffix; return; }
      var dur = 1100, start = null;
      function step(ts) {
        if (start === null) start = ts;
        var p = Math.min((ts - start) / dur, 1);
        var eased = 1 - Math.pow(1 - p, 3);
        var val = Math.round(from + (to - from) * eased);
        el.textContent = prefix + val + suffix;
        if (p < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    }

    var counters = Array.prototype.slice.call(document.querySelectorAll('[data-count]'));
    if (counters.length) {
      if (!('IntersectionObserver' in window)) {
        counters.forEach(animateCount);
      } else {
        var cio = new IntersectionObserver(function (entries) {
          entries.forEach(function (entry) {
            if (entry.isIntersecting) { animateCount(entry.target); cio.unobserve(entry.target); }
          });
        }, { threshold: 0.5 });
        counters.forEach(function (el) { cio.observe(el); });
      }
    }
  });
})();
