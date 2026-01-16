# -*- coding: utf-8 -*-

from .base_gateway import BaseGateway
from ..crypto_utils import CryptoUtils
import logging
import json
import random

_logger = logging.getLogger(__name__)


class ToslaGateway(BaseGateway):
    """Tosla (Eski AKÖde) POS Gateway"""

    def prepare_3d_request(self, order, card):
        """3D Secure isteği hazırla"""
        config = self.config
        
        # Tosla JSON API kullanır
        request_data = {
            'ApiVersion': '1.0.0',
            'MerchantId': config['merchant_id'],
            'TerminalId':  config['terminal_id'],
            'OrderId': order['id'],
            'Amount': self.format_amount(order['amount'], False),
            'Currency': self.map_currency(order.get('currency', 'TRY')),
            'InstallmentCount': str(order.get('installment', 1)),
            'TransactionType': 'Sale',
            'CardOwner': card['name'],
            'CardNumber':  card['number'],
            'CardExpireMonth': card['month'].zfill(2),
            'CardExpireYear': card['year'],
            'CardCvv': card['cvv'],
            'SuccessUrl': order['success_url'],
            'ErrorUrl': order['fail_url'],
            'SecureType': '3DPay',
            'Language': order.get('lang', 'tr'),
        }
        
        # Hash oluştur
        hash_str = (
            f"{config['merchant_id']}{config['terminal_id']}"
            f"{order['id']}{self.format_amount(order['amount'], False)}"
            f"{config['store_key']}"
        )
        request_data['Hash'] = CryptoUtils.sha256_hash(hash_str).upper()

        return {
            'request_type':  'json',
            'payment_data': request_data,
            'gateway_url': config['gateway_3d_url'],
        }

    def parse_3d_response(self, response_data):
        """3D yanıtını parse et"""
        result_code = response_data.get('ResultCode', '')
        result_status = response_data.get('ResultStatus', '')
        
        # ResultCode: '0000' = başarılı
        # ResultStatus: 'Success' = başarılı
        approved = (
            result_code == '0000' and 
            result_status == 'Success'
        )
        
        return {
            'approved':  approved,
            'order_id': response_data.get('OrderId'),
            'auth_code': response_data.get('AuthCode'),
            'host_ref_num': response_data.get('HostReferenceNumber'),
            'rrn': response_data.get('Rrn'),
            'md_status': '1' if approved else '0',
            'eci': response_data.get('Eci'),
            'cavv': response_data.get('Cavv'),
            'xid': response_data.get('Xid'),
            'error_code': result_code,
            'error_message': response_data.get('ResultMessage'),
            'transaction_id': response_data.get('TransactionId'),
        }

    def prepare_payment_request(self, order, card):
        """Non-secure ödeme isteği hazırla"""
        config = self.config
        
        data = {
            'ApiVersion':  '1.0.0',
            'MerchantId':  config['merchant_id'],
            'TerminalId': config['terminal_id'],
            'OrderId': order['id'],
            'Amount': self.format_amount(order['amount'], False),
            'Currency': self.map_currency(order.get('currency', 'TRY')),
            'InstallmentCount': str(order.get('installment', 1)),
            'TransactionType': 'Sale',
            'CardOwner': card['name'],
            'CardNumber': card['number'],
            'CardExpireMonth': card['month'].zfill(2),
            'CardExpireYear': card['year'],
            'CardCvv': card['cvv'],
            'SecureType': 'NonSecure',
        }
        
        # Hash oluştur
        hash_str = (
            f"{config['merchant_id']}{config['terminal_id']}"
            f"{order['id']}{self.format_amount(order['amount'], False)}"
            f"{config['store_key']}"
        )
        data['Hash'] = CryptoUtils.sha256_hash(hash_str).upper()

        return {
            'url': config['payment_api_url'],
            'data': json.dumps(data),
            'headers': {
                'Content-Type': 'application/json',
            }
        }

    def parse_payment_response(self, response):
        """Ödeme yanıtını parse et"""
        try:
            response_data = response.json()
        except:
            return {'approved': False, 'error_message': 'Geçersiz JSON yanıtı'}
        
        result_code = response_data.get('ResultCode', '')
        result_status = response_data.get('ResultStatus', '')
        
        approved = (
            result_code == '0000' and 
            result_status == 'Success'
        )
        
        return {
            'approved': approved,
            'order_id': response_data.get('OrderId'),
            'auth_code': response_data.get('AuthCode'),
            'host_ref_num': response_data.get('HostReferenceNumber'),
            'rrn':  response_data.get('Rrn'),
            'error_code': result_code,
            'error_message': response_data.get('ResultMessage'),
            'transaction_id': response_data.get('TransactionId'),
        }

    def prepare_cancel_request(self, order):
        """İptal isteği hazırla"""
        config = self.config
        
        data = {
            'ApiVersion':  '1.0.0',
            'MerchantId':  config['merchant_id'],
            'TerminalId': config['terminal_id'],
            'OrderId': order['id'],
            'TransactionType': 'Void',
            'TransactionId': order.get('transaction_id', ''),
        }
        
        # Hash oluştur
        hash_str = (
            f"{config['merchant_id']}{config['terminal_id']}"
            f"{order['id']}{config['store_key']}"
        )
        data['Hash'] = CryptoUtils.sha256_hash(hash_str).upper()

        return {
            'url': config['payment_api_url'],
            'data': json.dumps(data),
            'headers': {
                'Content-Type': 'application/json',
            }
        }

    def prepare_refund_request(self, order, amount=None):
        """İade isteği hazırla"""
        config = self.config
        refund_amount = amount if amount else order['amount']
        
        data = {
            'ApiVersion': '1.0.0',
            'MerchantId': config['merchant_id'],
            'TerminalId': config['terminal_id'],
            'OrderId':  order['id'],
            'Amount': self.format_amount(refund_amount, False),
            'Currency': self.map_currency(order.get('currency', 'TRY')),
            'TransactionType': 'Refund',
            'TransactionId': order.get('transaction_id', ''),
        }
        
        # Hash oluştur
        hash_str = (
            f"{config['merchant_id']}{config['terminal_id']}"
            f"{order['id']}{self.format_amount(refund_amount, False)}"
            f"{config['store_key']}"
        )
        data['Hash'] = CryptoUtils.sha256_hash(hash_str).upper()

        return {
            'url': config['payment_api_url'],
            'data': json.dumps(data),
            'headers': {
                'Content-Type': 'application/json',
            }
        }