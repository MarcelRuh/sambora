(function () {
  'use strict';

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var area = document.createElement('textarea');
      area.value = text;
      area.setAttribute('readonly', '');
      area.style.position = 'fixed';
      area.style.left = '-9999px';
      document.body.appendChild(area);
      area.select();
      try {
        document.execCommand('copy');
        resolve();
      } catch (err) {
        reject(err);
      } finally {
        document.body.removeChild(area);
      }
    });
  }

  function bind() {
    document.querySelectorAll('[data-copy]').forEach(function (btn) {
      if (btn.dataset.copyBound === '1') return;
      btn.dataset.copyBound = '1';
      btn.addEventListener('click', function () {
        var value = btn.getAttribute('data-copy') || '';
        if (!value) return;
        copyText(value).then(function () {
          if (window.showToast) window.showToast('Pfad kopiert.', 'success');
        }).catch(function () {
          if (window.showToast) window.showToast('Kopieren fehlgeschlagen.', 'error');
        });
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }
})();
