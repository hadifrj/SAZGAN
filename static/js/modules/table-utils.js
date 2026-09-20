/* این فایل بخشی از تفکیک base-ui.js (فاز ۲، بخش ۲) است — کد بدون تغییر منطق از static/js/base-ui.js منتقل شده. */

/* نکته: این فایل جزو ۹ ماژول نام‌برده در سند فاز ۲ نیست -- cardifyTables و
   sazganPaginate/autoPaginateTables هیچ‌کدام به مسئولیت‌های ۹گانه‌ی سند تعلق ندارند
   (جدول‌های ریسپانسیو و صفحه‌بندی سمت کلاینت‌اند)، برای جلوگیری از جازدن اجباری در
   یک فایل نامربوط، به‌صورت یک فایل دهم و صریح نگه داشته شدند. */

/* --- block 1 --- */
(function(){
  function cardifyTables(){
    if (window.innerWidth > 900) {
      document.querySelectorAll('table.cardified').forEach(function(t){ t.classList.remove('cardified'); });
      return;
    }
    document.querySelectorAll('.table-wrap table, .cp-table-wrap table').forEach(function(table){
      if (table.classList.contains('no-cardify')) return;
      var headerRow = table.querySelector('thead tr') || table.querySelector('tr');
      if (!headerRow) return;
      var headers = Array.from(headerRow.querySelectorAll('th, td')).map(function(h){ return h.textContent.trim(); });
      if (!headers.length) return;
      var bodyRows = table.querySelectorAll('tbody tr');
      if (!bodyRows.length) {
        bodyRows = Array.from(table.querySelectorAll('tr')).slice(1);
      }
      bodyRows.forEach(function(row){
        var cells = row.querySelectorAll('td');
        cells.forEach(function(td, i){
          if (headers[i]) td.setAttribute('data-label', headers[i]);
        });
      });
      table.classList.add('cardified');
    });
  }
  document.addEventListener('DOMContentLoaded', cardifyTables);
  window.addEventListener('resize', function(){
    clearTimeout(window.__cardifyT);
    window.__cardifyT = setTimeout(cardifyTables, 150);
  });
})();

/* ==========================================================================
   ابزار عمومی صفحه‌بندی سمت کلاینت برای جدول‌های لیست (پیش‌فرض ۲۵ ردیف/صفحه)
   استفاده: sazganPaginate('id-جدول', { perPage: 25, rowSelector: '.customer-row', paginationId: 'id-محل-دکمه‌ها' })
   خودش ردیف‌های مخفی‌شده (display:none — مثلاً از جستجو) را نادیده می‌گیرد.
   ========================================================================== */
function sazganPaginate(tableId, opts) {
    opts = opts || {};
    var perPage = opts.perPage || 25;
    var table = document.getElementById(tableId);
    if (!table) return null;
    var rowSelector = opts.rowSelector || 'tr:not(:first-child)';
    var pager = document.getElementById(opts.paginationId || (tableId + '-pagination'));
    var page = 1;

    function visibleRows() {
        var all = Array.prototype.slice.call(table.querySelectorAll(rowSelector));
        return all.filter(function (r) { return r.dataset.lpFiltered !== '1'; });
    }

    function render() {
        var rows = visibleRows();
        var total = rows.length;
        var pageCount = Math.max(1, Math.ceil(total / perPage));
        if (page > pageCount) page = pageCount;
        rows.forEach(function (r, i) {
            var onPage = Math.floor(i / perPage) + 1;
            r.style.display = (onPage === page) ? '' : 'none';
        });
        if (!pager) return;
        pager.innerHTML = '';
        if (pageCount <= 1) return;

        function makeBtn(label, targetPage, opts2) {
            opts2 = opts2 || {};
            var b = document.createElement('button');
            b.type = 'button';
            b.textContent = label;
            if (opts2.active) b.className = 'active';
            if (opts2.disabled) b.disabled = true;
            b.addEventListener('click', function () {
                page = targetPage;
                render();
                if (table.scrollIntoView) table.scrollIntoView({ block: 'nearest' });
            });
            return b;
        }

        pager.appendChild(makeBtn('قبلی', page - 1, { disabled: page === 1 }));

        var pages = [];
        for (var p = 1; p <= pageCount; p++) {
            if (p === 1 || p === pageCount || Math.abs(p - page) <= 1) pages.push(p);
        }
        var last = 0;
        pages.forEach(function (p) {
            if (last && p - last > 1) {
                var dots = document.createElement('span');
                dots.className = 'lp-ellipsis';
                dots.textContent = '…';
                pager.appendChild(dots);
            }
            pager.appendChild(makeBtn(String(p), p, { active: p === page }));
            last = p;
        });

        pager.appendChild(makeBtn('بعدی', page + 1, { disabled: page === pageCount }));
    }

    // اگر فیلتر/جستجوی جدول ردیفی را مخفی کند (display:none) و دوباره صدا زده شود، صفحه‌بندی هم به‌روزرسانی می‌شود
    var api = {
        refresh: function () { page = 1; render(); },
        render: render
    };
    render();
    return api;
}


/* صفحه‌بندی خودکار جداول لیست (حداکثر ۲۵ ردیف) اگر هنوز صفحه‌بندی ندارند */
(function autoPaginateTables() {
  function run() {
    if (typeof sazganPaginate !== 'function') return;
    document.querySelectorAll('table').forEach(function (table, idx) {
      if (table.closest('.no-auto-page') || table.dataset.autoPaged === '1') return;
      if (table.id && document.getElementById(table.id + '-pagination')) return;
      // فقط جداول داده با بیش از ۲۵ ردیف بدنه
      var rows = table.tBodies && table.tBodies[0] ? table.tBodies[0].rows : [];
      if (!rows || rows.length <= 25) return;
      // اگر والد قبلاً pagination سرور دارد رد شو
      var parent = table.closest('.card, .card-body, .table-wrap, main, .content') || table.parentElement;
      if (parent && parent.querySelector('.sg-pagination, .list-pagination')) return;
      if (!table.id) table.id = 'auto-table-' + idx;
      var pagerId = table.id + '-pagination';
      var pager = document.getElementById(pagerId);
      if (!pager) {
        pager = document.createElement('div');
        pager.id = pagerId;
        pager.className = 'list-pagination';
        pager.style.marginTop = '10px';
        pager.style.display = 'flex';
        pager.style.gap = '6px';
        pager.style.flexWrap = 'wrap';
        pager.style.justifyContent = 'center';
        if (table.parentNode) table.parentNode.insertBefore(pager, table.nextSibling);
      }
      table.dataset.autoPaged = '1';
      var rowSelector = table.tHead ? 'tbody tr' : 'tr:not(:first-child)';
      sazganPaginate(table.id, { perPage: 25, rowSelector: rowSelector, paginationId: pagerId });
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { setTimeout(run, 50); });
  } else {
    setTimeout(run, 50);
  }
})();
