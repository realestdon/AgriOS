/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { loadJS } from "@web/core/assets";

// jQuery is available as owl's global in Odoo 16 website pages but
// importing it explicitly avoids any scope issues.
// publicWidget already depends on jQuery so window.$ is safe to use
// inside widget methods — we just alias it here for clarity.
const $ = window.$;

// ─── JSON-RPC helper ──────────────────────────────────────────────────────────
async function rpc(url, params = {}) {
    const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ jsonrpc: "2.0", method: "call", id: Date.now(), params }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    const ct = res.headers.get("content-type") || "";
    if (!ct.includes("application/json")) {
        const txt = await res.text();
        throw new Error(`Expected JSON but got HTML: ${txt.substring(0, 100)}`);
    }
    const json = await res.json();
    if (json.error) throw new Error(json.error.data?.message || json.error.message || "RPC error");
    return json.result;
}

const FLAGS = { KE: "🇰🇪", UG: "🇺🇬", TZ: "🇹🇿", GH: "🇬🇭", NG: "🇳🇬", ZA: "🇿🇦", RW: "🇷🇼" };
const COLORS = ["#f5a623", "#ef4444", "#22c55e", "#a855f7", "#3b82f6", "#ec4899", "#14b8a6"];
const CURR_MAP = { KE: "KES", UG: "UGX", TZ: "TZS", GH: "GHS", NG: "NGN", ZA: "ZAR", RW: "RWF" };

