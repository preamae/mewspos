# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    mews_transaction_ids = fields.One2many(
        'mews.pos.transaction',
        'order_id',
        string='POS İşlemleri'
    )
    
    mews_selected_bank_id = fields.Many2one(
        'mews.pos.bank',
        string='Seçilen Banka'
    )
    
    mews_installment_count = fields.Integer(
        string='Taksit Sayısı',
        default=1
    )
    
    mews_installment_amount = fields.Float(
        string='Taksit Tutarı',
        digits=(12, 2),
        compute='_compute_installment_amounts'
    )
    
    mews_total_with_interest = fields.Float(
        string='Faizli Toplam',
        digits=(12, 2),
        compute='_compute_installment_amounts'
    )

    @api.depends('amount_total', 'mews_selected_bank_id', 'mews_installment_count')
    def _compute_installment_amounts(self):
        for order in self:
            if order.mews_selected_bank_id and order.mews_installment_count > 1:
                config = order.mews_selected_bank_id.installment_config_ids.filtered(
                    lambda c: c.installment_count == order.mews_installment_count
                )
                if config:
                    result = config[0].calculate_installment(order.amount_total)
                    order.mews_installment_amount = result['installment_amount']
                    order.mews_total_with_interest = result['total_amount']
                else:
                    order.mews_installment_amount = order.amount_total
                    order.mews_total_with_interest = order.amount_total
            else:
                order.mews_installment_amount = order.amount_total
                order.mews_total_with_interest = order.amount_total

    def get_available_installments(self):
        """Sipariş için mevcut taksit seçeneklerini getir"""
        self.ensure_one()
        
        category_ids = self.order_line.mapped('product_id.categ_id').ids
        
        no_installment_products = self.order_line.filtered(
            lambda l: not l.product_id.installment_allowed
        )
        if no_installment_products: 
            return []
        
        # Burada payment.provider yerine direkt bankalardan taksit al
        result = []
        banks = self.env['mews.pos.bank'].search([('active', '=', True)])
        
        for bank in banks: 
            bank_installments = []
            
            configs = bank.installment_config_ids.filtered(
                lambda c: c.active and c.min_amount <= self.amount_total
            )
            
            for config in configs:
                inst_data = config.calculate_installment(self.amount_total)
                inst_data['bank_id'] = bank.id
                inst_data['bank_name'] = bank.name
                inst_data['bank_code'] = bank.code
                
                if category_ids:
                    restrictions = bank.category_restriction_ids.filtered(
                        lambda r: r.category_id.id in category_ids
                    )
                    
                    if restrictions:
                        max_allowed = min(r.max_installment for r in restrictions)
                        if inst_data['installment_count'] > max_allowed:
                            continue
                        
                        blocked = []
                        for r in restrictions: 
                            blocked.extend(r.get_blocked_installment_list())
                        if inst_data['installment_count'] in blocked:
                            continue
                        
                        if not all(r.installment_allowed for r in restrictions):
                            continue
                
                bank_installments.append(inst_data)
            
            if bank_installments:
                result.append({
                    'bank':  {
                        'id': bank.id,
                        'name': bank.name,
                        'code': bank.code,
                    },
                    'installments':  sorted(
                        bank_installments,
                        key=lambda x: x['installment_count']
                    )
                })
        
        return result