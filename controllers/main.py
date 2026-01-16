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
                # Örneğin bankalarda "bin_prefix" gibi bir alan olduğunu varsayıyoruz.
                bank = (
                    request.env['mews.pos.bank']
                    .sudo()
                    .search([('bin_prefix', '=', bin_number[:6])], limit=1)
                )

            # c) Hâlâ banka yoksa: tüm bankalar üzerinden demo hesaplama
            if not bank:
                _logger.info("Mews POS - Bank not found, using demo banks")

                banks = [
                    {
                        'id': 1,
                        'name': 'Yapı Kredi Bankası',
                        'code': 'yapikredi',
                    },
                    {
                        'id': 2,
                        'name': 'İş Bankası',
                        'code': 'isbank',
                    },
                ]
            else:
                banks = [{
                    'id': bank.id,
                    'name': bank.name,
                    'code': bank.code or (bank.short_name if hasattr(bank, 'short_name') else ''),
                }]

            test_installments = []

            # ============================
            # 2) Her banka için taksit hesaplama
            # ============================
            for b in banks:
                bank_id_val = b['id']
                bank_name = b['name']
                bank_code = b['code']

                # İstersen burada gerçek modelden (installment_config_ids) okuyabilirsin.
                # Şimdilik senin verdiğin sabit senaryoları kullanıyoruz.

                if bank_id_val == 1:  # Yapı Kredi
                    installments = [
                        {
                            'installment_count': 1,
                            'installment_amount': round(amount, 2),
                            'total_amount': round(amount, 2),
                            'interest_rate': 0.0,
                            'is_campaign': False,
                        },
                        {
                            'installment_count': 2,
                            'installment_amount': round(amount / 2, 2),
                            'total_amount': round(amount, 2),
                            'interest_rate': 0.0,
                            'is_campaign': True,
                        },
                        {
                            'installment_count': 3,
                            'installment_amount': round(amount * 1.03 / 3, 2),
                            'total_amount': round(amount * 1.03, 2),
                            'interest_rate': 3.0,
                            'is_campaign': True,
                        },
                        {
                            'installment_count': 6,
                            'installment_amount': round(amount * 1.06 / 6, 2),
                            'total_amount': round(amount * 1.06, 2),
                            'interest_rate': 6.0,
                            'is_campaign': False,
                        },
                    ]
                elif bank_id_val == 2:  # İş Bankası
                    installments = [
                        {
                            'installment_count': 1,
                            'installment_amount': round(amount, 2),
                            'total_amount': round(amount, 2),
                            'interest_rate': 0.0,
                            'is_campaign': False,
                        },
                        {
                            'installment_count': 2,
                            'installment_amount': round(amount / 2, 2),
                            'total_amount': round(amount, 2),
                            'interest_rate': 0.0,
                            'is_campaign': True,
                        },
                        {
                            'installment_count': 4,
                            'installment_amount': round(amount * 1.04 / 4, 2),
                            'total_amount': round(amount * 1.04, 2),
                            'interest_rate': 4.0,
                            'is_campaign': False,
                        },
                    ]
                else:
                    # Diğer bankalar için sadece tek çekim örneği
                    installments = [
                        {
                            'installment_count': 1,
                            'installment_amount': round(amount, 2),
                            'total_amount': round(amount, 2),
                            'interest_rate': 0.0,
                            'is_campaign': False,
                        }
                    ]

                test_installments.append({
                    'bank': {
                        'id': bank_id_val,
                        'name': bank_name,
                        'code': bank_code,
                    },
                    'installments': installments,
                })

            response_data = {
                'jsonrpc': '2.0',
                'id': None,
                'result': {
                    'success': True,
                    'installments': test_installments,
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