// ─── Widget ───────────────────────────────────────────────────────────────────
publicWidget.registry.PayeCalculator = publicWidget.Widget.extend({
    selector: ".paye_page_wrapper",

    events: {
        "click  #btn_compute":      "_onCompute",
        "click  .yn_btn":           "_onYesNo",
        "input  .salary_input":     "_onSalaryInput",
        "input  .salary_slider":    "_onSliderInput",
        "change .structure_select": "_onStructureChange",
        "change .deduct_toggle":    "_onDeductToggle",
    },

    init() {
        this._super(...arguments);
        this._state = {
            salary:        0,
            structureId:   null,
            currency:      "KES",
            is_resident:   true,
            is_secondary:  false,
            deductNSSF:    true,
            deductPAYE:    true,
            deductHousing: true,
            deductNHIF:    true,
        };
    },

    start() {
        const p = this._super(...arguments);
        this._loadCountries();
        return p;
    },

    // ─── Step 1: countries ────────────────────────────────────────────────────
    async _loadCountries() {
        try {
            const res = await rpc("/paye/countries");
            if (res && res.success && res.countries && res.countries.length) {
                this._renderCountryTabs(res.countries);
                await this._loadStructures(res.countries[0].id, res.countries[0].code);
            } else {
                this._showError("No salary structures found. Please add a country to your payroll structure in Odoo.");
            }
        } catch (e) {
            console.error("PAYE countries error:", e);
            this._showError("Could not load countries: " + e.message);
        }
    },

    // ─── Step 2: structures for selected country ───────────────────────────────
    async _loadStructures(countryId, countryCode) {
        try {
            const res = await rpc("/paye/structures", { country_id: countryId });
            if (res && res.success && res.structures && res.structures.length) {
                this._renderStructureSelector(res.structures);
                this._state.structureId = res.structures[0].id;
                this._state.currency = CURR_MAP[countryCode] || "KES";
                this.$(".salary_currency").text(this._state.currency);
                this._enableComputeIfReady();
            } else {
                this.$(".structure_selector_wrap").hide();
                this._showError("No salary structures found for this country.");
                this.$("#btn_compute").prop("disabled", true);
            }
        } catch (e) {
            console.error("PAYE structures error:", e);
            this._showError("Could not load structures: " + e.message);
        }
    },

    // ─── Step 3: compute ──────────────────────────────────────────────────────
    async _onCompute() {
        const salary = parseFloat(this.$(".salary_input").val()) || 0;
        if (!salary || salary <= 0) { this._showError("Please enter a valid gross salary."); return; }
        if (!this._state.structureId) { this._showError("Please select a salary structure."); return; }

        this._hideError();
        this._setLoading(true);
        this._hideResults();

        try {
            const res = await rpc("/paye/compute", {
                structure_id:   this._state.structureId,
                gross_salary:   salary,
                is_resident:    this._state.is_resident,
                is_secondary:   this._state.is_secondary,
                deduct_nssf:    this._state.deductNSSF,
                deduct_paye:    this._state.deductPAYE,
                deduct_housing: this._state.deductHousing,
                deduct_nhif:    this._state.deductNHIF,
            });
            if (res && res.success) {
                this._renderResults(res);
            } else {
                this._showError((res && res.error) || "Computation failed.");
            }
        } catch (e) {
            console.error("PAYE compute error:", e);
            this._showError("Server error: " + e.message);
        } finally {
            this._setLoading(false);
        }
    },

    // ─── Render country tabs ──────────────────────────────────────────────────
    _renderCountryTabs(countries) {
        const $wrap = this.$("#country_tabs");
        $wrap.empty();
        countries.forEach((c, i) => {
            const flag = FLAGS[c.code] || "🌍";
            const $btn = $(`<button class="country_tab${i === 0 ? " active" : ""}">${flag} ${this._esc(c.name)}</button>`);
            $btn.data("countryId",   c.id);
            $btn.data("countryCode", c.code);
            $wrap.append($btn);
        });
        // Use Odoo widget event delegation — bind on the wrapper, not dynamically
        $wrap.off("click").on("click", ".country_tab", async (ev) => {
            const $btn = $(ev.currentTarget);
            $wrap.find(".country_tab").removeClass("active");
            $btn.addClass("active");
            this._hideResults();
            await this._loadStructures(
                $btn.data("countryId"),
                $btn.data("countryCode")
            );
        });
    },

    // ─── Render structure selector ────────────────────────────────────────────
    _renderStructureSelector(structures) {
        const $sel = this.$(".structure_select");
        $sel.empty();
        structures.forEach((s) => {
            $sel.append($("<option>").val(s.id).text(s.name));
        });
        this.$(".structure_selector_wrap").show();
    },

    // ─── Render results ───────────────────────────────────────────────────────
    _renderResults(res) {
        const { currency, gross, lines, net, total_deductions, skipped_rules } = res;
        const curr = currency || this._state.currency;
        const fmt  = (n) => Math.round(n).toLocaleString("en-KE");

        this.$(".curr_label").text(curr);
        this.$(".net_pay_amount .curr").text(curr);
        this.$(".gross_salary_display .amount").text(fmt(gross));
        this.$(".gross_salary_display .curr_label").text(curr);
        this.$(".net_pay_amount .net_val").text(fmt(net));

        // Breakdown rows
        const $bd = this.$(".results_breakdown").empty();
        let ci = 0;
        lines.filter((l) => l.appears_on_payslip).forEach((line) => {
            const isDed   = line.category === "DED";
            const isNet   = line.category === "NET";
            const isGross = line.category === "GROSS" || line.category === "BASIC";
            if (!isDed && !isNet && !isGross && !line.amount && !line.error) return;

            const color = COLORS[ci++ % COLORS.length];
            const pct   = gross > 0 ? ((Math.abs(line.amount) / gross) * 100).toFixed(1) + "%" : "—";
            let amtHtml = line.error
                ? `<span class="breakdown_amount" style="color:#f59e0b;">⚠ Error</span>`
                : isDed
                    ? `<span class="breakdown_amount deducted">− ${this._esc(curr)} ${fmt(line.amount)}</span>`
                    : `<span class="breakdown_amount">${this._esc(curr)} ${fmt(line.amount)}</span>`;

            $bd.append(`<div class="breakdown_item">
                <div class="breakdown_item_left">
                    <span class="breakdown_dot" style="background:${color}"></span>
                    <div>
                        <div class="breakdown_label">${this._esc(line.name)}</div>
                        <div class="breakdown_pct">${this._esc(line.category_name)} · ${pct}</div>
                    </div>
                </div>${amtHtml}</div>`);
        });

        $bd.append(`<div class="breakdown_item" style="border-top:2px solid var(--border);margin-top:8px;padding-top:16px;">
            <div class="breakdown_item_left">
                <div class="breakdown_label" style="font-size:13px;color:var(--text-muted);">Total Deductions</div>
            </div>
            <span class="breakdown_amount deducted" style="font-size:13px;">${this._esc(curr)} ${fmt(total_deductions)}</span>
        </div>`);

        // Skipped rules note
        this.$(".skipped_rules_note").remove();
        if (skipped_rules && skipped_rules.length) {
            const names = skipped_rules.map((r) => `<strong>${this._esc(r.name)}</strong>`).join(", ");
            $bd.after(`<div class="skipped_rules_note" style="margin:0 32px 16px;padding:12px 16px;
                background:#f0f9ff;border:1px solid #bae6fd;border-radius:8px;font-size:13px;
                color:#0369a1;line-height:1.6;">
                <strong>ℹ Not included:</strong> ${names} — these require an individual employee contract.
            </div>`);
        }

        // Donut
        const byCode = {};
        lines.forEach((l) => { byCode[l.code] = l; });
        const ga = (...codes) => { for (const c of codes) { if (byCode[c] && !byCode[c].error) return byCode[c].amount; } return 0; };
        this._updateDonut(ga("NSSF"), ga("PAYE"), ga("NHIF","SHIF"), Math.max(0, total_deductions - ga("NSSF") - ga("PAYE") - ga("NHIF","SHIF")), net, gross);
        this._updateHeroDonut(net, gross, curr);
        this._showResults();
    },

    // ─── Donut helpers ────────────────────────────────────────────────────────
    _updateDonut(nssf, paye, nhif, other, net, total) {
        if (!total) return;
        const C = 2 * Math.PI * 60;
        let offset = 0;
        [["seg_net", net], ["seg_paye", paye], ["seg_nssf", nssf], ["seg_nhif", nhif], ["seg_other", other]].forEach(([id, val]) => {
            const $el = this.$("#" + id);
            if (!$el.length) return;
            const dash = (Math.max(0, val) / total) * C;
            $el.attr({ "stroke-dasharray": `${dash.toFixed(2)} ${(C-dash).toFixed(2)}`, "stroke-dashoffset": (-offset).toFixed(2) });
            offset += dash;
        });
        this.$(".donut_net_pct").text(total > 0 ? ((net / total) * 100).toFixed(0) + "%" : "0%");
    },

    _updateHeroDonut(net, total, currency) {
        if (!total) return;
        const C = 2 * Math.PI * 90;
        const dash = (net / total) * C;
        this.$(".hero_seg_net").attr({ "stroke-dasharray": `${dash.toFixed(2)} ${(C-dash).toFixed(2)}` });
        this.$(".hero_net_pct").text(((net / total) * 100).toFixed(0) + "%");
        this.$(".hero_net_val").text(currency + " " + Math.round(net).toLocaleString("en-KE"));
    },

    // ─── Event handlers ───────────────────────────────────────────────────────
    _onYesNo(ev) {
        const $btn  = $(ev.currentTarget);
        const field = $btn.data("field");
        const val   = $btn.data("value");
        $btn.closest(".yes_no_select").find(".yn_btn").removeClass("active");
        $btn.addClass("active");
        if (field === "is_resident")  this._state.is_resident  = (val === "yes");
        if (field === "is_secondary") this._state.is_secondary = (val === "yes");
        this._hideResults();
    },

    _onDeductToggle(ev) {
        const key = $(ev.currentTarget).data("deduct");
        this._state[key] = ev.currentTarget.checked;
        this._hideResults();
    },

    _onSalaryInput() {
        const val = Math.max(0, Math.min(parseFloat(this.$(".salary_input").val()) || 0, 2000000));
        this._state.salary = val;
        this.$(".salary_slider").val(val);
        this._updateSliderTrack();
        this._enableComputeIfReady();
        this._hideError();
    },

    _onSliderInput() {
        const val = parseFloat(this.$(".salary_slider").val()) || 0;
        this._state.salary = val;
        this.$(".salary_input").val(val);
        this._updateSliderTrack();
        this._enableComputeIfReady();
    },

    _onStructureChange(ev) {
        this._state.structureId = parseInt($(ev.currentTarget).val(), 10) || null;
        this._enableComputeIfReady();
        this._hideResults();
    },

    // ─── UI helpers ───────────────────────────────────────────────────────────
    _enableComputeIfReady() {
        this.$("#btn_compute").prop("disabled", !(this._state.salary > 0 && this._state.structureId));
    },

    _setLoading(on) {
        this.$(".btn_compute_text").toggle(!on);
        this.$(".btn_compute_loading").toggle(on);
        this.$("#btn_compute").prop("disabled", on);
    },

    _showResults() {
        this.$(".results_empty_state").hide();
        this.$(".results_content").show();
    },

    _hideResults() {
        this.$(".results_content").hide();
        this.$(".results_empty_state").show();
    },

    _showError(msg) {
        this.$(".compute_error").text(msg).show();
    },

    _hideError() {
        this.$(".compute_error").hide();
    },

    _updateSliderTrack() {
        const el = this.$(".salary_slider")[0];
        if (!el) return;
        const pct = ((this._state.salary - el.min) / (el.max - el.min)) * 100;
        el.style.setProperty("--slider-pct", pct.toFixed(1) + "%");
    },

    _esc(str) {
        return String(str || "")
            .replace(/&/g, "&amp;").replace(/</g, "&lt;")
            .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    },
});