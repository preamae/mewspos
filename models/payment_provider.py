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
    
    # Default/Main bank for fallback
    mews_default_bank_id = fields.Many2one(
        'mews.pos.bank',
        string='Ana Banka',
        domain="[('id', 'in', mews_bank_ids)]",
        help='Taksit sunulmayan kartlar için kullanılacak ana banka. '
             'BIN tanımlı olmayan kartlarda tek çekim ödemesi bu banka ile yapılır.'
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

    @api.onchange('mews_bank_ids')
    def _onchange_mews_bank_ids(self):
        """Ensure default bank is in the selected banks"""
        if self.mews_default_bank_id and self.mews_default_bank_id not in self.mews_bank_ids:
            self.mews_default_bank_id = False
    
    def _get_compatible_providers(self, *args, **kwargs):
        """Include mews_pos in compatible providers"""
        providers = super()._get_compatible_providers(*args, **kwargs)
        return providers
