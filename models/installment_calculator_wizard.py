# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class InstallmentCalculatorWizard(models.TransientModel):
    """Taksit hesaplama sihirbazı"""
    _name = 'mews.pos.installment.calculator.wizard'
    _description = 'Taksit Hesaplama Sihirbazı'

    amount = fields.Float(string='Tutar', digits=(12, 2), required=True, default=1000.0)
    bank_id = fields.Many2one('mews.pos.bank', string='Banka', domain=[('active', '=', True)])
    category_id = fields.Many2one('product.category', string='Ürün Kategorisi')
    result_html = fields.Html(string='Sonuç', compute='_compute_result_html')

    @api.depends('amount', 'bank_id', 'category_id')
    def _compute_result_html(self):
        for wizard in self:
            if not wizard.amount:
                wizard.result_html = '<p class="text-muted">Lütfen bir tutar giriniz.</p>'
                continue

            html = '<div class="table-responsive">'
            banks = wizard.bank_id if wizard.bank_id else self.env['mews.pos.bank'].search([('active', '=', True)])
            
            for bank in banks: 
                configs = bank.installment_config_ids.filtered(
                    lambda c: c.active and c.min_amount <= wizard.amount
                )
                
                if not configs:
                    continue

                max_installment = 36
                if wizard.category_id:
                    restriction = bank.category_restriction_ids.filtered(
                        lambda r: r.category_id.id == wizard.category_id.id
                    )
                    if restriction:
                        if not restriction[0].installment_allowed:
                            continue
                        max_installment = restriction[0].max_installment

                html += f'''
                    <h5 class="mt-3">{bank.name}</h5>
                    <table class="table table-sm table-striped">
                        <thead>
                            <tr>
                                <th>Taksit</th>
                                <th class="text-end">Taksit Tutarı</th>
                                <th class="text-end">Toplam Tutar</th>
                                <th class="text-end">Faiz</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>Tek Çekim</td>
                                <td class="text-end">{wizard.amount:.2f} TL</td>
                                <td class="text-end">{wizard.amount:.2f} TL</td>
                                <td class="text-end">-</td>
                            </tr>
                '''

                for config in configs.sorted(key=lambda c: c.installment_count):
                    if config.installment_count > max_installment:
                        continue
                        
                    result = config.calculate_installment(wizard.amount)
                    campaign_badge = '<span class="badge bg-success ms-1">Kampanya</span>' if result['is_campaign'] else ''
                    
                    html += f'''
                        <tr class="{'table-success' if result['is_campaign'] else ''}">
                            <td>{result['installment_count']} Taksit {campaign_badge}</td>
                            <td class="text-end">{result['installment_amount']:.2f} TL</td>
                            <td class="text-end">{result['total_amount']:.2f} TL</td>
                            <td class="text-end">{result['interest_rate']:.2f}%</td>
                        </tr>
                    '''

                html += '</tbody></table>'

            html += '</div>'
            wizard.result_html = html