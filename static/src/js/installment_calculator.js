// Kart numarası değişikliklerini dinle
function setupCardNumberListener() {
    // Odoo'nun kart numarası input'larını bul (farklı tema/versiyonlar için)
    var cardInputSelectors = [
        'input[name="cc_number"]',
        'input[name="card_number"]',
        'input[data-bind="cardNumber"]',
        '#cc_number',
        '#card_number',
        '.card-number-input',
        'input[placeholder*="kart"]',
        'input[placeholder*="card"]'
    ];
    
    cardInputSelectors.forEach(function(selector) {
        $(document).on('input blur change', selector, function(e) {
            var cardNumber = $(this).val().replace(/\s/g, '');
            if (cardNumber.length >= 6) {
                detectBankFromCard(cardNumber);
            }
        });
    });
}

// Kart numarasından banka tespiti
function detectBankFromCard(cardNumber) {
    var bin = cardNumber.substring(0, 6);
    
    // Banka BIN numaraları
    var bankBins = {
        '450634': { id: 1, name: 'Yapı Kredi', code: 'yapikredi', color: '#005eb8' },
        '454671': { id: 2, name: 'İş Bankası', code: 'isbank', color: '#004b93' },
        '415514': { id: 3, name: 'Garanti BBVA', code: 'garanti', color: '#00a650' },
        '540667': { id: 4, name: 'Akbank', code: 'akbank', color: '#f15a29' },
        '552608': { id: 5, name: 'Maximum', code: 'maximum', color: '#e30613' },
        '453144': { id: 6, name: 'Bonus', code: 'bonus', color: '#ff5a00' },
        '546001': { id: 7, name: 'Axess', code: 'axess', color: '#2a388f' }
    };
    
    var detectedBank = null;
    for (var binPrefix in bankBins) {
        if (bin.startsWith(binPrefix)) {
            detectedBank = bankBins[binPrefix];
            break;
        }
    }
    
    if (detectedBank) {
        console.log('Bank detected:', detectedBank.name);
        showCardInfo(detectedBank, cardNumber);
        loadInstallmentsForBank(detectedBank.id);
    } else {
        console.log('Bank not detected, showing all banks');
        hideCardInfo();
        loadAllInstallments();
    }
}

// Kart bilgilerini göster
function showCardInfo(bank, cardNumber) {
    var formattedCard = cardNumber.replace(/(\d{4})(?=\d)/g, '$1 ');
    var lastFour = cardNumber.substr(-4);
    
    var html = '<div class="card-preview mb-4 p-3 border rounded" style="background: linear-gradient(135deg, ' + bank.color + '20, ' + bank.color + '40); border-color: ' + bank.color + '60;">';
    html += '<div class="d-flex align-items-center">';
    html += '<div class="bank-logo me-3" style="width: 50px; height: 50px; background: ' + bank.color + '; border-radius: 10px; display: flex; align-items: center; justify-content: center;">';
    html += '<span style="color: white; font-weight: bold; font-size: 18px;">' + bank.name.charAt(0) + '</span>';
    html += '</div>';
    html += '<div class="flex-grow-1">';
    html += '<h5 class="mb-1 fw-bold" style="color: ' + bank.color + '">' + bank.name + '</h5>';
    html += '<div class="text-muted">';
    html += '<div class="mb-1"><i class="fa fa-credit-card me-2"></i>•••• •••• •••• ' + lastFour + '</div>';
    
    // Kart sahibi adı (eğer input'ta varsa)
    var cardHolder = $('input[name="cc_holder_name"]').val() || '';
    if (cardHolder) {
        html += '<div><i class="fa fa-user me-2"></i>' + cardHolder + '</div>';
    }
    
    html += '</div>';
    html += '</div>';
    html += '</div>';
    html += '</div>';
    
    // Eski kart önizlemesini kaldır ve yenisini ekle
    $('.card-preview').remove();
    $('#o_payment_installments_container').before(html);
}

function hideCardInfo() {
    $('.card-preview').remove();
}

// Sadece belirli bir banka için taksit yükle
function loadInstallmentsForBank(bankId) {
    var $container = $('#o_payment_installments_container');
    var amount = parseFloat($container.data('amount')) || 0;
    
    $container.find('#installment_options').html(
        '<div class="text-center py-4">' +
        '<i class="fa fa-spinner fa-spin fa-2x text-primary"></i>' +
        '<div class="mt-2">Taksit seçenekleri yükleniyor...</div>' +
        '</div>'
    );
    
    fetch('/mews_pos/get_payment_installments?amount=' + amount + '&bank_id=' + bankId)
        .then(function(response) { return response.json(); })
        .then(function(data) {
            var result = data.result || data;
            if (result.success && result.installments) {
                renderInstallments(result.installments, amount);
            } else {
                showTestDataForBank(bankId);
            }
        })
        .catch(function(error) {
            console.error('Error:', error);
            showTestDataForBank(bankId);
        });
}

// Tüm bankalar için taksit yükle
function loadAllInstallments() {
    var $container = $('#o_payment_installments_container');
    var amount = parseFloat($container.data('amount')) || 0;
    
    $container.find('#installment_options').html(
        '<div class="text-center py-4">' +
        '<i class="fa fa-spinner fa-spin fa-2x text-primary"></i>' +
        '<div class="mt-2">Taksit seçenekleri yükleniyor...</div>' +
        '</div>'
    );
    
    fetch('/mews_pos/get_payment_installments?amount=' + amount)
        .then(function(response) { return response.json(); })
        .then(function(data) {
            var result = data.result || data;
            if (result.success && result.installments) {
                renderInstallments(result.installments, amount);
            } else {
                showTestData();
            }
        })
        .catch(function(error) {
            console.error('Error:', error);
            showTestData();
        });
}