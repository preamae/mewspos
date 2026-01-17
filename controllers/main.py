# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request, Response
import logging
import json

_logger = logging.getLogger(__name__)


class MewsPosController(http.Controller):

    @http.route(
        '/mews_pos/get_payment_installments',
        type='http',
        auth='public',
        website=True,
        csrf=False,
        methods=['GET', 'POST'],
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
                response_data = {
                    'jsonrpc': '2.0',
                    'id': None,
                    'result': {
                        'success': False,
                        'installments': [],
                        'amount': 0.0,
                        'message': 'Tutar bulunamadı',
                    },
                }
                return Response(
                    json.dumps(response_data, ensure_ascii=False),
                    content_type='application/json; charset=utf-8',
                    status=200,
                )

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

            # c) Hâlâ banka yoksa: tüm aktif bankalardan taksit getir
            if not bank:
                _logger.info("Mews POS - Bank not detected from BIN, loading all active banks")
                banks_to_process = request.env['mews.pos.bank'].sudo().search([('active', '=', True)])
            else:
                banks_to_process = bank

            result_installments = []

            # ============================
            # 2) Her banka için taksit hesaplama
            # ============================
            for bank_rec in banks_to_process:
                # Bankaya ait aktif taksit yapılandırmalarını getir
                installment_configs = request.env['mews.pos.installment.config'].sudo().search([
                    ('bank_id', '=', bank_rec.id),
                    ('active', '=', True),
                    ('min_amount', '<=', amount),
                ], order='installment_count')

                # Tek çekim her zaman olmalı (installment_count=1)
                has_single_payment = any(cfg.installment_count == 1 for cfg in installment_configs)
                
                installments = []
                
                # Tek çekim ekle (yoksa)
                if not has_single_payment:
                    installments.append({
                        'installment_count': 1,
                        'installment_amount': round(amount, 2),
                        'total_amount': round(amount, 2),
                        'interest_rate': 0.0,
                        'is_campaign': False,
                    })
                
                # Yapılandırılmış taksitleri ekle
                for config in installment_configs:
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

            response_data = {
                'jsonrpc': '2.0',
                'id': None,
                'result': {
                    'success': True,
                    'installments': result_installments,
                    'amount': amount,
                    'message': 'Taksit seçenekleri başarıyla yüklendi',
                },
            }

            return Response(
                json.dumps(response_data, ensure_ascii=False),
                content_type='application/json; charset=utf-8',
                status=200,
            )

        except Exception as e:
            _logger.error("Mews POS - get_payment_installments Error: %s", str(e), exc_info=True)
            return Response(
                json.dumps({'success': False, 'error': str(e)}, ensure_ascii=False),
                content_type='application/json; charset=utf-8',
                status=500,
            )

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