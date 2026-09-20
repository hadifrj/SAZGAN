/* این فایل بخشی از تفکیک base-ui.js (فاز ۲، بخش ۲) است — کد بدون تغییر منطق از static/js/base-ui.js منتقل شده. */

function showVersionInfo() {
            const modal = document.getElementById('version-info-modal');
            if (modal) {
                modal.style.display = 'flex';
                setTimeout(() => modal.classList.add('open'), 10);
            }
        }
        
        function closeVersionInfo() {
            const modal = document.getElementById('version-info-modal');
            if (modal) {
                modal.classList.remove('open');
                setTimeout(() => modal.style.display = 'none', 300);
            }
        }
        
        // بستن modal با Escape
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                const modal = document.getElementById('version-info-modal');
                if (modal && modal.style.display !== 'none') {
                    closeVersionInfo();
                }
            }
        });
