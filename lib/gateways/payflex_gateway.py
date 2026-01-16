# -*- coding: utf-8 -*-

from .base_gateway import BaseGateway
from ..crypto_utils import CryptoUtils
from ..xml_utils import XmlUtils
import logging

_logger = logging.getLogger(__name__)


class PayFlexGateway(BaseGateway):
    """Ziraat & Vakıfbank PayFlex Gateway"""

    def prepare_3d_request(self, order, card):
        """3D Secure form verisi hazırla"""
        config = self.config
        
        # Hash oluştur
        hash_data = self._create_hash(
            merchant_id=config['merchant_id'],
            terminal_id=config['terminal_id'],
            order_id=order['id'],
            amount=order['amount'],
            password=config['password']
        )

        form_data = {
            'MerchantId': config['merchant_id'],
            'TerminalNo': config['terminal_id'],
            'OrderId': order['id'],
            'Amount': self.format_amount(order['amount'], False),
            'Currency': self.map_currency(order.get('currency', 'TRY')),
            'InstallmentCount': str(order.get('installment', 1)),
            'TxnType': 'Sale',
            'SecureType': '3DPay',
            'Lang': order.get('lang', 'tr'),
            'SuccessUrl': order['success_url'],
            'FailUrl': order['fail_url'],
            'Pan': card['number'],
            'ExpiryDate': f"{card['month']}{card['year']}",
            'Cvv':  card['cvv'],
            'CardHolderName': card['name'],
            'HashData': hash_data,
        }

        return {
            'gateway_url': config['gateway_3d_url'],
            'method': 'POST',
            'inputs': form_data
        }

    def parse_3d_response(self, response_data):
        """3D yanıtını parse et"""
        result_code = response_data.get('ResultCode', '')
        response_code = response_data.get('ResponseCode', '')
        
        # ResultCode: Success = başarılı
        # ResponseCode: 00 = başarılı
        approved = (
            result_code == 'Success' and 
            response_code == '00'
        )
        
        return {
            'approved': approved,
            'order_id': response_data.get('OrderId'),
            'auth_code': response_data.get('AuthCode'),
            'host_ref_num': response_data.get('HostRefNum'),
            'rrn': response_data.get('Rrn'),
            'md_status': '1' if approved else '0',
            'eci': response_data.get('Eci'),
            'cavv': response_data.get('Cavv'),
            'error_code': response_code,
            'error_message':  response_data.get('ErrorMessage') or response_data.get('ResultDetail'),
            'result_code': result_code,
        }

    def prepare_payment_request(self, order, card):
        """Non-secure ödeme isteği hazırla"""
        config = self.config
        
        hash_data = self._create_hash(
            merchant_id=config['merchant_id'],
            terminal_id=config['terminal_id'],
            order_id=order['id'],
            amount=order['amount'],
            password=config['password']
        )

        xml_data = {
            'MerchantId': config['merchant_id'],
            'TerminalNo': config['terminal_id'],
            'OrderId': order['id'],
            'Amount': self.format_amount(order['amount'], False),
            'Currency': self.map_currency(order.get('currency', 'TRY')),
            'InstallmentCount': str(order.get('installment', 1)),
            'TxnType': 'Sale',
            'SecureType': 'NonSecure',
            'Pan': card['number'],
            'ExpiryDate': f"{card['month']}{card['year']}",
            'Cvv': card['cvv'],
            'HashData': hash_data,
        }

        xml_string = XmlUtils.dict_to_xml({'PayforRequest': xml_data}, root_name='PayforRequest')

        return {
            'url': config['payment_api_url'],
            'data': xml_string,
            'headers':  {'Content-Type': 'application/xml'}
        }

    def parse_payment_response(self, response):
        """Ödeme yanıtını parse et"""
        xml_response = response.text
        parsed = XmlUtils.xml_to_dict(xml_response)
        
        if 'PayforResponse' in parsed:
            data = parsed['PayforResponse']
            result_code = data.get('ResultCode', '')
            response_code = data.get('ResponseCode', '')
            
            approved = (
                result_code == 'Success' and 
                response_code == '00'
            )
            
            return {
                'approved': approved,
                'order_id': data.get('OrderId'),
                'auth_code': data.get('AuthCode'),
                'host_ref_num': data.get('HostRefNum'),
                'rrn': data.get('Rrn'),
                'error_code': response_code,
                'error_message': data.get('ErrorMessage') or data.get('ResultDetail'),
            }
        
        return {'approved': False, 'error_message': 'Geçersiz yanıt formatı'}

    def _create_hash(self, merchant_id, terminal_id, order_id, amount, password):
        """PayFlex hash oluştur"""
        hash_str = f"{merchant_id}{terminal_id}{order_id}{amount:.2f}{password}"
        return CryptoUtils.sha256_hash(hash_str).upper()

    def prepare_cancel_request(self, order):
        """İptal isteği hazırla"""
        config = self.config
        
        hash_data = self._create_hash(
            merchant_id=config['merchant_id'],
            terminal_id=config['terminal_id'],
            order_id=order['id'],
            amount=order['amount'],
            password=config['password']
        )

        xml_data = {
            'MerchantId': config['merchant_id'],
            'TerminalNo': config['terminal_id'],
            'OrderId': order['id'],
            'TxnType': 'Void',
            'ReferenceTransactionId': order.get('host_ref_num'),
            'HashData': hash_data,
        }

        xml_string = XmlUtils.dict_to_xml({'PayforRequest': xml_data}, root_name='PayforRequest')

        return {
            'url':  config['payment_api_url'],
            'data': xml_string,
            'headers': {'Content-Type': 'application/xml'}
        }

    def prepare_refund_request(self, order, amount=None):
        """İade isteği hazırla"""
        config = self.config
        refund_amount = amount if amount else order['amount']
        
        hash_data = self._create_hash(
            merchant_id=config['merchant_id'],
            terminal_id=config['terminal_id'],
            order_id=order['id'],
            amount=refund_amount,
            password=config['password']
        )

        xml_data = {
            'MerchantId': config['merchant_id'],
            'TerminalNo': config['terminal_id'],
            'OrderId': order['id'],
            'Amount': self.format_amount(refund_amount, False),
            'Currency': self.map_currency(order.get('currency', 'TRY')),
            'TxnType': 'Refund',
            'ReferenceTransactionId': order.get('host_ref_num'),
            'HashData': hash_data,
        }

        xml_string = XmlUtils.dict_to_xml({'PayforRequest': xml_data}, root_name='PayforRequest')

        return {
            'url': config['payment_api_url'],
            'data': xml_string,
            'headers': {'Content-Type': 'application/xml'}
        }