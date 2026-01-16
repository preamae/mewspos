# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ProductPublicCategory(models.Model):
    _inherit = 'product.public.category'

    installment_restriction_ids = fields.One2many(
        'mews.pos.category.restriction',
        'category_id',
        string='Taksit Kısıtlamaları'
    )
    
    max_installment_global = fields.Integer(
        string='Genel Maksimum Taksit',
        default=12,
        help='Tüm bankalar için geçerli maksimum taksit sayısı'
    )
    
    installment_allowed = fields.Boolean(
        string='Taksit İzni',
        default=True,
        help='Bu kategori için taksitli satış yapılabilir mi?'
    )
    
    def get_max_installment_for_bank(self, bank_id):
        """Belirli bir banka için maksimum taksit sayısını döndür"""
        self.ensure_one()
        
        if not self.installment_allowed:
            return 1
        
        restriction = self.installment_restriction_ids.filtered(
            lambda r: r.bank_id.id == bank_id
        )
        
        if restriction:
            return restriction[0].max_installment
        
        return self.max_installment_global