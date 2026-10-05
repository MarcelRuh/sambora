(function () {
  'use strict';

  var modalEl = null;
  var modalTitle = null;
  var modalBody = null;
  var modalOk = null;
  var modalCancel = null;
  var modalResolve = null;
  var lastFocus = null;

  function focusableInModal() {
    return Array.prototype.filter.call(
      modalEl.querySelectorAll('button, [href], input, select, textarea'),
      function (el) {
        return !el.disabled && !el.hidden;
      }
    );
  }

  function onModalKeydown(e) {
    if (!modalEl || modalEl.hidden) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      closeModal(false);
      return;
    }
    if (e.key !== 'Tab') return;
    var nodes = focusableInModal();
    if (!nodes.length) {
      e.preventDefault();
      return;
    }
    var first = nodes[0];
    var last = nodes[nodes.length - 1];
    var active = document.activeElement;
    if (e.shiftKey && (active === first || !modalEl.contains(active))) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && (active === last || !modalEl.contains(active))) {
      e.preventDefault();
      first.focus();
    }
  }

  function initModal() {
    modalEl = document.getElementById('ui-modal');
    if (!modalEl) return;
    modalTitle = document.getElementById('ui-modal-title');
    modalBody = document.getElementById('ui-modal-body');
    modalOk = document.getElementById('ui-modal-ok');
    modalCancel = document.getElementById('ui-modal-cancel');

    modalCancel.addEventListener('click', function () {
      closeModal(false);
    });
    modalOk.addEventListener('click', function () {
      closeModal(true);
    });
    modalEl.querySelector('.ui-modal-backdrop').addEventListener('click', function () {
      closeModal(false);
    });
    document.addEventListener('keydown', onModalKeydown);
  }

  function openModal(message, options) {
    options = options || {};
    if (!modalEl) return Promise.resolve(false);

    modalTitle.textContent = options.title || 'Bestätigen';
    modalBody.textContent = message;
    modalOk.textContent = options.okLabel || 'OK';
    modalCancel.textContent = options.cancelLabel || 'Abbrechen';
    modalOk.className = 'btn ' + (options.danger ? 'btn-danger' : 'btn-primary');

    lastFocus = document.activeElement;
    modalEl.hidden = false;
    modalEl.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
    modalOk.focus();

    return new Promise(function (resolve) {
      modalResolve = resolve;
    });
  }

  function openPrompt(options) {
    options = options || {};
    if (!modalEl) return Promise.resolve(null);

    modalTitle.textContent = options.title || 'Eingabe';
    modalBody.innerHTML = '';
    var label = document.createElement('label');
    label.className = 'form-group';
    label.textContent = options.label || '';
    var input = document.createElement('input');
    input.type = options.inputType === 'password' ? 'password' : 'text';
    input.className = 'ui-prompt-input';
    input.value = options.defaultValue || '';
    input.autocomplete = options.inputType === 'password' ? 'current-password' : 'off';
    label.appendChild(input);
    modalBody.appendChild(label);

    modalOk.textContent = options.okLabel || 'OK';
    modalCancel.textContent = options.cancelLabel || 'Abbrechen';
    modalOk.className = 'btn btn-primary';

    lastFocus = document.activeElement;
    modalEl.hidden = false;
    modalEl.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');

    return new Promise(function (resolve) {
      modalResolve = function (ok) {
        resolve(ok ? input.value.trim() : null);
      };
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          closeModal(true);
        }
      });
      setTimeout(function () { input.focus(); }, 0);
    });
  }

  function closeModal(result) {
    if (!modalEl || modalEl.hidden) return;
    modalEl.hidden = true;
    modalEl.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('modal-open');
    var restore = lastFocus;
    lastFocus = null;
    var resolve = modalResolve;
    modalResolve = null;
    if (resolve) resolve(!!result);
    if (modalEl.hidden && restore && typeof restore.focus === 'function') {
      restore.focus();
    }
  }

  function finishConfirmedSubmit(form) {
    form.dataset.confirmed = '1';
    if (typeof form.requestSubmit === 'function') {
      form.requestSubmit();
    } else {
      form.submit();
    }
  }

  function bindConfirmForms() {
    document.querySelectorAll('form[data-confirm]').forEach(function (form) {
      form.addEventListener('submit', function (e) {
        if (form.dataset.confirmed === '1') {
          delete form.dataset.confirmed;
          return;
        }
        e.preventDefault();
        e.stopImmediatePropagation();
        var message = form.getAttribute('data-confirm') || 'Fortfahren?';
        var files = form.querySelector('input[name="delete_files"]');
        if (files && files.checked) {
          var path = form.getAttribute('data-delete-path') || '';
          message += ' Der Ordner' + (path ? ' ' + path : '') +
            ' und alle Dateien werden dauerhaft gelöscht. Das kann nicht rückgängig gemacht werden.';
        }
        var title = form.getAttribute('data-confirm-title') || 'Bestätigen';
        var danger = form.hasAttribute('data-confirm-danger');
        openModal(message, { title: title, danger: danger }).then(function (ok) {
          if (!ok) return;
          if (form.hasAttribute('data-reauth')) {
            var api = window.Sambora || window.SambaUI;
            if (!api || !api.promptPassword) return;
            api.promptPassword({
              title: form.getAttribute('data-reauth-title') || 'Passwort bestätigen',
              okLabel: 'Bestätigen',
            }).then(function (password) {
              if (!password) return;
              var input = form.querySelector('input[name="confirm_password"]');
              if (!input) {
                input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'confirm_password';
                form.appendChild(input);
              }
              input.value = password;
              form.dataset.reauthDone = '1';
              finishConfirmedSubmit(form);
            });
            return;
          }
          finishConfirmedSubmit(form);
        });
      });
    });
  }

  function bindToastDismiss() {
    document.querySelectorAll('[data-toast]').forEach(function (toast) {
      var closeBtn = toast.querySelector('.toast-close');
      if (closeBtn) {
        closeBtn.addEventListener('click', function () {
          toast.classList.add('toast-hide');
          setTimeout(function () {
            toast.remove();
          }, 220);
        });
      }
      setTimeout(function () {
        if (!toast.isConnected) return;
        toast.classList.add('toast-hide');
        setTimeout(function () {
          if (toast.isConnected) toast.remove();
        }, 220);
      }, 8000);
    });
  }

  function bindSidebar() {
    var toggle = document.getElementById('sidebar-toggle');
    var backdrop = document.getElementById('sidebar-backdrop');
    if (!toggle) return;

    function setOpen(open) {
      document.body.classList.toggle('sidebar-open', open);
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (backdrop) backdrop.hidden = !open;
    }

    toggle.addEventListener('click', function () {
      setOpen(!document.body.classList.contains('sidebar-open'));
    });
    if (backdrop) {
      backdrop.addEventListener('click', function () { setOpen(false); });
    }
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') setOpen(false);
    });
    document.querySelectorAll('.sidebar-nav a').forEach(function (link) {
      link.addEventListener('click', function () { setOpen(false); });
    });
  }

  function bindFormLoading() {
    document.querySelectorAll('form[data-loading]').forEach(function (form) {
      form.addEventListener('submit', function (e) {
        if (e.defaultPrevented) return;
        var btn = form.querySelector('button[type="submit"]');
        if (!btn || btn.disabled) return;
        btn.disabled = true;
        btn.dataset.originalText = btn.textContent;
        btn.textContent = 'Wird ausgeführt …';
        btn.classList.add('is-loading');
      });
    });
  }

  function formatSize(bytes) {
    if (!bytes) return '0 B';
    var units = ['B', 'KB', 'MB', 'GB', 'TB'];
    var i = 0;
    var size = bytes;
    while (size >= 1024 && i < units.length - 1) {
      size /= 1024;
      i += 1;
    }
    return (i === 0 ? size : size.toFixed(size >= 10 ? 0 : 1)) + ' ' + units[i];
  }

  function showToast(message, type) {
    var stack = document.querySelector('.toast-stack');
    if (!stack) {
      stack = document.createElement('div');
      stack.className = 'toast-stack';
      stack.setAttribute('role', 'status');
      var main = document.querySelector('.container');
      if (main) main.insertBefore(stack, main.firstChild);
    }
    var toast = document.createElement('div');
    toast.className = 'toast ' + (type || 'success');
    toast.setAttribute('data-toast', '');
    toast.innerHTML =
      '<span class="toast-icon" aria-hidden="true">' + (type === 'error' ? '!' : '✓') + '</span>' +
      '<span class="toast-message"></span>' +
      '<button type="button" class="toast-close" aria-label="Schließen">×</button>';
    toast.querySelector('.toast-message').textContent = message;
    stack.appendChild(toast);
    var closeBtn = toast.querySelector('.toast-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', function () {
        toast.remove();
      });
    }
    setTimeout(function () {
      if (toast.isConnected) toast.remove();
    }, 8000);
  }

  function bindReauthForms() {
    document.querySelectorAll('form[data-reauth]').forEach(function (form) {
      form.addEventListener('submit', function (e) {
        if (form.dataset.reauthDone === '1') {
          delete form.dataset.reauthDone;
          return;
        }
        e.preventDefault();
        var api = window.Sambora || window.SambaUI;
        if (!api || !api.promptPassword) {
          return;
        }
        api.promptPassword({
          title: form.getAttribute('data-reauth-title') || 'Passwort bestätigen',
          okLabel: 'Bestätigen',
        }).then(function (password) {
          if (!password) return;
          var input = form.querySelector('input[name="confirm_password"]');
          if (!input) {
            input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'confirm_password';
            form.appendChild(input);
          }
          input.value = password;
          form.dataset.reauthDone = '1';
          if (typeof form.requestSubmit === 'function') {
            form.requestSubmit();
          } else {
            form.submit();
          }
        });
      });
    });
  }

  window.Sambora = {
    confirm: openModal,
    prompt: openPrompt,
    promptPassword: function (options) {
      options = options || {};
      options.inputType = 'password';
      options.label = options.label || 'Admin-Passwort';
      options.title = options.title || 'Passwort bestätigen';
      return openPrompt(options);
    },
    toast: showToast,
    formatSize: formatSize,
    csrfToken: function () {
      var meta = document.querySelector('meta[name="csrf-token"]');
      return meta ? meta.getAttribute('content') : '';
    },
  };
  window.SambaUI = window.Sambora;

  window.showToast = showToast;

  function bindMeters() {
    document.querySelectorAll('[data-meter]').forEach(function (el) {
      var value = Number(el.getAttribute('data-meter'));
      if (!isFinite(value)) return;
      el.style.width = Math.max(0, Math.min(100, value)) + '%';
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    initModal();
    bindMeters();
    document.querySelectorAll('.nav-item.active').forEach(function (el) {
      el.setAttribute('aria-current', 'page');
    });
    bindConfirmForms();
    bindReauthForms();
    bindToastDismiss();
    bindFormLoading();
    bindSidebar();
  });
})();
