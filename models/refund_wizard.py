# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import json


class MewsPosRefundWizard(models.TransientModel):
    """İade işlemi sihirbazı"""
    _name = 'mews.pos.refund.wizard'
    _description = 'Mews POS İade Sihirbazı'

    transaction_id = fields.Many2one('mews.pos.transaction', string='İşlem', required=True, readonly=True)
    max_amount = fields.Float(string='Maksimum İade Tutarı', digits=(12, 2), readonly=True)
    amount = fields.Float(string='İade Tutarı', digits=(12, 2), required=True)
    is_full_refund = fields.Boolean(string='Tam İade', default=True)
    notes = fields.Text(string='Notlar')

    @api.onchange('is_full_refund')
    def _onchange_is_full_refund(self):
        if self.is_full_refund:
            self.amount = self.max_amount

    @api.constrains('amount')
    def _check_amount(self):
        for wizard in self:
            if wizard.amount <= 0:
                raise ValidationError(_('İade tutarı 0\'dan büyük olmalıdır! '))
            if wizard.amount > wizard.max_amount:
                raise ValidationError(_('İade tutarı maksimum tutarı (%.2f) aşamaz!') % wizard.max_amount)

    def action_refund(self):
        self.ensure_one()
        transaction = self.transaction_id
        
        from odoo.addons.mews_pos.services.payment_gateway_service import PaymentGatewayService
        gateway = PaymentGatewayService(self.env)
        
        refund = self.env['mews.pos.refund'].create({
            'transaction_id': transaction.id,
            'amount': self.amount,
            'notes': self.notes,
            'state': 'pending',
        })
        
        try:
            result = gateway.process_refund(transaction, self.amount)
            
            if result.get('success'):
                refund.write({
                    'state': 'success',
                    'refund_ref': result.get('data', {}).get('refund_ref'),
                    'response_data': json.dumps(result, ensure_ascii=False),
                    'processed_at': fields.Datetime.now(),
                })
                
                new_refunded = transaction.refunded_amount + self.amount
                if new_refunded >= transaction.total_amount:
                    transaction.write({
                        'state': 'refunded',
                        'refunded_amount': new_refunded,
                    })
                else:
                    transaction.write({
                        'state': 'partial_refund',
                        'refunded_amount': new_refunded,
                    })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Başarılı'),
                        'message': _('İade işlemi başarıyla tamamlandı.'),
                        'type': 'success',
                        'next':  {'type': 'ir.actions.act_window_close'},
                    }
                }
            else: 
                refund.write({
                    'state': 'failed',
                    'error_message':  result.get('error', 'Bilinmeyen hata'),
                    'response_data': json.dumps(result, ensure_ascii=False),
                })
                
                raise UserError(_('İade işlemi başarısız:  %s') % result.get('error', 'Bilinmeyen hata'))
                
        except Exception as e: 
            refund.write({
                'state': 'failed',
                'error_message': str(e),
            })
            raise