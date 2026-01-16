# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MewsPosInstallmentConfig(models.Model):
    """Banka bazlı taksit yapılandırması"""
    _name = 'mews.pos.installment.config'
    _description = 'Mews POS Taksit Yapılandırması'
    _order = 'bank_id, installment_count'

    bank_id = fields.Many2one(
        'mews.pos.bank',
        string='Banka',
        required=True,
        ondelete='cascade'
    )
    
    installment_count = fields.Integer(
        string='Taksit Sayısı',
        required=True,
        help='Taksit sayısı (2-12 arası)'
    )
    
    interest_rate = fields.Float(
        string='Faiz Oranı (%)',
        digits=(5, 2),
        default=0.0,
        help='Taksit için uygulanan faiz oranı yüzdesi'
    )
    
    commission_rate = fields.Float(
        string='Komisyon Oranı (%)',
        digits=(5, 2),
        default=0.0,
        help='Bankaya ödenen komisyon oranı'
    )
    
    active = fields.Boolean(string='Aktif', default=True)
    
    min_amount = fields.Float(
        string='Minimum Tutar',
        digits=(12, 2),
        default=0.0,
        help='Bu taksit seçeneği için minimum sipariş tutarı'
    )
    
    campaign_active = fields.Boolean(string='Kampanya Aktif', default=False)
    campaign_rate = fields.Float(
        string='Kampanyalı Faiz Oranı (%)',
        digits=(5, 2),
        default=0.0
    )
    campaign_start_date = fields.Date(string='Kampanya Başlangıç')
    campaign_end_date = fields.Date(string='Kampanya Bitiş')

    _sql_constraints = [
        ('bank_installment_unique', 
         'unique(bank_id, installment_count)', 
         'Her banka için taksit sayısı benzersiz olmalıdır!')
    ]

    @api.constrains('installment_count')
    def _check_installment_count(self):
        for record in self:
            if record.installment_count < 2 or record.installment_count > 36:
                raise ValidationError(_('Taksit sayısı 2 ile 36 arasında olmalıdır!'))

    def get_effective_rate(self):
        self.ensure_one()
        today = fields.Date.today()
        if (self.campaign_active and 
            self.campaign_start_date and 
            self.campaign_end_date and
            self.campaign_start_date <= today <= self.campaign_end_date):
            return self.campaign_rate
        return self.interest_rate

    def calculate_installment(self, amount):
        self.ensure_one()
        rate = self.get_effective_rate()
        
        if rate > 0:
            total_amount = amount * (1 + rate / 100)
        else:
            total_amount = amount
            
        installment_amount = total_amount / self.installment_count
        
        return {
            'installment_count': self.installment_count,
            'installment_amount':  round(installment_amount, 2),
            'total_amount': round(total_amount, 2),
            'interest_rate': rate,
            'original_amount': amount,
            'interest_amount': round(total_amount - amount, 2),
            'is_campaign': self.campaign_active and rate == self.campaign_rate,
        }