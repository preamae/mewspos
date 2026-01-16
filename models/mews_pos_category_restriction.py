# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MewsPosCategoryRestriction(models.Model):
    """Kategori bazlı taksit kısıtlamaları - eCommerce kategorileri için"""
    _name = 'mews.pos.category.restriction'
    _description = 'Mews POS Kategori Taksit Kısıtlaması'
    _order = 'bank_id, category_id'

    bank_id = fields.Many2one(
        'mews.pos.bank',
        string='Banka',
        required=True,
        ondelete='cascade'
    )
    
    category_id = fields.Many2one(
        'product.public.category',  # ✅ DEĞİŞTİ - eCommerce kategorisi
        string='eCommerce Kategorisi',
        required=True,
        ondelete='cascade'
    )
    
    max_installment = fields.Integer(
        string='Maksimum Taksit',
        required=True,
        default=12,
        help='Bu kategori için izin verilen maksimum taksit sayısı'
    )
    
    min_installment = fields.Integer(
        string='Minimum Taksit',
        default=2,
        help='Bu kategori için izin verilen minimum taksit sayısı'
    )
    
    installment_allowed = fields.Boolean(
        string='Taksit İzni',
        default=True,
        help='Bu kategori için taksit seçeneği aktif mi?'
    )
    
    blocked_installments = fields.Char(
        string='Engellenen Taksitler',
        help='Virgülle ayrılmış engellenen taksit sayıları (örn: 3,5,7)'
    )
    
    notes = fields.Text(string='Notlar')

    _sql_constraints = [
        ('bank_category_unique', 
         'unique(bank_id, category_id)', 
         'Her banka-kategori kombinasyonu benzersiz olmalıdır!')
    ]

    @api.constrains('max_installment', 'min_installment')
    def _check_installment_range(self):
        for record in self:
            if record.min_installment > record.max_installment:
                raise ValidationError(
                    _('Minimum taksit, maksimum taksitten büyük olamaz!')
                )

    def get_blocked_installment_list(self):
        self.ensure_one()
        if not self.blocked_installments:
            return []
        try:
            return [int(x.strip()) for x in self.blocked_installments.split(',')]
        except ValueError:
            return []

    def get_allowed_installments(self, available_installments):
        self.ensure_one()
        
        if not self.installment_allowed:
            return []
        
        blocked = self.get_blocked_installment_list()
        allowed = []
        
        for inst in available_installments:
            count = inst.get('installment_count', 0)
            if (self.min_installment <= count <= self.max_installment and 
                count not in blocked):
                allowed.append(inst)
        
        return allowed