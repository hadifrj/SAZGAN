/**
 * Sazgan advanced searchable select
 * - searchable dropdown with larger panel
 * - search filter + keyboard nav (↑↓ Enter Esc)
 * - clear button
 * - فقط روی selectهای customer / ss-enable فعال است
 */
(function () {
  function enhanceSelect(sel) {
    if (!sel || sel.dataset.ssReady === "1") return;
    if (sel.multiple) return;
    if (sel.size && parseInt(sel.size, 10) > 1) return;
    if (sel.closest(".ss-wrap")) return;
    if (sel.disabled) return;
    // تاریخ شمسی: سه فیلد کنار هم — searchable نکن
    if (sel.closest(".jalali-row") || sel.classList.contains("jalali-year")
        || sel.classList.contains("jalali-month") || sel.classList.contains("jalali-day")
        || /recep_(year|month|day)|_year$|_month$|_day$/.test(sel.name || "")) return;
    // فیلتر لیست‌ها: فقط select معمولی (بدون سرچ)
    if (sel.closest(".filter-bar") || sel.closest(".filter-field")
        || sel.classList.contains("no-ss") || sel.dataset.ss === "off") return;

    // فقط مشتری / صریح ss-enable
    var isCustomer =
      sel.id === "customer_id" ||
      sel.id === "ca_customer_id" ||
      sel.name === "customer_id" ||
      sel.classList.contains("customer-select") ||
      sel.classList.contains("ss-enable") ||
      sel.dataset.ss === "on";
    if (!isCustomer) return;

    sel.dataset.ssReady = "1";
    var options = Array.prototype.slice.call(sel.options || []);

    var wrap = document.createElement("div");
    wrap.className = "ss-wrap";
    if (isCustomer) wrap.classList.add("customer-ss");

    var display = document.createElement("button");
    display.type = "button";
    display.className = "ss-display";
    display.setAttribute("aria-haspopup", "listbox");

    var textSpan = document.createElement("span");
    textSpan.className = "ss-text";

    var clearBtn = document.createElement("button");
    clearBtn.type = "button";
    clearBtn.className = "ss-clear";
    clearBtn.title = "پاک کردن";
    clearBtn.innerHTML = "×";
    clearBtn.tabIndex = -1;

    var caret = document.createElement("span");
    caret.className = "ss-caret";
    caret.textContent = "▾";

    display.appendChild(textSpan);
    display.appendChild(clearBtn);
    display.appendChild(caret);

    var panel = document.createElement("div");
    panel.className = "ss-panel";

    var searchWrap = document.createElement("div");
    searchWrap.className = "ss-search-wrap";
    var searchIcon = document.createElement("span");
    searchIcon.className = "ss-search-icon";
    searchIcon.innerHTML = '<svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><line x1="16.3" y1="16.3" x2="21" y2="21"/></svg>';
    var search = document.createElement("input");
    search.type = "text";
    search.className = "ss-search";
    search.placeholder = "جستجو در گزینه‌ها...";
    search.autocomplete = "off";
    searchWrap.appendChild(searchIcon);
    searchWrap.appendChild(search);

    var list = document.createElement("ul");
    list.className = "ss-list";
    list.setAttribute("role", "listbox");

    var meta = document.createElement("div");
    meta.className = "ss-meta";

    panel.appendChild(searchWrap);
    panel.appendChild(list);
    panel.appendChild(meta);

    sel.parentNode.insertBefore(wrap, sel);
    wrap.appendChild(display);
    wrap.appendChild(panel);
    wrap.appendChild(sel);
    sel.classList.add("ss-native-hidden");

    var activeIdx = -1;
    var visibleLis = [];

    function selectedOpt() {
      return sel.options[sel.selectedIndex] || null;
    }
    function hasRealValue() {
      var o = selectedOpt();
      return !!(o && o.value !== "");
    }
    function syncDisplay() {
      var o = selectedOpt();
      if (!o || o.value === "") {
        textSpan.classList.add("is-placeholder");
        textSpan.textContent = (o && o.text) ? o.text : "— انتخاب —";
        wrap.classList.remove("has-value");
      } else {
        textSpan.classList.remove("is-placeholder");
        textSpan.textContent = o.text;
        wrap.classList.add("has-value");
      }
    }
    function setActive(i) {
      visibleLis.forEach(function (li) { li.classList.remove("ss-active"); });
      activeIdx = i;
      if (i >= 0 && i < visibleLis.length) {
        visibleLis[i].classList.add("ss-active");
        visibleLis[i].scrollIntoView({ block: "nearest" });
      }
    }
    function buildList(filter) {
      list.innerHTML = "";
      var requireSearch = sel.dataset.ssSearchRequired === "1";
      var rawFilter = (filter || "").trim();
      if (requireSearch && rawFilter.length < 2) {
        var hint = document.createElement("li");
        hint.className = "ss-empty";
        hint.textContent = rawFilter ? "حداقل ۲ حرف/عدد برای جستجو وارد کنید" : "برای جستجوی قطعه، نام یا کد انبار را تایپ کنید";
        list.appendChild(hint);
        meta.textContent = "جستجو کنید";
        visibleLis = [];
        activeIdx = -1;
        return;
      }
      visibleLis = [];
      activeIdx = -1;
      var q = (filter || "").trim().toLowerCase();
      var total = 0;
      options.forEach(function (opt, idx) {
        if (opt.hidden || opt.disabled) return;
        if (opt.style && opt.style.display === "none") return;
        var label = (opt.text || "").trim();
        var val = String(opt.value || "");
        if (q && label.toLowerCase().indexOf(q) === -1 && val.toLowerCase().indexOf(q) === -1) return;
        total++;
        var li = document.createElement("li");
        li.textContent = label || "—";
        li.dataset.index = String(idx);
        li.setAttribute("role", "option");
        if (idx === sel.selectedIndex) li.classList.add("ss-selected");
        li.addEventListener("mousedown", function (e) {
          e.preventDefault();
          pick(idx);
        });
        li.addEventListener("mouseenter", function () {
          setActive(visibleLis.indexOf(li));
        });
        list.appendChild(li);
        visibleLis.push(li);
      });
      if (total === 0) {
        var empty = document.createElement("li");
        empty.className = "ss-empty";
        empty.textContent = "موردی یافت نشد";
        list.appendChild(empty);
      }
      meta.textContent = total
        ? total + " مورد" + (q ? " برای «" + filter.trim() + "»" : "")
        : "بدون نتیجه";
      if (visibleLis.length) setActive(0);
    }
    function pick(idx) {
      sel.selectedIndex = idx;
      sel.dispatchEvent(new Event("change", { bubbles: true }));
      syncDisplay();
      close();
      display.focus();
    }
    function open() {
      document.querySelectorAll(".ss-wrap.ss-open").forEach(function (w) {
        if (w !== wrap) w.classList.remove("ss-open");
      });
      wrap.classList.add("ss-open");
      search.value = "";
      buildList("");
      setTimeout(function () { search.focus(); }, 20);
    }
    function close() {
      wrap.classList.remove("ss-open");
      activeIdx = -1;
    }

    display.addEventListener("click", function (e) {
      if (e.target === clearBtn || clearBtn.contains(e.target)) return;
      e.preventDefault();
      if (wrap.classList.contains("ss-open")) close();
      else open();
    });
    clearBtn.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      // انتخاب اولین option خالی اگر وجود دارد
      var emptyIdx = -1;
      for (var i = 0; i < options.length; i++) {
        if (!options[i].value) { emptyIdx = i; break; }
      }
      if (emptyIdx >= 0) pick(emptyIdx);
      else {
        sel.selectedIndex = -1;
        sel.dispatchEvent(new Event("change", { bubbles: true }));
        syncDisplay();
      }
    });

    search.addEventListener("input", function () { buildList(search.value); });
    search.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        e.preventDefault();
        close();
        display.focus();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        if (!visibleLis.length) return;
        setActive(Math.min(activeIdx + 1, visibleLis.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (!visibleLis.length) return;
        setActive(Math.max(activeIdx - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (activeIdx >= 0 && visibleLis[activeIdx]) {
          pick(parseInt(visibleLis[activeIdx].dataset.index, 10));
        }
      }
    });

    sel.addEventListener("change", syncDisplay);
    syncDisplay();
  }

  function enhanceAll(root) {
    (root || document).querySelectorAll("select.field-select").forEach(enhanceSelect);
  }

  document.addEventListener("click", function (e) {
    if (!e.target.closest(".ss-wrap")) {
      document.querySelectorAll(".ss-wrap.ss-open").forEach(function (w) {
        w.classList.remove("ss-open");
      });
    }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { enhanceAll(document); });
  } else {
    enhanceAll(document);
  }

  window.enhanceSearchableSelects = enhanceAll;

  // wrap openModal when available
  function hookOpenModal() {
    var _open = window.openModal;
    if (typeof _open === "function" && !_open._ssHooked) {
      window.openModal = function (id) {
        _open(id);
        var el = document.getElementById(id);
        if (el) setTimeout(function () { enhanceAll(el); }, 40);
      };
      window.openModal._ssHooked = true;
    }
  }
  hookOpenModal();
  setTimeout(hookOpenModal, 500);
})();
