# -*- coding: utf-8 -*-

import requests
import json
import logging
from odoo import api, models, _
from odoo. exceptions import UserError

_logger = logging. getLogger(__name__)


class PhpGatewayService: 
    """PHP Gateway ile iletişim servisi"""
    
    def __init__(self, env):
        self.env = env
        self.gateway_url = self._get_gateway_url()
        self.timeout = 30
    
    def _get_gateway_url(self):
        """PHP Gateway URL'sini config'den al"""
        return self.env['ir.config_parameter']. sudo().get_param(
            'mews_pos. php_gateway_url',
            default='http://localhost:8080/payment_processor. php'
        )
    
    def _make_request(self, action, data):
        """PHP Gateway'e istek gönder"""
        payload = {
            'action': action,
            **data
        }
        
        try:
            _logger.info(f"PHP Gateway isteği: {action}")
            _logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
            
            response = requests.post(
                self. gateway_url,
                json=payload,
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )
            
            response.raise_for_status()
            result = response.json()
            
            _logger.info(f"PHP Gateway yanıtı: {result. get('success', False)}")
            _logger.debug(f"Response: {json.dumps(result, indent=2)}")
            
            return result
            
        except requests.exceptions. Timeout:
            _logger.error("PHP Gateway timeout hatası")
            raise UserError(_("Ödeme işlemi zaman aşımına uğradı.  Lütfen tekrar deneyiniz."))
            
        except requests. exceptions.ConnectionError:
            _logger. error("PHP Gateway bağlantı hatası")
            raise UserError(_("Ödeme sistemine bağlanılamadı.  Lütfen daha sonra tekrar deneyiniz."))
            
        except requests.exceptions.RequestException as e: 
            _logger.error(f"PHP Gateway istek hatası: {str(e)}")
            raise UserError(_("Ödeme işlemi sırasında bir hata oluştu:  %s") % str(e))
            
        except json.JSONDecodeError: 
            _logger.error("PHP Gateway JSON parse hatası")
            raise UserError(_("Ödeme sisteminden geçersiz yanıt alındı. "))
    
    def create_3d_form(self, transaction, card_data):
        """3D Secure form verisi oluştur"""
        bank = transaction.bank_id
        
        data = {
            'transaction_id': transaction.transaction_id,
            'amount': transaction. total_amount,
            'currency': transaction.currency,
            'installment': transaction.installment_count,
            'success_url': transaction._get_callback_url('success'),
            'fail_url': transaction._get_callback_url('fail'),
            'card':  card_data,
            'bank_config': bank.get_account_config(),
        }
        
        result = self._make_request('create_3d_form', data)
        
        if not result.get('success'):
            raise UserError(_("3D form oluşturulamadı:  %s") % result.get('error', 'Bilinmeyen hata'))
        
        return result. get('data', {})
    
    def process_3d_callback(self, transaction, callback_data):
        """3D Secure callback işle"""
        bank = transaction.bank_id
        
        data = {
            'order_id': transaction. transaction_id,
            'amount': transaction. total_amount,
            'currency': transaction.currency,
            'installment': transaction.installment_count,
            'callback_data': callback_data,
            'bank_config': bank. get_account_config(),
        }
        
        result = self._make_request('process_3d_callback', data)
        
        return result
    
    def process_non_secure_payment(self, transaction, card_data):
        """Non-Secure ödeme işle"""
        bank = transaction.bank_id
        
        data = {
            'transaction_id': transaction. transaction_id,
            'amount': transaction.total_amount,
            'currency':  transaction.currency,
            'installment':  transaction.installment_count,
            'card': card_data,
            'bank_config': bank. get_account_config(),
        }
        
        result = self._make_request('non_secure_payment', data)
        
        return result
    
    def process_cancel(self, transaction):
        """İptal işlemi"""
        bank = transaction.bank_id
        
        data = {
            'order_id': transaction. bank_order_id or transaction.transaction_id,
            'amount': transaction.total_amount,
            'currency': transaction.currency,
            'bank_config': bank. get_account_config(),
        }
        
        result = self._make_request('cancel', data)
        
        return result
    
    def process_refund(self, transaction, amount=None):
        """İade işlemi"""
        bank = transaction.bank_id
        
        data = {
            'order_id': transaction.bank_order_id or transaction.transaction_id,
            'amount':  amount or transaction.total_amount,
            'currency': transaction. currency,
            'bank_config': bank.get_account_config(),
        }
        
        result = self._make_request('refund', data)
        
        return result
    
    def check_status(self, transaction):
        """İşlem durumu sorgula"""
        bank = transaction.bank_id
        
        data = {
            'order_id': transaction.bank_order_id or transaction.transaction_id,
            'bank_config': bank. get_account_config(),
        }
        
        result = self._make_request('check_status', data)
        
        return result