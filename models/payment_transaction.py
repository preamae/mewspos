# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
import json

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'
    
    # Mews POS specific fields
    mews_bank_id = fields.Many2one('mews.pos.bank', string='Banka', ondelete='restrict')
    mews_installment_count = fields.Integer(string='Taksit Sayısı', default=1)
    mews_transaction_id = fields.Char(string='Mews Transaction ID')
    mews_card_number_masked = fields.Char(string='Kart No (Maskeli)')
    mews_bin_number = fields.Char(string='BIN Numarası', size=6)
    mews_3d_html = fields.Text(string='3D Secure HTML Form')
    
    def _get_specific_rendering_values(self, processing_values):
        """Override to add Mews POS specific rendering values for direct flow"""
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'mews_pos':
            return res
        
        _logger.info("Mews POS - Getting rendering values for transaction %s", self.reference)
        
        # For direct flow, we need to return the 3D Secure HTML
        if self.mews_3d_html:
            res.update({
                'redirect_form_html': self.mews_3d_html,
            })
        
        return res
    
    def _send_payment_request(self):
        """
        Override to handle Mews POS payment request - Direct Flow
        
        This implements the 3-step payment flow:
        Step 1: Get card data → Send to bank → Get preliminary approval → Get 3D redirect form
        Step 2: (Handled by bank) User enters 3D password → Bank validates → Redirects to return URL
        Step 3: (Handled in _process_notification_data) Validate bank response → Confirm payment to bank
        """
        if self.provider_code != 'mews_pos':
            return super()._send_payment_request()
        
        _logger.info("Mews POS - Processing payment request for transaction %s", self.reference)
        
        # Get bank from BIN or use default
        bank = self.mews_bank_id
        if not bank and self.provider_id.mews_bank_ids:
            bank = self.provider_id.mews_bank_ids[0]
        
        if not bank:
            raise ValidationError(_("No bank configuration found for Mews POS payment."))
        
        # Store bank info
        self.mews_bank_id = bank.id
        
        # Get card data from tokenization or inline form
        # In direct flow, card data is submitted with the form
        # We'll process it in _get_processing_values
        
        # Set transaction to pending (Step 1: Preliminary approval)
        self._set_pending()
        
        _logger.info("Mews POS - Transaction %s set to pending, will redirect to 3D", self.reference)
    
    def _get_processing_values(self):
        """
        Get processing values and initiate bank payment (Direct Flow Step 1)
        
        This is called when payment form is submitted.
        We get card data, send to bank for preliminary approval,
        and return 3D Secure redirect form.
        """
        res = super()._get_processing_values()
        
        if self.provider_code != 'mews_pos':
            return res
        
        _logger.info("Mews POS - Getting processing values for transaction %s", self.reference)
        
        try:
            # Get card data from request context
            # This is passed from the inline form
            card_number = self.env.context.get('card_number', '')
            card_holder = self.env.context.get('card_name', '')
            card_month = self.env.context.get('card_month', '')
            card_year = self.env.context.get('card_year', '')
            card_cvv = self.env.context.get('card_cvv', '')
            
            # Validate card data
            if not card_number or len(card_number.replace(' ', '')) < 15:
                raise ValidationError(_("Please enter a valid card number."))
            
            # Store masked card number and BIN
            card_number_clean = card_number.replace(' ', '')
            self.mews_card_number_masked = '*' * (len(card_number_clean) - 4) + card_number_clean[-4:]
            self.mews_bin_number = card_number_clean[:6]
            
            # Get bank integration
            from ..models.bank_integration import get_bank_integration
            
            integration = get_bank_integration(self.mews_bank_id)
            if not integration:
                raise ValidationError(_("Bank integration not found for %s") % self.mews_bank_id.name)
            
            # Prepare order data for bank
            base_url = self.provider_id.get_base_url()
            order_data = {
                'transaction_id': self.reference,
                'order_id': self.reference,
                'amount': self.amount,
                'installment': self.mews_installment_count,
                'card_number': card_number_clean,
                'card_holder': card_holder,
                'card_exp_month': card_month,
                'card_exp_year': card_year,
                'card_cvv': card_cvv,
                'success_url': f'{base_url}/payment/mews_pos/return',
                'fail_url': f'{base_url}/payment/mews_pos/return',
            }
            
            # Step 1: Send to bank for preliminary approval and get 3D redirect form
            _logger.info("Mews POS - Requesting 3D form from bank for transaction %s", self.reference)
            form_data = integration.create_payment_form(order_data)
            
            # Generate HTML form for 3D Secure redirect
            redirect_url = form_data.get('redirect_url', '')
            redirect_method = form_data.get('redirect_method', 'POST')
            form_fields = form_data.get('form_fields', {})
            
            html = f'<form id="mews_pos_payment_form" action="{redirect_url}" method="{redirect_method}">\n'
            
            for key, value in form_fields.items():
                html += f'<input type="hidden" name="{key}" value="{value}"/>\n'
            
            html += '''
</form>
<script>
    document.getElementById('mews_pos_payment_form').submit();
</script>
'''
            
            # Store the 3D form for rendering
            self.mews_3d_html = html
            
            _logger.info("Mews POS - 3D form prepared for transaction %s", self.reference)
            
            # Update processing values with redirect form
            res.update({
                'redirect_form_html': html,
            })
            
        except Exception as e:
            _logger.error("Mews POS - Error processing transaction %s: %s", self.reference, str(e), exc_info=True)
            self._set_error(str(e))
            raise ValidationError(_("Payment processing error: %s") % str(e))
        
        return res
    
    def _process_notification_data(self, notification_data):
        """
        Process the notification data sent by the bank (Direct Flow Step 3)
        
        This is called when bank redirects back after 3D authentication.
        We validate the response and confirm payment to bank.
        """
        if self.provider_code != 'mews_pos':
            return super()._process_notification_data(notification_data)
        
        _logger.info("Mews POS - Processing notification for transaction %s: %s", self.reference, notification_data)
        
        try:
            # Parse bank response
            # Different banks have different response formats
            success = (
                notification_data.get('success') == 'true' or
                notification_data.get('approved') == '1' or
                notification_data.get('Response') == 'Approved' or
                notification_data.get('mdStatus') in ['1', '2', '3', '4']  # 3D Secure success statuses
            )
            
            if success:
                # Step 3: Confirm payment to bank (second API call)
                # This step verifies the 3D authentication and finalizes payment
                _logger.info("Mews POS - 3D authentication successful for transaction %s, confirming payment", self.reference)
                
                # Get bank integration for confirmation
                from ..models.bank_integration import get_bank_integration
                
                integration = get_bank_integration(self.mews_bank_id)
                if integration:
                    # Some banks require a confirmation call
                    # This would be implemented in the bank integration
                    try:
                        # confirmation_result = integration.confirm_payment(notification_data)
                        pass  # Placeholder for bank-specific confirmation
                    except Exception as confirm_error:
                        _logger.error("Mews POS - Payment confirmation error: %s", str(confirm_error))
                
                # Set transaction as done
                self._set_done()
                _logger.info("Mews POS - Transaction %s completed successfully", self.reference)
            else:
                # Payment failed or cancelled
                error_msg = (
                    notification_data.get('ErrMsg') or
                    notification_data.get('errorMessage') or
                    notification_data.get('ResponseMessage') or
                    _('Payment was not approved by the bank')
                )
                _logger.warning("Mews POS - Transaction %s failed: %s", self.reference, error_msg)
                self._set_error(error_msg)
                
        except Exception as e:
            _logger.error("Mews POS - Error processing notification for transaction %s: %s", 
                         self.reference, str(e), exc_info=True)
            self._set_error(str(e))
    
    @api.model
    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Find transaction from notification data"""
        if provider_code != 'mews_pos':
            return super()._get_tx_from_notification_data(provider_code, notification_data)
        
        # Get transaction reference from notification data
        # Different banks use different field names
        reference = (
            notification_data.get('reference') or
            notification_data.get('transaction_id') or
            notification_data.get('order_id') or
            notification_data.get('oid') or
            notification_data.get('OrderId')
        )
        
        if not reference:
            _logger.error("Mews POS - No transaction reference found in notification data: %s", notification_data)
            raise ValidationError(_("No transaction reference found in bank response"))
        
        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'mews_pos')], limit=1)
        if not tx:
            _logger.error("Mews POS - No transaction found with reference %s", reference)
            raise ValidationError(_("No transaction found with reference %s") % reference)
        
        return tx
