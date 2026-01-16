/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import ajax from "web.ajax";

publicWidget.registry.MewsPosPaymentForm = publicWidget.Widget.extend({
    selector: ".mews-pos-payment-form",

    events: {
        "input #card_number": "_onCardNumberInput",
        "input #card_name": "_onCardNameInput",
        "change #card_month, #card_year": "_onExpireChange",
        "change input[name='installment']": "_onInstallmentChange",
    },

    start() {
        this._super(...arguments);
        this.$installmentContainer = this.$("#mews_installment_container");
        this.amount = parseFloat(this.$el.data("amount")) || 0;
        this.categoryIds = this.$el.data("category-ids") || "";
        this.currentBin = null;
        return Promise.resolve();
    },

    // Kart numarası her değiştiğinde
    _onCardNumberInput(ev) {
        const input = ev.currentTarget;
        let value = input.value.replace(/\D/g, "");
        value = value.substring(0, 19);

        const groups = [];
        for (let i = 0; i < value.length; i += 4) {
            groups.push(value.substring(i, i + 4));
        }
        input.value = groups.join(" ");

        const visibleValue = groups.length ? groups.join(" ") : "••••  ••••  ••••  ••••";
        this.$(".card_number_preview").text(visibleValue);

        if (value.length >= 6) {
            const bin = value.substring(0, 6);
            if (bin !== this.currentBin) {
                this.currentBin = bin;
                this._loadInstallments(bin);
            }
        }
    },

    _onCardNameInput(ev) {
        const value = ev.currentTarget.value || "İsim Soyisim";
        this.$(".fullname_preview").text(value);
    },

    _onExpireChange() {
        const month = this.$("#card_month").val() || "AA";
        const year = this.$("#card_year").val() || "YY";
        this.$(".date_month_preview").text(month);
        this.$(".date_year_preview").text(year.toString().slice(-2));
    },

    _onInstallmentChange(ev) {
        let $hidden = this.$("input[name='installment_selected']");
        if (!$hidden.length) {
            $hidden = $("<input>", {
                type: "hidden",
                name: "installment_selected",
            }).appendTo(this.$el);
        }
        $hidden.val($(ev.currentTarget).val());
    },

    _loadInstallments(bin) {
        if (!this.$installmentContainer.length || !this.amount) {
            return;
        }

        this.$installmentContainer
            .addClass("opacity-50")
            .html('<span class="text-muted">Taksit seçenekleri yükleniyor...</span>');

        ajax.jsonRpc("/mews_pos/get_payment_installments", "call", {
            amount: this.amount,
            bin_number: bin,
        }).then((result) => {
            // Controller'da sen result'ı result: {...} altında döndürüyorsun
            const payload = result.result || result;
            this._renderInstallments(payload);
        }).catch((err) => {
            console.error("Mews POS installments error:", err);
            this.$installmentContainer
                .removeClass("opacity-50")
                .html('<span class="text-danger">Taksit seçenekleri alınırken hata oluştu.</span>');
        });
    },

    _renderInstallments(payload) {
        const installmentsData = payload && payload.installments ? payload.installments : [];

        if (!installmentsData.length) {
            this.$installmentContainer
                .removeClass("opacity-50")
                .html('<span class="text-muted">Bu kart için taksit seçeneği bulunamadı.</span>');
            return;
        }

        const $wrapper = $("<div>", { class: "list-group" });

        let index = 0;
        installmentsData.forEach((bankData) => {
            const bankName = bankData.bank && bankData.bank.name ? bankData.bank.name : "Banka";
            const $bankHeader = $("<h6>", {
                class: "text-muted px-3 mb-2 mt-2",
                text: bankName,
            });
            $wrapper.append($bankHeader);

            (bankData.installments || []).forEach((inst) => {
                const id = `mews_inst_${index}`;
                const isFirst = index === 0;
                const label = inst.installment_count === 1
                    ? "Tek Çekim"
                    : `${inst.installment_count} Taksit`;
                const badge = inst.is_campaign
                    ? '<span class="badge bg-success ms-2">Kampanya</span>'
                    : "";
                const monthly = inst.installment_amount || inst.amount_per || 0;
                const total = inst.total_amount || (monthly * inst.installment_count);

                const $item = $(`
                    <label class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
                        <div>
                            <div class="fw-semibold">${label}${badge}</div>
                            <div class="text-muted small">${monthly.toFixed ? monthly.toFixed(2) : monthly} ₺ x ${inst.installment_count} = ${total.toFixed ? total.toFixed(2) : total} ₺</div>
                        </div>
                        <div class="form-check">
                            <input type="radio"
                                   class="form-check-input"
                                   id="${id}"
                                   name="installment"
                                   value="${inst.installment_count}"
                                   ${isFirst ? "checked" : ""}/>
                        </div>
                    </label>
                `);
                $wrapper.append($item);
                index++;
            });
        });

        this.$installmentContainer
            .removeClass("opacity-50")
            .empty()
            .append($wrapper);

        const $checked = this.$("input[name='installment']:checked");
        if ($checked.length) {
            this._onInstallmentChange({ currentTarget: $checked[0] });
        }
    },
});