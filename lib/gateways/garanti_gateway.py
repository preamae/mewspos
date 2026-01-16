# -*- coding: utf-8 -*-

from .base_gateway import BaseGateway
from .crypto_utils import CryptoUtils
from .xml_utils import XmlUtils
import logging

_logger = logging.getLogger(__name__)


class GarantiGateway(BaseGateway):
    """Garanti BBVA POS Gateway"""

    def prepare_3d_request(self, order, card):
        """3D Secure form verisi hazırla"""
        config = self.config
        
        # Security Data oluştur (password hash)
        security_data = CryptoUtils.sha1_hash(
            config['password'] + str(config['terminal_id']).zfill(9)
        ).upper()
        
        # Hash oluştur
        hash_data = CryptoUtils.create_3d_hash_garanti(
            terminal_id=str(config['terminal_id']).zfill(9),
            order_id=order['id'],
            amount=self.format_amount(order['amount']),
            success_url=order['success_url'],
            fail_url=order['fail_url'],
            trans_type='sales',
            installment=self.format_installment(order.get('installment', 1)) or '0',
            store_key=config['store_key'],
            security_data=security_data
        )

        form_data = {
            'mode': 'PROD' if not self.test_mode else 'TEST',
            'secure3dsecuritylevel': '3D_PAY',
            'apiversion': 'v0.01',
            'terminalprovuserid': config['username'],
            'terminaluserid': config['username'],
            'terminalmerchantid': config['merchant_id'],
            'terminalid': str(config['terminal_id']).zfill(9),
            'txntype': 'sales',
            'txnamount': self.format_amount(order['amount']),
            'txncurrencycode': self.map_currency(order.get('currency', 'TRY')),
            'txninstallmentcount': self.format_installment(order.get('installment', 1)) or '',
            'orderid': order['id'],
            'successurl': order['success_url'],
            'errorurl': order['fail_url'],
            'customeripaddress': order.get('ip_address', '127.0.0.1'),
            'customeremailaddress': order.get('email', 'test@test.com'),
            'secure3dhash': hash_data,
            'cardnumber': card['number'],
            'cardexpiredatemonth': card['month'].zfill(2),
            'cardexpiredateyear':  card['year'],
            'cardcvv2': card['cvv'],
            'cardholdername': card['name'],
            'lang': order.get('lang', 'tr'),
        }

        return {
            'gateway_url':  config['gateway_3d_url'],
            'method': 'POST',
            'inputs': form_data
        }

    def parse_3d_response(self, response_data):
        """3D yanıtını parse et"""
        md_status = response_data.get('mdstatus', '0')
        
        # Garanti mdStatus değerleri: 
        # 1,2,3,4 = Başarılı
        # 0,5,6,7,8,9 = Başarısız
        
        approved = md_status in ['1', '2', '3', '4']
        
        # İkinci provizyon gerekli mi kontrol et
        if approved and response_data.get('txnstatus') == 'N':
            approved = False
        
        return {
            'approved': approved,
            'order_id': response_data.get('orderid'),
            'auth_code': response_data.get('authcode'),
            'host_ref_num': response_data.get('hostrefnum'),
            'rrn': response_data.get('rrn'),
            'md_status': md_status,
            'eci': response_data.get('eci'),
            'cavv':  response_data.get('cavv'),
            'xid': response_data.get('xid'),
            'error_code': response_data.get('errmsg'),
            'error_message': response_data.get('errmsg'),
            'proc_return_code': response_data.get('procreturncode'),
            'response_code': response_data.get('responsecode'),
            'response_message': response_data.get('responsemessage'),
        }

    def prepare_payment_request(self, order, card):
        """Non-secure ödeme isteği hazırla"""
        config = self.config
        
        # Security Data
        security_data = CryptoUtils.sha1_hash(
            config['password'] + str(config['terminal_id']).zfill(9)
        ).upper()
        
        # Hash Data
        hash_str = (
            f"{order['id']}{str(config['terminal_id']).zfill(9)}"
            f"{card['number']}{self.format_amount(order['amount'])}{security_data}"
        )
        hash_data = CryptoUtils.sha1_hash(hash_str).upper()

        xml_data = {
            'Mode': 'PROD' if not self.test_mode else 'TEST',
            'Version': 'v0.01',
            'Terminal': {
                'ProvUserID': config['username'],
                'UserID': config['username'],
                'ID': str(config['terminal_id']).zfill(9),
                'MerchantID': config['merchant_id'],
            },
            'Customer': {
                'IPAddress': order.get('ip_address', '127.0.0.1'),
                'EmailAddress': order.get('email', 'test@test.com'),
            },
            'Card': {
                'Number': card['number'],
                'ExpireDate': f"{card['month']}{card['year']}",
                'CVV2': card['cvv'],
            },
            'Order': {
                'OrderID':  order['id'],
                'GroupID': '',
            },
            'Transaction': {
                'Type': 'sales',
                'InstallmentCnt': self.format_installment(order.get('installment', 1)) or '',
                'Amount': self.format_amount(order['amount']),
                'CurrencyCode': self.map_currency(order.get('currency', 'TRY')),
                'CardholderPresentCode': '0',
                'MotoInd': 'N',
                'Description': '',
                'OriginalRetrefNum': '',
            },
        }

        xml_string = XmlUtils.dict_to_xml({'GVPSRequest': xml_data}, root_name='GVPSRequest')

        return {
            'url': config['payment_api_url'],
            'data': xml_string,
            'headers': {'Content-Type': 'application/xml'}
        }

    def parse_payment_response(self, response):
        """Ödeme yanıtını parse et"""
        xml_response = response.text
        parsed = XmlUtils.xml_to_dict(xml_response)
        
        if 'GVPSResponse' in parsed:
            data = parsed['GVPSResponse']
            transaction = data.get('Transaction', {})
            
            response_code = transaction.get('Response', {}).get('Code', '')
            approved = response_code == '00'
            
            return {
                'approved': approved,
                'order_id': data.get('Order', {}).get('OrderID'),
                'auth_code': transaction.get('AuthCode'),
                'host_ref_num': transaction.get('RetrefNum'),
                'rrn': transaction.get('RRN'),
                'error_code': response_code,
                'error_message': transaction.get('Response', {}).get('Message'),
                'proc_return_code': transaction.get('RetrefNum'),
            }
        
        return {'approved': False, 'error_message': 'Geçersiz yanıt formatı'}

    def prepare_cancel_request(self, order):
        """İptal isteği hazırla"""
        config = self.config
        
        security_data = CryptoUtils.sha1_hash(
            config['password'] + str(config['terminal_id']).zfill(9)
        ).upper()

        xml_data = {
            'Mode': 'PROD' if not self.test_mode else 'TEST',
            'Version': 'v0.01',
            'Terminal': {
                'ProvUserID': config['username'],
                'UserID':  config['username'],
                'ID': str(config['terminal_id']).zfill(9),
                'MerchantID': config['merchant_id'],
            },
            'Customer': {
                'IPAddress': order.get('ip_address', '127.0.0.1'),
                'EmailAddress': order.get('email', 'test@test.com'),
            },
            'Order': {
                'OrderID': order['id'],
            },
            'Transaction': {
                'Type': 'void',
                'Amount': self.format_amount(order['amount']),
                'CurrencyCode': self.map_currency(order.get('currency', 'TRY')),
                'OriginalRetrefNum': order.get('host_ref_num', ''),
            },
        }

        xml_string = XmlUtils.dict_to_xml({'GVPSRequest': xml_data}, root_name='GVPSRequest')

        return {
            'url': config['payment_api_url'],
            'data': xml_string,
            'headers': {'Content-Type':  'application/xml'}
        }

    def prepare_refund_request(self, order, amount=None):
        """İade isteği hazırla"""
        config = self.config
        refund_amount = amount if amount else order['amount']
        
        security_data = CryptoUtils.sha1_hash(
            config['password'] + str(config['terminal_id']).zfill(9)
        ).upper()

        xml_data = {
            'Mode': 'PROD' if not self.test_mode else 'TEST',
            'Version': 'v0.01',
            'Terminal': {
                'ProvUserID':  config['username'],
                'UserID': config['username'],
                'ID': str(config['terminal_id']).zfill(9),
                'MerchantID': config['merchant_id'],
            },
            'Customer': {
                'IPAddress':  order.get('ip_address', '127.0.0.1'),
                'EmailAddress': order.get('email', 'test@test.com'),
            },
            'Order': {
                'OrderID': order['id'],
            },
            'Transaction':  {
                'Type': 'refund',
                'Amount':  self.format_amount(refund_amount),
                'CurrencyCode':  self.map_currency(order.get('currency', 'TRY')),
                'OriginalRetrefNum': order.get('host_ref_num', ''),
            },
        }

        xml_string = XmlUtils.dict_to_xml({'GVPSRequest': xml_data}, root_name='GVPSRequest')

        return {
            'url': config['payment_api_url'],
            'data': xml_string,
            'headers': {'Content-Type': 'application/xml'}
        }