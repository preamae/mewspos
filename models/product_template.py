# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    installment_allowed = fields.Boolean(
        string='Taksit İzni',
        default=True,
        help='Bu ürün için taksitli satış yapılabilir mi?'
    )
    
    max_installment = fields.Integer(
        string='Maksimum Taksit',
        default=0,
        help='0 = Kategori ayarlarını kullan'
    )
    
    min_installment_amount = fields.Float(
        string='Minimum Taksit Tutarı',
        digits=(12, 2),
        default=100.0,
        help='Taksitli satış için minimum tutar'
    )

    def _get_installment_display_data(self):
        """Ürün sayfası için taksit verilerini hazırla"""
        self.ensure_one()
        
        _logger.info(f"Getting installments for product: {self.name}")
        
        if not self.installment_allowed:
            _logger.info("Installment not allowed for this product")
            return []
        
        amount = self.list_price
        if amount < self.min_installment_amount:
            _logger.info(f"Amount {amount} less than min {self.min_installment_amount}")
            return []
        
        result = []
        banks = self.env['mews.pos.bank'].sudo().search([('active', '=', True)], order='sequence')
        
        _logger.info(f"Found {len(banks)} active banks")
        
        for bank in banks:
            configs = bank.installment_config_ids.filtered(
                lambda c: c.active and c.min_amount <= amount
            )
            
            if not configs:
                continue
            
            installments = []
            for config in configs.sorted(key=lambda c: c.installment_count):
                inst_data = config.calculate_installment(amount)
                installments.append(inst_data)
            
            if installments:
                result.append({
                    'bank_id': bank.id,
                    'bank_name': bank.name,
                    'bank_code': bank.code,
                    'color': self._get_bank_color(bank.code),
                    'installments': installments,
                })
        
        _logger.info(f"Returning {len(result)} banks with installments")
        return result
    
    def _get_bank_color(self, bank_code):
        """Banka renk kodları"""
        colors = {
            'akbank': '#f15a29',
            'garanti': '#00a650',
            'yapikredi': '#005eb8',
            'isbank': '#004b93',
        }
        return colors.get(bank_code.lower(), '#6c757d')