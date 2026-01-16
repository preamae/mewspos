# -*- coding: utf-8 -*-

from .base_gateway import BaseGateway
from ..crypto_utils import CryptoUtils
import logging
import json

_logger = logging.getLogger(__name__)


class InterPosGateway(BaseGateway):
    """Denizbank InterPOS Gateway"""

    def prepare_3d_request(self, order, card):
        """3D Secure form verisi hazırla"""
        config = self.config
        
        # Hash oluştur
        hash_str = (
            f"{config['client_id']}{order['id']}"
            f"{self.format_amount(order['amount'], False)}"
            f"{order['success_url']}{order['fail_url']}"
            f"{config['username']}{config['password']}"
        )
        hash_data = CryptoUtils.sha256_hash(hash_str).upper()

        form_data = {
            'ShopCode': config['client_id'],
            'TxnType': 'Auth',
            'SecureType': '3DPay',
            'PurchAmount': self.format_amount(order['amount'], False),
            'Currency': self.map_currency(order.get('currency', 'TRY')),
            'InstallmentCount': str(order.get('installment', 1)) if order.get('installment', 1) > 1 else '',
            'OrderId': order['id'],
            'OkUrl': order['success_url'],
            'FailUrl':  order['fail_url'],
            'Rnd': hash_str[: 10],
            'Hash': hash_data,
            'Lang': order.get('lang', 'tr'),
            'Pan': card['number'],
            'ExpiryDate': f"{card['month']}{card['year']}",
            'Cvv2': card['cvv'],
            'CardHolderName': card['name'],
            'UserCode': config['username'],
        }

        return {
            'gateway_url': config['gateway_3d_url'],
            'method': 'POST',
            'inputs': form_data
        }

    def parse_3d_response(self, response_data):
        """3D yanıtını parse et"""
        proc_return_code = response_data.get('ProcReturnCode', '')
        md_status = response_data.get('TRANSTAT', '')
        
        # TRANSTAT: Success = başarılı
        # ProcReturnCode: 00 = başarılı
        approved = (
            md_status == 'Success' and 
            proc_return_code == '00'
        )
        
        return {
            'approved': approved,
            'order_id': response_data.get('OrderId'),
            'auth_code': response_data.get('AuthCode'),
            'host_ref_num': response_data.get('HostRefNum'),
            'rrn': response_data.get('RetrefNum'),
            'md_status': '1' if approved else '0',
            'error_code': proc_return_code,
            'error_message':  response_data.get('ErrMsg'),
            'transaction_id': response_data.get('TransId'),
        }

    def prepare_payment_request(self, order, card):
        """Non-secure ödeme isteği hazırla"""
        config = self.config
        
        data = {
            'ShopCode': config['client_id'],
            'UserCode': config['username'],
            'UserPass': config['password'],
            'TxnType': 'Auth',
            'SecureType': 'NonSecure',
            'PurchAmount': self.format_amount(order['amount'], False),
            'Currency': self.map_currency(order.get('currency', 'TRY')),
            'InstallmentCount':  str(order.get('installment', 1)) if order.get('installment', 1) > 1 else '',
            'OrderId': order['id'],
            'Pan': card['number'],
            'ExpiryDate':  f"{card['month']}{card['year']}",
            'Cvv2': card['cvv'],
            'MOTO': '0',
        }

        return {
            'url': config['payment_api_url'],
            'data': data,
            'headers': {'Content-Type': 'application/x-www-form-urlencoded'}
        }

    def parse_payment_response(self, response):
        """Ödeme yanıtını parse et"""
        # InterPos genelde JSON veya form-encoded döner
        try:
            response_data = response.json()
        except:
            from urllib.parse import parse_qs
            response_data = parse_qs(response.text)
            response_data = {k: v[0] if isinstance(v, list) and len(v) > 0 else v 
                           for k, v in response_data.items()}
        
        proc_return_code = response_data.get('ProcReturnCode', '')
        approved = proc_return_code == '00'
        
        return {
            'approved': approved,
            'order_id': response_data.get('OrderId'),
            'auth_code': response_data.get('AuthCode'),
            'host_ref_num': response_data.get('HostRefNum'),
            'rrn':  response_data.get('RetrefNum'),
            'error_code': proc_return_code,
            'error_message':  response_data.get('ErrMsg'),
            'transaction_id': response_data.get('TransId'),
        }

    def prepare_cancel_request(self, order):
        """İptal isteği hazırla"""
        config = self.config
        
        data = {
            'ShopCode': config['client_id'],
            'UserCode':  config['username'],
            'UserPass': config['password'],
            'TxnType': 'Void',
            'SecureType': 'NonSecure',
            'OrderId': order['id'],
            'OrgOrderId': order['id'],
            'TransId': order.get('transaction_id', ''),
        }

        return {
            'url': config['payment_api_url'],
            'data': data,
            'headers': {'Content-Type': 'application/x-www-form-urlencoded'}
        }

    def prepare_refund_request(self, order, amount=None):
        """İade isteği hazırla"""
        config = self.config
        refund_amount = amount if amount else order['amount']
        
        data = {
            'ShopCode': config['client_id'],
            'UserCode': config['username'],
            'UserPass':  config['password'],
            'TxnType': 'Refund',
            'SecureType': 'NonSecure',
            'PurchAmount': self.format_amount(refund_amount, False),
            'Currency': self.map_currency(order.get('currency', 'TRY')),
            'OrderId': order['id'],
            'OrgOrderId': order['id'],
            'TransId': order.get('transaction_id', ''),
        }

        return {
            'url': config['payment_api_url'],
            'data':  data,
            'headers': {'Content-Type': 'application/x-www-form-urlencoded'}
        }