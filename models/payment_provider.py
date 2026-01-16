# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    # ✅ ÖNCE CODE SELECTİON'A EKLE
    code = fields.Selection(
        selection_add=[('mews_pos', 'Mews POS')],
        ondelete={'mews_pos': 'cascade'}
    )

    # Mews POS için özel fieldlar
    mews_bank_ids = fields.Many2many(
        'mews.pos.bank',
        'payment_provider_mews_bank_rel',
        'provider_id',
        'bank_id',
        string='Mews POS Bankaları',
        help='Bu ödeme sağlayıcısı için kullanılabilir bankalar'
    )
    
    mews_show_installments = fields.Boolean(
        string='Taksit Seçeneklerini Göster',
        default=True,
        help='Ödeme sayfasında taksit seçeneklerini göster'
    )
    
    mews_default_installment = fields.Integer(
        string='Varsayılan Taksit',
        default=1,
        help='Varsayılan seçili taksit sayısı'
    )
    
    mews_max_installment = fields.Integer(
        string='Maksimum Taksit',
        default=12,
        help='Gösterilecek maksimum taksit sayısı'
    )
    
    mews_min_installment_amount = fields.Float(
        string='Minimum Taksit Tutarı',
        digits=(12, 2),
        default=100.0,
        help='Taksitli ödemeler için minimum sipariş tutarı'
    )

    def _get_compatible_providers(self, *args, **kwargs):
        """Include mews_pos in compatible providers"""
        providers = super()._get_compatible_providers(*args, **kwargs)
        return providers