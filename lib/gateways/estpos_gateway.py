# -*- coding: utf-8 -*-

import random
import logging

_logger = logging.getLogger(__name__)


class EstPosGateway:
    """EstPos/EstV3Pos Gateway (Akbank, İşbank, TEB, Şekerbank, Finansbank)"""

    def __init__(self, config):
        from odoo.addons.mews_pos.lib.crypto_utils import CryptoUtils
        from odoo.addons.mews_pos.lib.xml_utils import XmlUtils
        
        self.config = config
        self.timeout = 30
        self.test_mode = config.get('environment') == 'test'
        self.CryptoUtils = CryptoUtils
        self.XmlUtils = XmlUtils

    def prepare_3d_request(self, order, card):
        """3D Secure form verisi hazırla"""
        config = self.config
        rnd = str(random.randint(100000, 999999))
        
        # Hash oluştur
        hash_str = self.CryptoUtils.create_3d_hash_estpos(
            client_id=config['client_id'],
            order_id=order['id'],
            amount=self.format_amount(order['amount']),
            ok_url=order['success_url'],
            fail_url=order['fail_url'],
            trans_type='Auth',
            installment=self.format_installment(order.get('installment', 1)),
            rnd=rnd,
            store_key=config['store_key'],
            hash_algorithm='sha512'
        )

        form_data = {
            'clientid': config['client_id'],
            'storetype': '3d_pay',
            'hash': hash_str,
            'hashAlgorithm': 'ver3',
            'lang': order.get('lang', 'tr'),
            'TranType': 'Auth',
            'currency': self.map_currency(order.get('currency', 'TRY')),
            'oid': order['id'],
            'amount': self.format_amount(order['amount']),
            'okUrl': order['success_url'],
            'failUrl': order['fail_url'],
            'rnd': rnd,
            'pan': card['number'],
            'Ecom_Payment_Card_ExpDate_Year': card['year'],
            'Ecom_Payment_Card_ExpDate_Month': card['month'],
            'cv2': card['cvv'],
            'cardHolderName': card['name'],
        }

        if order.get('installment', 1) > 1:
            form_data['taksit'] = str(order['installment'])

        return {
            'gateway_url': config['gateway_3d_url'],
            'method': 'POST',
            'inputs': form_data
        }

    def parse_3d_response(self, response_data):
        """3D yanıtını parse et"""
        md_status = response_data.get('mdStatus', '0')
        approved = md_status in ['1', '2', '3', '4']
        
        return {
            'approved': approved,
            'order_id': response_data.get('oid'),
            'auth_code': response_data.get('AuthCode'),
            'host_ref_num': response_data.get('HostRefNum'),
            'proc_return_code': response_data.get('ProcReturnCode'),
            'md_status': md_status,
            'eci': response_data.get('eci'),
            'cavv': response_data.get('cavv'),
            'xid': response_data.get('xid'),
            'error_code': response_data.get('ErrCode'),
            'error_message': response_data.get('ErrMsg') or response_data.get('mdErrorMsg'),
            'response':  response_data.get('Response'),
        }

    def prepare_payment_request(self, order, card):
        """Non-secure ödeme isteği hazırla"""
        config = self.config
        
        xml_data = {
            'Name': config['username'],
            'Password': config['password'],
            'ClientId': config['client_id'],
            'Type': 'Auth',
            'IPAddress': order.get('ip_address', '127.0.0.1'),
            'Email': order.get('email', ''),
            'OrderId': order['id'],
            'Total': self.format_amount(order['amount']),
            'Currency': self.map_currency(order.get('currency', 'TRY')),
            'Taksit': self.format_installment(order.get('installment', 1)),
            'Number': card['number'],
            'Expires': f"{card['month']}/{card['year']}",
            'Cvv2Val': card['cvv'],
        }

        xml_string = self.XmlUtils.dict_to_xml({'CC5Request': xml_data}, root_name='CC5Request')

        return {
            'url':  config['payment_api_url'],
            'data': {'DATA': xml_string},
            'headers': {'Content-Type': 'application/x-www-form-urlencoded'}
        }

    def parse_payment_response(self, response):
        """Ödeme yanıtını parse et"""
        xml_response = response.text
        parsed = self.XmlUtils.xml_to_dict(xml_response)
        
        if 'CC5Response' in parsed: 
            data = parsed['CC5Response']
            proc_return_code = data.get('ProcReturnCode', '')
            approved = proc_return_code == '00'
            
            return {
                'approved': approved,
                'order_id': data.get('OrderId'),
                'auth_code': data.get('AuthCode'),
                'host_ref_num': data.get('HostRefNum'),
                'proc_return_code': proc_return_code,
                'error_code': data.get('ErrCode'),
                'error_message': data.get('ErrMsg'),
                'response': data.get('Response'),
            }
        
        return {'approved': False, 'error_message': 'Geçersiz yanıt formatı'}

    def prepare_cancel_request(self, order):
        """İptal isteği hazırla"""
        config = self.config
        
        xml_data = {
            'Name': config['username'],
            'Password': config['password'],
            'ClientId': config['client_id'],
            'Type': 'Void',
            'OrderId': order['id'],
        }

        xml_string = self.XmlUtils.dict_to_xml({'CC5Request': xml_data}, root_name='CC5Request')

        return {
            'url': config['payment_api_url'],
            'data': {'DATA': xml_string},
            'headers': {'Content-Type': 'application/x-www-form-urlencoded'}
        }

    def prepare_refund_request(self, order, amount=None):
        """İade isteği hazırla"""
        config = self.config
        refund_amount = amount if amount else order['amount']
        
        xml_data = {
            'Name':  config['username'],
            'Password': config['password'],
            'ClientId': config['client_id'],
            'Type': 'Credit',
            'OrderId': order['id'],
            'Total': self.format_amount(refund_amount),
            'Currency': self.map_currency(order.get('currency', 'TRY')),
        }

        xml_string = self.XmlUtils.dict_to_xml({'CC5Request': xml_data}, root_name='CC5Request')

        return {
            'url': config['payment_api_url'],
            'data': {'DATA': xml_string},
            'headers': {'Content-Type': 'application/x-www-form-urlencoded'}
        }

    def make_request(self, url, data, headers=None, method='POST'):
        """HTTP isteği gönder"""
        import requests
        
        try:
            _logger.info(f"Gateway isteği:  {url}")
            
            if headers is None:
                headers = {'Content-Type': 'application/x-www-form-urlencoded'}

            if method == 'POST':
                response = requests.post(url, data=data, headers=headers, timeout=self.timeout)
            else:
                response = requests.get(url, params=data, headers=headers, timeout=self.timeout)

            response.raise_for_status()
            return response

        except requests.exceptions.Timeout:
            _logger.error("Gateway timeout")
            raise Exception("İstek zaman aşımına uğradı")

        except requests.exceptions.RequestException as e:
            _logger.error(f"Gateway isteği hatası: {str(e)}")
            raise Exception(f"İstek hatası: {str(e)}")

    def format_amount(self, amount, include_decimal=True):
        """Tutarı gateway formatına çevir"""
        if include_decimal:
            return str(int(amount * 100))
        else:
            return f"{amount:.2f}"

    def format_installment(self, installment):
        """Taksit sayısını formata çevir"""
        return str(installment) if installment > 1 else ''

    def map_currency(self, currency):
        """Para birimi kodunu map et"""
        currency_map = {
            'TRY': '949',
            'USD': '840',
            'EUR': '978',
            'GBP': '826',
        }
        return currency_map.get(currency, '949')

    def normalize_response(self, raw_response):
        """Yanıtı standart formata çevir"""
        return {
            'success': raw_response.get('approved', False),
            'status': 'approved' if raw_response.get('approved') else 'declined',
            'order_id':  raw_response.get('order_id'),
            'transaction_id': raw_response.get('transaction_id'),
            'auth_code': raw_response.get('auth_code'),
            'host_ref_num': raw_response.get('host_ref_num'),
            'rrn': raw_response.get('rrn'),
            'error_code': raw_response.get('error_code'),
            'error_message': raw_response.get('error_message'),
            'md_status': raw_response.get('md_status'),
            'eci': raw_response.get('eci'),
            'cavv': raw_response.get('cavv'),
            'xid':  raw_response.get('xid'),
            'raw_response': raw_response,
        }