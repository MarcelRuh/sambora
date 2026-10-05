(function () {
  'use strict';

  var path = document.getElementById('path');
  if (path && path.hasAttribute('data-focus-end')) {
    path.focus();
    var len = path.value.length;
    path.setSelectionRange(len, len);
  }

  var guest = document.getElementById('guest_ok');
  var section = document.getElementById('users-section');
  var dropdown = document.getElementById('user-dropdown');
  var trigger = document.getElementById('user-dropdown-trigger');
  var panel = document.getElementById('user-dropdown-panel');
  var summary = document.getElementById('user-dropdown-summary');
  var chips = document.getElementById('user-selected-chips');
  var picker = document.getElementById('user-picker');

  function selectedUsers() {
    if (!picker) return [];
    return Array.from(picker.querySelectorAll('input[type=checkbox]:checked')).map(function (cb) {
      return cb.value;
    });
  }

  function updateUserDisplay() {
    if (!summary || !chips) return;
    var users = selectedUsers();
    if (users.length === 0) {
      summary.textContent = 'Benutzer auswählen …';
    } else if (users.length === 1) {
      summary.textContent = users[0];
    } else {
      summary.textContent = users.length + ' Benutzer ausgewählt';
    }
    chips.innerHTML = '';
    users.forEach(function (name) {
      var chip = document.createElement('span');
      chip.className = 'user-chip';
      chip.textContent = name;
      chips.appendChild(chip);
    });
  }

  function closeDropdown() {
    if (!panel || !trigger) return;
    panel.hidden = true;
    trigger.setAttribute('aria-expanded', 'false');
    dropdown && dropdown.classList.remove('is-open');
  }

  function openDropdown() {
    if (!panel || !trigger || !section || section.classList.contains('user-section-disabled')) return;
    panel.hidden = false;
    trigger.setAttribute('aria-expanded', 'true');
    dropdown && dropdown.classList.add('is-open');
  }

  function toggleDropdown() {
    if (!panel || panel.hidden) openDropdown();
    else closeDropdown();
  }

  if (trigger && panel) {
    trigger.addEventListener('click', function (e) {
      e.preventDefault();
      toggleDropdown();
    });
    document.addEventListener('click', function (e) {
      if (!dropdown || !dropdown.contains(e.target)) closeDropdown();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeDropdown();
    });
  }

  if (picker) {
    picker.addEventListener('change', updateUserDisplay);
    updateUserDisplay();
  }

  if (!guest || !section) return;

  function syncUsers() {
    var on = guest.checked;
    section.classList.toggle('user-section-disabled', on);
    if (picker) {
      picker.querySelectorAll('input[type=checkbox]').forEach(function (cb) {
        cb.disabled = on;
        if (on) cb.checked = false;
      });
    }
    if (on) closeDropdown();
    updateUserDisplay();
  }

  guest.addEventListener('change', syncUsers);
  syncUsers();
})();
