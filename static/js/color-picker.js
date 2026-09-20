/**
 * Color Picker — فشرده و کارتی (مثل مدل iOS/Android)
 * بدون نمایش کد HEX/RGB
 */
class ColorPicker {
    constructor(options = {}) {
        this.options = {
            currentColor: '#1976d2',
            onSelect: null,
            ...options
        };
        this.currentColor = this.options.currentColor;
        this.hue = 210;
        this.sat = 80;
        this.bri = 90;
        this._targetKey = null;
        this.presets = [
            '#42A5F5', '#26A69A', '#66BB6A', '#EF5350', '#AB47BC', '#5C6BC0',
            '#78909C', '#546E7A', '#9CCC65', '#FFA726', '#8D6E63', '#29B6F6',
            '#EC407A', '#7E57C2', '#26C6DA', '#FFCA28', '#FF7043', '#8D6E63'
        ];
        this.init();
    }

    init() {
        if (document.getElementById('cp-modal')) return;
        const html = `
<div class="cp-modal" id="cp-modal" style="display:none;" aria-hidden="true">
  <div class="cp-overlay" data-cp-close></div>
  <div class="cp-card" role="dialog" aria-label="انتخاب رنگ">
    <div class="cp-gradient" id="cp-gradient">
      <div class="cp-pointer" id="cp-pointer"></div>
    </div>
    <div class="cp-hue" id="cp-hue">
      <div class="cp-hue-pointer" id="cp-hue-pointer"></div>
    </div>
    <div class="cp-presets" id="cp-presets"></div>
    <div class="cp-footer">
      <button type="button" class="cp-btn cp-btn-ghost" data-cp-close>خیر</button>
      <button type="button" class="cp-btn cp-btn-primary" id="cp-select">انتخاب</button>
    </div>
  </div>
</div>`;
        document.body.insertAdjacentHTML('beforeend', html);
        this.modal = document.getElementById('cp-modal');
        this.gradient = document.getElementById('cp-gradient');
        this.pointer = document.getElementById('cp-pointer');
        this.hueBar = document.getElementById('cp-hue');
        this.huePointer = document.getElementById('cp-hue-pointer');
        this.buildPresets();
        this.bind();
    }

    buildPresets() {
        const root = document.getElementById('cp-presets');
        root.innerHTML = '';
        this.presets.forEach(c => {
            const b = document.createElement('button');
            b.type = 'button';
            b.className = 'cp-swatch';
            b.style.background = c;
            b.title = c;
            b.addEventListener('click', () => this.setFromHex(c));
            root.appendChild(b);
        });
    }

    bind() {
        this.modal.querySelectorAll('[data-cp-close]').forEach(el => {
            el.addEventListener('click', () => this.close());
        });
        document.getElementById('cp-select').addEventListener('click', () => this.select());

        const onGrad = (e) => {
            e.preventDefault();
            const pt = e.touches ? e.touches[0] : e;
            const r = this.gradient.getBoundingClientRect();
            const x = Math.max(0, Math.min(pt.clientX - r.left, r.width));
            const y = Math.max(0, Math.min(pt.clientY - r.top, r.height));
            this.sat = (x / r.width) * 100;
            this.bri = 100 - (y / r.height) * 100;
            this.updateFromHSB();
        };
        const onHue = (e) => {
            e.preventDefault();
            const pt = e.touches ? e.touches[0] : e;
            const r = this.hueBar.getBoundingClientRect();
            const x = Math.max(0, Math.min(pt.clientX - r.left, r.width));
            this.hue = (x / r.width) * 360;
            this.updateFromHSB();
        };

        let dragG = false, dragH = false;
        this.gradient.addEventListener('mousedown', e => { dragG = true; onGrad(e); });
        this.hueBar.addEventListener('mousedown', e => { dragH = true; onHue(e); });
        this.gradient.addEventListener('touchstart', e => { dragG = true; onGrad(e); }, {passive:false});
        this.hueBar.addEventListener('touchstart', e => { dragH = true; onHue(e); }, {passive:false});
        window.addEventListener('mousemove', e => { if (dragG) onGrad(e); if (dragH) onHue(e); });
        window.addEventListener('touchmove', e => { if (dragG) onGrad(e); if (dragH) onHue(e); }, {passive:false});
        window.addEventListener('mouseup', () => { dragG = dragH = false; });
        window.addEventListener('touchend', () => { dragG = dragH = false; });
    }

