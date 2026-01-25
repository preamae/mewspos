# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request, Response
from odoo.exceptions import UserError
import logging
import json

_logger = logging.getLogger(__name__)


class MewsPosController(http.Controller):

    @http.route(
        '/mews_pos/get_payment_installments',
        type='json',
        auth='public',
        website=True,
        csrf=False,
        methods=['POST'],
    )
    def get_payment_installments(self, **kwargs):
        """
        Ödeme sayfası için taksit seçeneklerini getirir.

        Parametreler:
            amount: (opsiyonel) Tutar. Gelmezse sepetten alınır.
            bank_id: (opsiyonel) Banka ID'si. Varsa doğrudan o bankaya göre taksit döner.
            bin_number: (opsiyonel) Kartın ilk 6 hanesi. Buna göre banka seçilebilir.
        Dönen format:
            {
              "jsonrpc": "2.0",
              "id": null,
              "result": {
                  "success": true,
                  "installments": [
                      {
                        "bank": {"id": 1, "name": "...", "code": "..."},
                        "installments": [
                            {
                              "installment_count": 1,
                              "installment_amount": 100.0,
                              "total_amount": 100.0,
                              "interest_rate": 0.0,
                              "is_campaign": false
                            },
                            ...
                        ]
                      },
                      ...
                  ],
                  "amount": 250.0,
                  "message": "..."
              }
            }
        """

        try:
            _logger.info("Mews POS - get_payment_installments kwargs: %s", kwargs)

            # HTTP body'den JSON geldiyse onu da dikkate alalım (fetch ile POST için)
            if request.httprequest.method == 'POST':
                try:
                    data = json.loads(request.httprequest.data or b'{}')
                    if isinstance(data, dict) and data.get('params'):
                        kwargs.update(data.get('params'))
                except Exception:
                    # body parse edilemezse sorun etmiyoruz
                    pass

            # Tutar
            amount = float(kwargs.get('amount', 0.0) or 0.0)
            bank_id = kwargs.get('bank_id')
            bin_number = (kwargs.get('bin_number') or '').strip()

            _logger.info(
                "Processing installments - Amount: %s, Bank ID: %s, BIN: %s",
                amount, bank_id, bin_number,
            )

            # Eğer amount 0 ise sepetten al
            if amount <= 0:
                order = request.website.sale_get_order()
                if order:
                    amount = order.amount_total

            # Henüz sipariş / sepet yoksa
            if amount <= 0:
                return {
                    'success': False,
                    'installments': [],
                    'amount': 0.0,
                    'message': 'Tutar bulunamadı',
                }

            # ============================
            # 1) Banka tespiti
            # ============================
            bank = None

            # a) bank_id ile doğrudan
            if bank_id:
                try:
                    bank = request.env['mews.pos.bank'].sudo().browse(int(bank_id))
                    if not bank or not bank.exists():
                        bank = None
                except Exception:
                    bank = None

            # b) bank_id yoksa bin_number ile tespit
            if not bank and bin_number and len(bin_number) >= 6:
                # BIN numarasından bankayı bul
                bin_record = (
                    request.env['mews.pos.bin']
                    .sudo()
                    .search([('bin_number', '=', bin_number[:6]), ('active', '=', True)], limit=1)
                )
                if bin_record and bin_record.bank_id:
                    bank = bin_record.bank_id
                    _logger.info("Bank found from BIN: %s -> %s", bin_number[:6], bank.name)
                else:
                    _logger.info("BIN not found in database: %s, will use default bank", bin_number[:6])

            # c) BIN tanımlı değilse veya banka bulunamadıysa: varsayılan bankayı kullan (tek çekim)
            if not bank:
                _logger.info("No specific bank found, using default bank for single payment")
                # Varsayılan ödeme sağlayıcısından ana bankayı al
                provider = request.env['payment.provider'].sudo().search([
                    ('code', '=', 'mews_pos'),
                    ('state', '=', 'enabled')
                ], limit=1)
                
                # Önce ana banka alanını kontrol et
                if provider and provider.mews_default_bank_id:
                    bank = provider.mews_default_bank_id
                    _logger.info("Using default bank: %s (from mews_default_bank_id)", bank.name)
                elif provider and provider.mews_bank_ids:
                    # Ana banka tanımlı değilse ilk aktif bankayı kullan
                    bank = provider.mews_bank_ids[0]
                    _logger.warning("No default bank configured, using first available bank: %s", bank.name)
                
                # Hâlâ banka yoksa: tüm aktif bankalardan ilkini göster
                if not bank:
                    _logger.warning("No banks found in provider, searching all active banks")
                    banks_to_process = request.env['mews.pos.bank'].sudo().search([('active', '=', True)])
                else:
                    banks_to_process = bank
            else:
                banks_to_process = bank

            result_installments = []

            # ============================
            # 2) Her banka için taksit hesaplama
            # ============================
            # BIN tanımlı değilse sadece tek çekim göster
            bin_not_found = bin_number and len(bin_number) >= 6 and not any(
                b.id == banks_to_process.id if hasattr(banks_to_process, 'id') else b.id in [bp.id for bp in banks_to_process]
                for b in request.env['mews.pos.bin'].sudo().search([('bin_number', '=', bin_number[:6]), ('active', '=', True)])
            )
            
            for bank_rec in banks_to_process:
                # BIN tanımlı değilse sadece tek çekim
                if bin_not_found:
                    installments = [{
                        'installment_count': 1,
                        'installment_amount': round(amount, 2),
                        'total_amount': round(amount, 2),
                        'interest_rate': 0.0,
                        'is_campaign': False,
                    }]
                else:
                    # Bankaya ait aktif taksit yapılandırmalarını getir
                    installment_configs = request.env['mews.pos.installment.config'].sudo().search([
                        ('bank_id', '=', bank_rec.id),
                        ('active', '=', True),
                        ('min_amount', '<=', amount),
                    ], order='installment_count')

                    # Tek çekim yapılandırmasını kontrol et
                    single_payment_config = request.env['mews.pos.installment.config'].sudo().search([
                        ('bank_id', '=', bank_rec.id),
                        ('active', '=', True),
                        ('installment_count', '=', 1),
                    ], limit=1)
                    
                    installments = []
                    
                    # Tek çekim ekle (yoksa)
                    if not single_payment_config:
                        installments.append({
                            'installment_count': 1,
                            'installment_amount': round(amount, 2),
                            'total_amount': round(amount, 2),
                            'interest_rate': 0.0,
                            'is_campaign': False,
                        })
                    else:
                        # Tek çekim yapılandırması varsa onu ekle
                        calc_result = single_payment_config.calculate_installment(amount)
                        installments.append(calc_result)
                    
                    # Diğer taksitleri ekle (tek çekim hariç)
                    for config in installment_configs:
                        if config.installment_count != 1:
                            calc_result = config.calculate_installment(amount)
                            installments.append(calc_result)
                
                # Eğer hiç taksit yoksa, en azından tek çekim ekle
                if not installments:
                    installments.append({
                        'installment_count': 1,
                        'installment_amount': round(amount, 2),
                        'total_amount': round(amount, 2),
                        'interest_rate': 0.0,
                        'is_campaign': False,
                    })

                result_installments.append({
                    'bank': {
                        'id': bank_rec.id,
                        'name': bank_rec.name,
                        'code': bank_rec.code or '',
                    },
                    'installments': installments,
                })

            return {
                'success': True,
                'installments': result_installments,
                'amount': amount,
                'message': 'Taksit seçenekleri başarıyla yüklendi',
            }

        except Exception as e:
            _logger.error("Mews POS - get_payment_installments Error: %s", str(e), exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'installments': [],
            }

    @http.route(
        '/mews_pos/test_installments',
        type='http',
        auth='public',
        website=True,
        csrf=False,
    )
    def test_installments(self, **kwargs):
        """Basit test endpoint (değiştirmene gerek yok ama dursun)."""
        try:
            amount = float(kwargs.get('amount', 252.00))

            test_data = {
                'success': True,
                'message': 'Test endpoint çalışıyor!',
                'amount': amount,
                'installments': [
                    {
                        'bank': {
                            'id': 1,
                            'name': 'Test Bankası',
                            'code': 'testbank',
                        },
                        'installments': [
                            {
                                'installment_count': 1,
                                'installment_amount': round(amount, 2),
                                'total_amount': round(amount, 2),
                                'interest_rate': 0.0,
                                'is_campaign': False,
                            },
                            {
                                'installment_count': 3,
                                'installment_amount': round(amount * 1.03 / 3, 2),
                                'total_amount': round(amount * 1.03, 2),
                                'interest_rate': 3.0,
                                'is_campaign': True,
                            },
                        ],
                    }
                ],
            }

            return Response(
                json.dumps(test_data, ensure_ascii=False),
                content_type='application/json; charset=utf-8',
                status=200,
            )

        except Exception as e:
            return Response(
                json.dumps({'success': False, 'error': str(e)}, ensure_ascii=False),
                content_type='application/json; charset=utf-8',
                status=500,
            )
    
    @http.route(
        '/mews_pos/validate_bank_config',
        type='json',
        auth='public',
        website=True,
        csrf=False,
    )
    def validate_bank_config(self, bin_number=None, **kwargs):
        """
        Validate bank configuration before payment
        Returns error if API credentials or gateway URLs are missing
        """
        try:
            _logger.info("Mews POS - validate_bank_config BIN: %s", bin_number)
            
            # Find bank from BIN
            bank = None
            if bin_number and len(bin_number) >= 6:
                bin_record = (
                    request.env['mews.pos.bin']
                    .sudo()
                    .search([('bin_number', '=', bin_number[:6]), ('active', '=', True)], limit=1)
                )
                if bin_record and bin_record.bank_id:
                    bank = bin_record.bank_id
            
            if not bank:
                return {
                    'success': False,
                    'error': 'Kart numarasına ait banka bulunamadı. Lütfen kart numarasını kontrol edin.',
                }
            
            # Check required fields based on gateway type
            errors = []
            
            if not bank.merchant_id:
                errors.append('Üye İşyeri No (Merchant ID)')
            if not bank.terminal_id:
                errors.append('Terminal No')
            if not bank.username:
                errors.append('Kullanıcı Adı')
            if not bank.password:
                errors.append('Şifre')
            
            # Check gateway URLs based on payment model
            if bank.payment_model in ['3d_secure', '3d_pay']:
                if not bank.gateway_3d_url:
                    errors.append('3D Gateway URL')
            elif bank.payment_model == '3d_host':
                if not bank.gateway_3d_host_url:
                    errors.append('3D Host Gateway URL')
            
            # For most gateways, store_key is required
            if bank.gateway_type != 'tosla' and not bank.store_key:
                errors.append('Store Key / 3D Secure Key')
            
            # Tosla specific validation
            if bank.gateway_type == 'tosla':
                if not bank.client_id:
                    errors.append('Client ID')
                if not bank.payment_api_url:
                    errors.append('Payment API URL')
            
            if errors:
                error_msg = f'{bank.name} bankası için eksik bilgiler:\n' + '\n'.join([f'- {e}' for e in errors])
                return {
                    'success': False,
                    'error': error_msg,
                    'bank_name': bank.name,
                    'missing_fields': errors,
                }
            
            return {
                'success': True,
                'bank_name': bank.name,
                'bank_code': bank.code,
                'gateway_type': bank.gateway_type,
                'payment_model': bank.payment_model,
            }
            
        except Exception as e:
            _logger.error("Mews POS - validate_bank_config Error: %s", str(e), exc_info=True)
            return {
                'success': False,
                'error': f'Banka yapılandırması kontrol edilirken hata oluştu: {str(e)}',
            }
    
    @http.route(
        '/payment/mews_pos/return',
        type='http',
        auth='public',
        website=True,
        csrf=False,
        methods=['GET', 'POST'],
    )
    def mews_pos_return(self, **kwargs):
        """Handle return from bank 3D Secure page"""
        try:
            _logger.info("Mews POS - Return from bank: %s", kwargs)
            
            # Process the notification data
            tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data('mews_pos', kwargs)
            tx_sudo._process_notification_data(kwargs)
            
            # Redirect to payment status page
            return request.redirect('/payment/status')
            
        except Exception as e:
            _logger.error("Mews POS - Return handler Error: %s", str(e), exc_info=True)
            return request.render('mews_pos.payment_error', {
                'error_message': f'Ödeme işlemi sırasında hata oluştu: {str(e)}',
            })
    
    @http.route(
        '/mews_pos/payment_success',
        type='http',
        auth='public',
        website=True,
        csrf=False,
        methods=['GET', 'POST'],
    )
    def payment_success(self, **kwargs):
        """Handle successful payment callback from bank"""
        try:
            _logger.info("Mews POS - payment_success callback: %s", kwargs)
            
            # TODO: Verify payment with bank
            # TODO: Update transaction status
            # TODO: Confirm order
            
            return request.render('mews_pos.payment_success', {})
            
        except Exception as e:
            _logger.error("Mews POS - payment_success Error: %s", str(e), exc_info=True)
            return request.render('mews_pos.payment_error', {
                'error_message': f'Ödeme doğrulama hatası: {str(e)}',
            })
    
    @http.route(
        '/mews_pos/payment_fail',
        type='http',
        auth='public',
        website=True,
        csrf=False,
        methods=['GET', 'POST'],
    )
    def payment_fail(self, **kwargs):
        """Handle failed payment callback from bank"""
        try:
            _logger.info("Mews POS - payment_fail callback: %s", kwargs)
            
            error_message = kwargs.get('errorMessage') or kwargs.get('ErrMsg') or 'Ödeme işlemi başarısız oldu.'
            
            return request.render('mews_pos.payment_error', {
                'error_message': error_message,
            })
            
        except Exception as e:
            _logger.error("Mews POS - payment_fail Error: %s", str(e), exc_info=True)
            return request.render('mews_pos.payment_error', {
                'error_message': f'Bir hata oluştu: {str(e)}',
            })