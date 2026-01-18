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
        const formData = this.el?.dataset || {};
        this.originalAmount = parseFloat(formData.amount) || 0;
        this.amount = this.originalAmount;
        this.categoryIds = formData.categoryIds || "";
        this.currentBin = null;

        // Taksit seçimi için gizli alanı kontrol et
        this._ensureInstallmentHiddenField();

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
        const cardPreview = this.el?.querySelector(".card_number_preview");
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
            // Orijinal tutara geri dön
            this._updateTotalAmount(this.originalAmount, 1);
        }
    },

    _onCardNameInput(ev) {
        const value = ev.currentTarget.value || "İsim Soyisim";
        const namePreview = this.el?.querySelector(".fullname_preview");
        if (namePreview) {
            namePreview.textContent = value;
        }
    },

    _onExpireChange() {
        const monthSelect = this.el?.querySelector("#card_month");
        const yearSelect = this.el?.querySelector("#card_year");
        const monthPreview = this.el?.querySelector(".date_month_preview");
        const yearPreview = this.el?.querySelector(".date_year_preview");

        if (monthSelect && yearSelect && monthPreview && yearPreview) {
            const month = monthSelect.value || "AA";
            const year = yearSelect.value || "YY";
            monthPreview.textContent = month;
            yearPreview.textContent = year.toString().slice(-2);
        }
    },

    _ensureInstallmentHiddenField() {
        if (!this.el) return;

        let hiddenInput = this.el.querySelector("input[name='installment_selected']");
        if (!hiddenInput) {
            hiddenInput = document.createElement("input");
            hiddenInput.type = "hidden";
            hiddenInput.name = "installment_selected";
            hiddenInput.value = "1"; // Varsayılan tek çekim
            this.el.appendChild(hiddenInput);
        }

        // Toplam tutar için gizli alan
        let totalInput = this.el.querySelector("input[name='mews_total_amount']");
        if (!totalInput) {
            totalInput = document.createElement("input");
            totalInput.type = "hidden";
            totalInput.name = "mews_total_amount";
            totalInput.value = this.originalAmount;
            this.el.appendChild(totalInput);
        }
    },

    _onInstallmentChange(ev) {
        const selectedValue = ev.currentTarget.value;
        const selectedInstallmentCount = parseInt(selectedValue) || 1;

        // Taksit bilgilerini al
        const listItem = ev.currentTarget.closest('label.list-group-item');
        let totalAmount = this.originalAmount;

        if (listItem) {
            // Taksit detaylarını al
            const amountText = listItem.querySelector('.text-muted.small')?.textContent || '';
            const matches = amountText.match(/(\d+\.?\d*)\s*₺\s*x\s*(\d+)\s*=\s*(\d+\.?\d*)/);

            if (matches && matches.length >= 4) {
                totalAmount = parseFloat(matches[3]);
            }
        }

        // Gizli alanları güncelle
        if (this.el) {
            let hiddenInput = this.el.querySelector("input[name='installment_selected']");
            if (!hiddenInput) {
                hiddenInput = document.createElement("input");
                hiddenInput.type = "hidden";
                hiddenInput.name = "installment_selected";
                this.el.appendChild(hiddenInput);
            }
            hiddenInput.value = selectedValue;

            // Toplam tutar gizli alanını güncelle
            let totalInput = this.el.querySelector("input[name='mews_total_amount']");
            if (!totalInput) {
                totalInput = document.createElement("input");
                totalInput.type = "hidden";
                totalInput.name = "mews_total_amount";
                this.el.appendChild(totalInput);
            }
            totalInput.value = totalAmount;
        }

        // Toplam tutarı görsel olarak güncelle
        this._updateTotalAmount(totalAmount, selectedInstallmentCount);

        // Odoo ödeme formundaki tutarı güncelle
        this._updateOdooPaymentAmount(totalAmount);
    },

    _updateTotalAmount(totalAmount, installmentCount) {
        // Odoo'nun standart sınıflarını kullanarak toplam tutarı bul
        const updateAmountInElement = (element) => {
            if (element && element.textContent) {
                // Eğer element zaten tutar içeriyorsa güncelle
                if (element.textContent.match(/\d+\.?\d*\s*₺/)) {
                    element.textContent = `${totalAmount.toFixed(2)} ₺`;
                    return true;
                }
            }
            return false;
        };

        // Odoo 19'daki yaygın toplam tutar elementlerini güncelle
        const selectors = [
            '.oe_order_total .oe_currency_value',
            '.oe_website_sale .oe_currency_value:last-child',
            '.order_total .oe_currency_value',
            '.total .amount',
            'td.text-end:last-child .oe_currency_value',
            '#total .oe_currency_value',
            '#order_total .oe_currency_value',
            '.amount_total',
            'span.oe_currency_value:last-child'
        ];

        selectors.forEach(selector => {
            const elements = document.querySelectorAll(selector);
            elements.forEach(el => updateAmountInElement(el));
        });

        // Tablo satırlarında "Toplam" veya "Total" yazan hücreleri bul
        const tableCells = document.querySelectorAll('td');
        tableCells.forEach(td => {
            const text = td.textContent?.trim().toLowerCase() || '';
            if (text === 'toplam' || text === 'total') {
                const nextTd = td.nextElementSibling;
                if (nextTd && nextTd.tagName === 'TD') {
                    updateAmountInElement(nextTd);
                }
            }
        });

        // Özel bir toplam gösterim alanı ekle
        let customDisplay = document.getElementById('mews_installment_total_display');
        if (!customDisplay && this.installmentContainer?.parentNode) {
            customDisplay = document.createElement('div');
            customDisplay.id = 'mews_installment_total_display';
            customDisplay.className = 'alert alert-info mt-2';
            this.installmentContainer.parentNode.insertAdjacentElement('afterend', customDisplay);
        }

        if (customDisplay && installmentCount > 1) {
            const diffAmount = totalAmount - this.originalAmount;
            const diffText = diffAmount > 0 ?
                `(+${diffAmount.toFixed(2)} ₺ faiz)` :
                `(${diffAmount.toFixed(2)} ₺ faiz)`;

            customDisplay.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <strong>Seçilen Taksit: ${installmentCount} Taksit</strong><br>
                        <small class="text-muted">${diffText}</small>
                    </div>
                    <div class="text-end">
                        <strong>${totalAmount.toFixed(2)} ₺</strong><br>
                        <small class="text-muted">Toplam Ödenecek</small>
                    </div>
                </div>
            `;
            customDisplay.style.display = 'block';
        } else if (customDisplay) {
            customDisplay.style.display = 'none';
        }
    },

    _updateOdooPaymentAmount(totalAmount) {
        // Odoo'nun payment formundaki amount alanını bul
        const paymentForm = document.querySelector('form[name="o_payment_submit_form"], form.o_payment_form');
        if (paymentForm) {
            // amount adında bir input arıyoruz
            let amountInput = paymentForm.querySelector('input[name="amount"]');

            if (amountInput) {
                amountInput.value = totalAmount;
            } else {
                // Eğer yoksa oluştur (dikkatli ol - Odoo'nun form yapısını bozabilir)
                // Sadece gerçekten gerekliyse oluştur
                amountInput = document.createElement('input');
                amountInput.type = 'hidden';
                amountInput.name = 'amount';
                amountInput.value = totalAmount;
                paymentForm.appendChild(amountInput);
            }

            // Ayrıca taksit bilgisini de gönder
            let installmentInput = paymentForm.querySelector('input[name="installment_count"]');
            if (!installmentInput) {
                installmentInput = document.createElement('input');
                installmentInput.type = 'hidden';
                installmentInput.name = 'installment_count';
                paymentForm.appendChild(installmentInput);
            }

            const selectedInstallment = this.el?.querySelector('input[name="installment"]:checked');
            installmentInput.value = selectedInstallment ? selectedInstallment.value : '1';
        }
    },

    _clearInstallments() {
        if (!this.installmentContainer) {
            return;
        }

        this.installmentContainer.classList.remove("opacity-50");
        this.installmentContainer.innerHTML = `
            <p class="text-muted mb-0">
                İlk 6 haneyi girdikten sonra taksit seçenekleri yüklenecektir.
            </p>
        `;

        // Taksit toplam gösterimini gizle
        const customDisplay = document.getElementById('mews_installment_total_display');
        if (customDisplay) {
            customDisplay.style.display = 'none';
        }

        // Tutarı orijinaline döndür
        this._updateTotalAmount(this.originalAmount, 1);
        this._updateOdooPaymentAmount(this.originalAmount);
    },

    async _loadInstallments(bin) {
        if (!this.installmentContainer || !this.amount) {
            return;
        }

        // Yükleme durumunu göster
        this.installmentContainer.classList.add("opacity-50");
        this.installmentContainer.innerHTML = '<span class="text-muted">Taksit seçenekleri yükleniyor...</span>';

        try {
            const result = await rpc("/mews_pos/get_payment_installments", {
                amount: this.amount,
                bin_number: bin,
                category_ids: this.categoryIds,
            });

            // Sunucudan gelen veriyi işle
            this._renderInstallments(result);
        } catch (error) {
            console.error("Mews POS installments error:", error);
            this.installmentContainer.classList.remove("opacity-50");
            this.installmentContainer.innerHTML = `
                <span class="text-danger">
                    Taksit seçenekleri alınırken hata oluştu. Lütfen tekrar deneyin.
                </span>
            `;
        }
    },

    _renderInstallments(response) {
        if (!this.installmentContainer) {
            return;
        }

        // Sunucudan gelen yapıyı kontrol et
        // Eğer success: false ise hata göster
        if (response && response.success === false) {
            this.installmentContainer.classList.remove("opacity-50");
            this.installmentContainer.innerHTML = `
                <span class="text-warning">
                    ${response.message || "Bu kart için taksit seçeneği bulunamadı."}
                </span>
            `;
            return;
        }

        // Yanıt verisini al
        const responseData = response.result || response;

        // Eğer boşsa veya installments yoksa
        if (!responseData || !responseData.installments || responseData.installments.length === 0) {
            this.installmentContainer.classList.remove("opacity-50");
            this.installmentContainer.innerHTML = `
                <span class="text-muted">
                    Bu kart için taksit seçeneği bulunamadı.
                </span>
            `;
            return;
        }

        // BIN'e özel bankaları göster
        const wrapper = document.createElement("div");
        wrapper.className = "list-group";

        let index = 0;

        // Her banka için
        responseData.installments.forEach((bankData) => {
            const bankName = bankData.bank && bankData.bank.name ? bankData.bank.name : "Banka";

            // Sadece bu BIN'e uygun taksitler varsa göster
            if (!bankData.installments || bankData.installments.length === 0) {
                return;
            }

            const bankHeader = document.createElement("h6");
            bankHeader.className = "text-muted px-3 mb-2 mt-2";
            bankHeader.textContent = bankName;
            wrapper.appendChild(bankHeader);

            // Bu bankanın taksit seçeneklerini göster
            bankData.installments.forEach((inst) => {
                const id = `mews_inst_${index}`;
                const isFirst = index === 0;
                const label = inst.installment_count === 1
                    ? "Tek Çekim"
                    : `${inst.installment_count} Taksit`;

                const badge = inst.is_campaign
                    ? '<span class="badge bg-success ms-2">Kampanya</span>'
                    : "";

                // Tutarları güvenli şekilde al
                const monthly = inst.installment_amount || inst.amount_per || 0;
                const total = inst.total_amount || (monthly * inst.installment_count);

                const itemHTML = `
                    <label class="list-group-item list-group-item-action d-flex justify-content-between align-items-center"
                           data-total-amount="${total.toFixed(2)}"
                           data-installment-count="${inst.installment_count}"
                           data-monthly-amount="${monthly.toFixed(2)}">
                        <div>
                            <div class="fw-semibold">${label}${badge}</div>
                            <div class="text-muted small installment-details">
                                ${monthly.toFixed(2)} ₺ x ${inst.installment_count} = 
                                ${total.toFixed(2)} ₺
                            </div>
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
                `;

                const tempDiv = document.createElement("div");
                tempDiv.innerHTML = itemHTML;
                wrapper.appendChild(tempDiv.firstElementChild);
                index++;
            });
        });

        // Eğer hiç taksit seçeneği yoksa
        if (index === 0) {
            this.installmentContainer.classList.remove("opacity-50");
            this.installmentContainer.innerHTML = `
                <span class="text-muted">
                    Bu kart için taksit seçeneği bulunamadı.
                </span>
            `;
            return;
        }

        this.installmentContainer.classList.remove("opacity-50");
        this.installmentContainer.innerHTML = "";
        this.installmentContainer.appendChild(wrapper);

        // İlk seçeneği seçili yap ve tetikle
        const firstRadio = this.installmentContainer.querySelector("input[name='installment']");
        if (firstRadio) {
            firstRadio.checked = true;
            // İlk taksitin change event'ini tetikle
            setTimeout(() => {
                this._onInstallmentChange({ currentTarget: firstRadio });
            }, 100);
        }
    },
});
