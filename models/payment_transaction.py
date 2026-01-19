# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'
    
    # Mews POS specific fields
    mews_bank_id = fields.Many2one('mews.pos.bank', string='Banka', ondelete='restrict')
    mews_installment_count = fields.Integer(string='Taksit Sayısı', default=1)
    mews_transaction_id = fields.Char(string='Mews Transaction ID')
    mews_card_number_masked = fields.Char(string='Kart No (Maskeli)')
    mews_bin_number = fields.Char(string='BIN Numarası', size=6)
    
    def _get_specific_rendering_values(self, processing_values):
        """Override to add Mews POS specific rendering values"""
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'mews_pos':
            return res
        
        # Add Mews POS specific values
        return {
            'api_url': self.provider_id.mews_bank_ids[0].payment_api_url if self.provider_id.mews_bank_ids else '',
            'mews_bank_id': self.mews_bank_id.id if self.mews_bank_id else None,
            'mews_installment_count': self.mews_installment_count,
        }
    
    def _send_payment_request(self):
        """Override to handle Mews POS payment request"""
        if self.provider_code != 'mews_pos':
            return super()._send_payment_request()
        
        _logger.info("Processing Mews POS payment request for transaction %s", self.reference)
        
        # Get bank from BIN or use default
        bank = self.mews_bank_id
        if not bank and self.provider_id.mews_bank_ids:
            bank = self.provider_id.mews_bank_ids[0]
        
        if not bank:
            raise ValidationError(_("No bank configuration found for Mews POS payment."))
        
        # Store bank info
        self.mews_bank_id = bank.id
        
        # Set transaction to pending
        self._set_pending()
        
        # Return redirect URL - this will be handled by the inline form
        # Odoo will use this to redirect to 3D Secure
        return {
            'redirect_form_html': self._get_redirect_form_html(),
        }
    
    def _get_redirect_form_html(self):
        """Generate HTML form for 3D Secure redirect"""
        # This method generates the auto-submit form for 3D Secure
        # The form will be injected by Odoo's payment form JavaScript
        base_url = self.provider_id.get_base_url()
        
        # Use the bank integration to get form data
        from ..models.bank_integration import get_bank_integration
        
        integration = get_bank_integration(self.mews_bank_id)
        if not integration:
            raise ValidationError(_("Bank integration not found for %s") % self.mews_bank_id.name)
        
        order_data = {
            'transaction_id': self.reference,
            'order_id': self.reference,
            'amount': self.amount,
            'installment': self.mews_installment_count,
            'card_number': '',  # Will be filled by inline form
            'card_holder': '',  # Will be filled by inline form
            'card_exp_month': '',  # Will be filled by inline form
            'card_exp_year': '',  # Will be filled by inline form
            'card_cvv': '',  # Will be filled by inline form
            'success_url': f'{base_url}/payment/mews_pos/return',
            'fail_url': f'{base_url}/payment/mews_pos/return',
        }
        
        try:
            form_data = integration.create_payment_form(order_data)
            
            # Generate HTML form
            html = f'''
            <form id="mews_pos_payment_form" action="{form_data.get('redirect_url', '')}" method="{form_data.get('redirect_method', 'POST')}">
            '''
            
            for key, value in form_data.get('form_fields', {}).items():
                html += f'<input type="hidden" name="{key}" value="{value}"/>'
            
            html += '''
            </form>
            <script>
                document.getElementById('mews_pos_payment_form').submit();
            </script>
            '''
            
            return html
        except Exception as e:
            _logger.error("Error creating payment form: %s", str(e))
            raise ValidationError(_("Error creating payment form: %s") % str(e))
    
    def _process_notification_data(self, notification_data):
        """Process the notification data sent by the bank"""
        if self.provider_code != 'mews_pos':
            return super()._process_notification_data(notification_data)
        
        _logger.info("Processing Mews POS notification for transaction %s: %s", self.reference, notification_data)
        
        # Check if payment was successful based on notification data
        # This depends on the bank's response format
        success = notification_data.get('success') or notification_data.get('approved')
        
        if success:
            self._set_done()
        else:
            error_msg = notification_data.get('error_message', _('Payment failed'))
            self._set_error(error_msg)
    
    @api.model
    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Find transaction from notification data"""
        if provider_code != 'mews_pos':
            return super()._get_tx_from_notification_data(provider_code, notification_data)
        
        # Get transaction reference from notification data
        reference = notification_data.get('reference') or notification_data.get('transaction_id') or notification_data.get('order_id')
        
        if not reference:
            raise ValidationError(_("No transaction reference found in notification data"))
        
        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'mews_pos')])
        if not tx:
            raise ValidationError(_("No transaction found with reference %s") % reference)
        
        return tx
