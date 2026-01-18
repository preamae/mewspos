/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.MewsPosPaymentForm = publicWidget.Widget.extend({
    selector: ".mews-pos-payment-form",

    events: {
        "input #card_number": "_onCardNumberInput",
        "input #card_name": "_onCardNameInput",
        "change #card_month, #card_year": "_onExpireChange",
        "change input[name='installment']": "_onInstallmentChange",
    },

    /**
     * @override
     */
    start() {
        this._super(...arguments);
        this.installmentContainer = document.getElementById("mews_installment_container");

        // Orijinal tutarı sakla
        const formData = this.el.dataset;
        this.originalAmount = parseFloat(formData.amount) || 0;
        this.amount = this.originalAmount;
        this.categoryIds = formData.categoryIds || "";
        this.currentBin = null;
        this.selectedInstallmentCount = 1;
        this.selectedTotalAmount = this.originalAmount;

        // Odoo payment formunu bul
        this.paymentForm = document.querySelector('form[name="o_payment_submit_form"]');

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

        // Preview güncelle
        const cardPreview = this.el.querySelector(".card_number_preview");
        if (cardPreview) {
            const visibleValue = groups.length ? groups.join(" ") : "••••  ••••  ••••  ••••";
            cardPreview.textContent = visibleValue;
        }

        // BIN değiştiğinde kontrol et
        if (value.length >= 6) {
            const bin = value.substring(0, 6);
            if (bin !== this.currentBin) {
                this.currentBin = bin;
                this._loadInstallments(bin);
            }
        } else {
            // BIN yeterli değilse taksit seçeneklerini temizle
            this.currentBin = null;
            this._clearInstallments();
            this.selectedInstallmentCount = 1;
            this.selectedTotalAmount = this.originalAmount;
            this._updateTotalAmount(this.originalAmount, 1);
        }
    },

    _onCardNameInput(ev) {
        const value = ev.currentTarget.value || "İsim Soyisim";
        const namePreview = this.el.querySelector(".fullname_preview");
        if (namePreview) {
            namePreview.textContent = value;
        }
    },

    _onExpireChange() {
        const monthSelect = this.el.querySelector("#card_month");
        const yearSelect = this.el.querySelector("#card_year");
        const monthPreview = this.el.querySelector(".date_month_preview");
        const yearPreview = this.el.querySelector(".date_year_preview");

        if (monthSelect && monthPreview) monthPreview.textContent = monthSelect.value || "AA";
        if (yearSelect && yearPreview) yearPreview.textContent = yearSelect.value ? yearSelect.value.toString().slice(-2) : "YY";
    },

    _onInstallmentChange(ev) {
        const selectedValue = ev.currentTarget.value;
        const selectedInstallmentCount = parseInt(selectedValue) || 1;

        // Taksit bilgilerini al
        const listItem = ev.currentTarget.closest('label.list-group-item');
        let totalAmount = this.originalAmount;

        if (listItem) {
            const amountText = listItem.querySelector('.text-muted.small')?.textContent || '';
            const matches = amountText.match(/(\d+\.?\d*)\s*₺\s*x\s*(\d+)\s*=\s*(\d+\.?\d*)/);

            if (matches && matches.length >= 4) {
                totalAmount = parseFloat(matches[3]);
            }
        }

        // Değerleri sakla
        this.selectedInstallmentCount = selectedInstallmentCount;
        this.selectedTotalAmount = totalAmount;

        // Toplam tutarı görsel olarak güncelle
        this._updateTotalAmount(totalAmount, selectedInstallmentCount);
    },

    _updateTotalAmount(totalAmount, installmentCount) {
        try {
            // Sayfadaki toplam tutarı güncelleyen basit bir yöntem
            const totalElements = document.querySelectorAll('.total-amount, .amount_total, .oe_currency_value:last-child');
            totalElements.forEach(el => {
                if (el.textContent.includes('₺')) {
                    el.textContent = `${totalAmount.toFixed(2)} ₺`;
                }
            });

            // Özel bilgilendirme mesajı
            let infoDiv = document.getElementById('mews-installment-info');
            if (!infoDiv && installmentCount > 1) {
                infoDiv = document.createElement('div');
                infoDiv.id = 'mews-installment-info';
                infoDiv.className = 'alert alert-warning mt-2';
                this.installmentContainer.parentNode.appendChild(infoDiv);
            }

            if (installmentCount > 1 && infoDiv) {
                const diff = totalAmount - this.originalAmount;
                infoDiv.innerHTML = `
                    <strong>${installmentCount} Taksit Seçildi</strong><br>
                    <small>Toplam Ödeme: ${totalAmount.toFixed(2)} ₺ (${diff > 0 ? '+' : ''}${diff.toFixed(2)} ₺)</small>
                `;
                infoDiv.style.display = 'block';
            } else if (infoDiv) {
                infoDiv.style.display = 'none';
            }
        } catch (error) {
            console.warn('Mews POS: Toplam tutar güncellenirken hata:', error);
        }
    },

    _clearInstallments() {
        if (!this.installmentContainer) return;

        this.installmentContainer.innerHTML = `
            <p class="text-muted mb-0">
                İlk 6 haneyi girdikten sonra taksit seçenekleri yüklenecektir.
            </p>
        `;

        const infoDiv = document.getElementById('mews-installment-info');
        if (infoDiv) infoDiv.style.display = 'none';
    },

    async _loadInstallments(bin) {
        if (!this.installmentContainer) return;

        this.installmentContainer.innerHTML = '<span class="text-muted">Taksit seçenekleri yükleniyor...</span>';

        try {
            const result = await rpc("/mews_pos/get_payment_installments", {
                amount: this.amount,
                bin_number: bin,
                category_ids: this.categoryIds,
            });

            this._renderInstallments(result);
        } catch (error) {
            console.error("Mews POS installments error:", error);
            this.installmentContainer.innerHTML = '<span class="text-danger">Taksit seçenekleri alınamadı.</span>';
        }
    },

    _renderInstallments(response) {
        if (!this.installmentContainer) return;

        const responseData = response.result || response;

        if (!responseData || !responseData.installments || responseData.installments.length === 0) {
            this.installmentContainer.innerHTML = '<span class="text-muted">Bu kart için taksit seçeneği bulunamadı.</span>';
            return;
        }

        let html = '<div class="list-group">';
        let index = 0;

        responseData.installments.forEach((bankData) => {
            if (!bankData.installments || bankData.installments.length === 0) return;

            html += `<h6 class="text-muted px-3 mb-2 mt-2">${bankData.bank?.name || 'Banka'}</h6>`;

            bankData.installments.forEach((inst) => {
                const monthly = inst.installment_amount || 0;
                const total = inst.total_amount || (monthly * inst.installment_count);
                const isFirst = index === 0;

                html += `
                    <label class="list-group-item list-group-item-action">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <div class="fw-semibold">
                                    ${inst.installment_count === 1 ? 'Tek Çekim' : inst.installment_count + ' Taksit'}
                                    ${inst.is_campaign ? '<span class="badge bg-success ms-2">Kampanya</span>' : ''}
                                </div>
                                <div class="text-muted small">
                                    ${monthly.toFixed(2)} ₺ x ${inst.installment_count} = ${total.toFixed(2)} ₺
                                </div>
                            </div>
                            <input type="radio" class="form-check-input" name="installment" 
                                   value="${inst.installment_count}" ${isFirst ? 'checked' : ''}>
                        </div>
                    </label>
                `;
                index++;
            });
        });

        html += '</div>';
        this.installmentContainer.innerHTML = html;

        // Event listener'ları yeniden bağla
        this._bindInstallmentEvents();
    },

    _bindInstallmentEvents() {
        const radios = this.installmentContainer.querySelectorAll('input[name="installment"]');
        radios.forEach(radio => {
            radio.addEventListener('change', (ev) => this._onInstallmentChange(ev));
        });
    },
});