    hsbToHex(h, s, b) {
        s /= 100; b /= 100;
        const k = n => (n + h / 60) % 6;
        const f = n => b * (1 - s * Math.max(0, Math.min(k(n), 4 - k(n), 1)));
        const r = Math.round(f(5) * 255);
        const g = Math.round(f(3) * 255);
        const bl = Math.round(f(1) * 255);
        return '#' + [r, g, bl].map(x => x.toString(16).padStart(2, '0')).join('').toUpperCase();
    }

    hexToHsb(hex) {
        let r = 0, g = 0, b = 0;
        const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex || '');
        if (m) { r = parseInt(m[1],16)/255; g = parseInt(m[2],16)/255; b = parseInt(m[3],16)/255; }
        const max = Math.max(r,g,b), min = Math.min(r,g,b), d = max - min;
        let h = 0;
        if (d) {
            if (max === r) h = ((g - b) / d) % 6;
            else if (max === g) h = (b - r) / d + 2;
            else h = (r - g) / d + 4;
            h *= 60; if (h < 0) h += 360;
        }
        const s = max === 0 ? 0 : (d / max) * 100;
        const bri = max * 100;
        return { h, s, b: bri };
    }

    updateFromHSB() {
        this.currentColor = this.hsbToHex(this.hue, this.sat, this.bri);
        const pure = this.hsbToHex(this.hue, 100, 100);
        this.gradient.style.background = `linear-gradient(to top, #000, transparent), linear-gradient(to right, #fff, ${pure})`;
        const r = this.gradient.getBoundingClientRect();
        if (r.width) {
            this.pointer.style.left = (this.sat / 100 * r.width) + 'px';
            this.pointer.style.top = ((100 - this.bri) / 100 * r.height) + 'px';
        }
        const hr = this.hueBar.getBoundingClientRect();
        if (hr.width) {
            this.huePointer.style.left = (this.hue / 360 * hr.width) + 'px';
        }
        // mark active preset
        document.querySelectorAll('.cp-swatch').forEach(el => {
            el.classList.toggle('active', el.title.toUpperCase() === this.currentColor);
        });
    }

    setFromHex(hex) {
        const hsb = this.hexToHsb(hex);
        this.hue = hsb.h; this.sat = hsb.s; this.bri = hsb.b;
        this.updateFromHSB();
    }

    open(opts = {}) {
        if (opts.color) this.setFromHex(opts.color);
        else this.updateFromHSB();
        if (opts.onSelect) this.options.onSelect = opts.onSelect;
        this._targetKey = opts.targetKey || null;
        this.modal.style.display = 'flex';
        this.modal.setAttribute('aria-hidden', 'false');
        requestAnimationFrame(() => {
            this.updateFromHSB();
            this.modal.classList.add('open');
        });
    }

    close() {
        this.modal.classList.remove('open');
        this.modal.setAttribute('aria-hidden', 'true');
        setTimeout(() => { this.modal.style.display = 'none'; }, 200);
    }

    select() {
        if (typeof this.options.onSelect === 'function') {
            this.options.onSelect(this.currentColor, this._targetKey);
        }
        this.close();
    }
}

let colorPickerInstance;
function __initColorPicker() {
    if (!window.colorPickerInstance) {
        colorPickerInstance = new ColorPicker();
        window.colorPickerInstance = colorPickerInstance;
    }
}
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', __initColorPicker);
} else {
    __initColorPicker();
}
