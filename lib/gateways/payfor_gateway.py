# -*- coding: utf-8 -*-

from .base_gateway import BaseGateway
from ..crypto_utils import CryptoUtils
import logging
import random

_logger = logging.getLogger(__name__)


class PayForGateway(BaseGateway):
    """QNB Finansbank PayFor Gateway"""

    def prepare_3d_request(self, order, card):
        """3D Secure form verisi hazırla"""
        config = self.config
        rnd = str(random.randint(100000, 999999))
        
        # Hash oluştur
        hash_data = CryptoUtils.create_3d_hash_payfor(
            merchant_id=config['merchant_id'],
            terminal_id=config['terminal_id'],
            total_amount=self.format_amount(order['amount']),
            order_id=order['id'],
            success_url=order['success_url'],
            fail_url=order['fail_url'],
            rnd=rnd,
            store_key=config['store_key']
        )

        form_data = {
            'MbrId': '5',  # 5=Finansbank, 7=Ziraat Katılım
            'MerchantID':  config['merchant_id'],
            'UserCode': config['username'],
            'OrderId': order['id'],
            'Lang': order.get('lang', 'TR'),
            'SecureType': '3DPay',
            'TxnType': 'Auth',
            'InstallmentCount': self.format_installment(order.get('installment', 1)) or '0',
            'Currency': self.map_currency(order.get('currency', 'TRY')),
            'OkUrl': order['success_url'],
            'FailUrl': order['fail_url'],
            'Rnd': rnd,
            'Hash': hash_data,
            'CardNumber': card['number'],
            'ExpireDate': f"{card['month']}{card['year']}",
            'Cvv': card['cvv'],
            'CardHolderName': card['name'],
            'TotalAmount': self.format_amount(order['amount']),
        }

        return {
            'gateway_url': config['gateway_3d_url'],
            'method': 'POST',
            'inputs': form_data
        }

    def parse_3d_response(self, response_data):
        """3D yanıtını parse et"""
        proc_return_code = response_data.get('ProcReturnCode', '')
        md_status = response_data.get('mdStatus', '0')
        
        # mdStatus:  1,2,3,4 = başarılı
        # ProcReturnCode: 00 = başarılı
        approved = (
            md_status in ['1', '2', '3', '4'] and 
            proc_return_code == '00'
        )
        
        return {
            'approved': approved,
            'order_id': response_data.get('OrderId'),
            'auth_code': response_data.get('AuthCode'),
            'host_ref_num': response_data.get('HostRefNum'),
            'rrn': response_data.get('RetrefNum'),
            'md_status': md_status,
            'eci': response_data.get('eci'),
            'cavv': response_data.get('cavv'),
            'error_code': proc_return_code,
            'error_message': response_data.get('ErrMsg'),
            'response':  response_data.get('Response'),
        }

    def prepare_payment_request(self, order, card):
        """Non-secure ödeme isteği hazırla"""
        config = self.config
        
        data = {
            'MbrId': '5',
            'MerchantID':  config['merchant_id'],
            'UserCode': config['username'],
            'UserPass': config['password'],
            'OrderId': order['id'],
            'SecureType': 'NonSecure',
            'TxnType': 'Auth',
            'InstallmentCount': self.format_installment(order.get('installment', 1)) or '0',
            'Currency': self.map_currency(order.get('currency', 'TRY')),
            'CardNumber': card['number'],
            'ExpireDate': f"{card['month']}{card['year']}",
            'Cvv': card['cvv'],
            'CardHolderName': card['name'],
            'TotalAmount': self.format_amount(order['amount']),
        }

        return {
            'url': config['payment_api_url'],
            'data': data,
            'headers': {'Content-Type': 'application/x-www-form-urlencoded'}
        }

    def parse_payment_response(self, response):
        """Ödeme yanıtını parse et"""
        # PayFor genelde URL-encoded response döner
        from urllib.parse import parse_qs
        
        response_data = parse_qs(response.text)
        
        # Liste değerlerini tek değere çevir
        parsed = {k: v[0] if isinstance(v, list) and len(v) > 0 else v 
                  for k, v in response_data.items()}
        
        proc_return_code = parsed.get('ProcReturnCode', '')
        approved = proc_return_code == '00'
        
        return {
            'approved': approved,
            'order_id': parsed.get('OrderId'),
            'auth_code': parsed.get('AuthCode'),
            'host_ref_num': parsed.get('HostRefNum'),
            'rrn': parsed.get('RetrefNum'),
            'error_code': proc_return_code,
            'error_message':  parsed.get('ErrMsg'),
        }

    def prepare_cancel_request(self, order):
        """İptal isteği hazırla"""
        config = self.config
        
        data = {
            'MbrId': '5',
            'MerchantID': config['merchant_id'],
            'UserCode': config['username'],
            'UserPass': config['password'],
            'OrderId': order['id'],
            'SecureType': 'NonSecure',
            'TxnType': 'Void',
            'OrgOrderId': order['id'],
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
            'MbrId': '5',
            'MerchantID': config['merchant_id'],
            'UserCode': config['username'],
            'UserPass':  config['password'],
            'OrderId': order['id'],
            'SecureType': 'NonSecure',
            'TxnType': 'Refund',
            'TotalAmount': self.format_amount(refund_amount),
            'Currency': self.map_currency(order.get('currency', 'TRY')),
            'OrgOrderId': order['id'],
        }

        return {
            'url': config['payment_api_url'],
            'data': data,
            'headers':  {'Content-Type': 'application/x-www-form-urlencoded'}
        }