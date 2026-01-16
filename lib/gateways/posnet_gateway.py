# -*- coding: utf-8 -*-

from .base_gateway import BaseGateway
from ..crypto_utils import CryptoUtils
from ..xml_utils import XmlUtils
import logging
import base64

_logger = logging.getLogger(__name__)


class PosNetGateway(BaseGateway):
    """YapıKredi PosNet Gateway"""

    def prepare_3d_request(self, order, card):
        """3D Secure isteği hazırla"""
        config = self.config
        
        # Önce OOS (3D) request oluştur
        xml_request = {
            'mid': config['merchant_id'],
            'tid': config['terminal_id'],
            'oosRequestData': {
                'posnetid': config['client_id'],
                'XID': order['id'],
                'amount': self.format_amount(order['amount']),
                'currencyCode': self.map_currency(order.get('currency', 'TRY')),
                'installment': self.format_installment(order.get('installment', 1)) or '00',
                'tranType': 'Sale',
                'cardHolderName': card['name'],
                'ccno': card['number'],
                'expDate': f"{card['year']}{card['month']}",
                'cvc': card['cvv'],
            }
        }

        xml_string = XmlUtils.dict_to_xml({'posnetRequest': xml_request}, root_name='posnetRequest')

        # OOS request gönder
        try:
            response = self.make_request(
                config['payment_api_url'],
                {'xmldata': xml_string},
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            parsed_response = XmlUtils.xml_to_dict(response.text)
            
            if 'posnetResponse' in parsed_response:
                oos_response = parsed_response['posnetResponse']
                
                if oos_response.get('approved') == '1':
                    # 3D form data hazırla
                    form_data = {
                        'mid': config['merchant_id'],
                        'posnetID': config['client_id'],
                        'posnetData': oos_response.get('oosRequestDataResponse', {}).get('data1'),
                        'posnetData2': oos_response.get('oosRequestDataResponse', {}).get('data2'),
                        'digest': oos_response.get('oosRequestDataResponse', {}).get('sign'),
                        'merchantReturnURL': order['success_url'],
                        'lang': order.get('lang', 'tr'),
                        'url': '',
                    }
                    
                    return {
                        'gateway_url': config['gateway_3d_url'],
                        'method':  'POST',
                        'inputs': form_data
                    }
                else:
                    raise Exception(f"OOS hatası: {oos_response.get('respText', 'Bilinmeyen hata')}")
            else:
                raise Exception("Geçersiz OOS yanıtı")
                
        except Exception as e: 
            _logger.error(f"PosNet 3D hazırlama hatası: {str(e)}")
            raise

    def parse_3d_response(self, response_data):
        """3D yanıtını parse et"""
        # 3D yanıtı geldikten sonra provizyon al
        config = self.config
        
        # Response verilerini decode et
        merchant_packet = response_data.get('MerchantPacket', '')
        bank_packet = response_data.get('BankPacket', '')
        sign = response_data.get('Sign', '')
        
        # Provizyon isteği gönder
        xml_request = {
            'mid': config['merchant_id'],
            'tid': config['terminal_id'],
            'oosResolveMerchantData': {
                'bankData': bank_packet,
                'merchantData': merchant_packet,
                'sign': sign,
                'mac': self._create_mac(config),
            }
        }

        xml_string = XmlUtils.dict_to_xml({'posnetRequest': xml_request}, root_name='posnetRequest')

        try:
            response = self.make_request(
                config['payment_api_url'],
                {'xmldata': xml_string},
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            parsed = XmlUtils.xml_to_dict(response.text)
            
            if 'posnetResponse' in parsed:
                data = parsed['posnetResponse']
                approved = data.get('approved') == '1'
                
                return {
                    'approved':  approved,
                    'order_id': data.get('oosResolveMerchantDataResponse', {}).get('xid'),
                    'auth_code': data.get('oosResolveMerchantDataResponse', {}).get('authCode'),
                    'host_ref_num': data.get('oosResolveMerchantDataResponse', {}).get('hostlogkey'),
                    'error_code': data.get('respCode'),
                    'error_message': data.get('respText'),
                    'md_status': '1' if approved else '0',
                }
            
            return {'approved': False, 'error_message': 'Geçersiz yanıt'}
            
        except Exception as e:
            _logger.error(f"PosNet 3D provizyon hatası: {str(e)}")
            return {
                'approved': False,
                'error_message': str(e)
            }

    def prepare_payment_request(self, order, card):
        """Non-secure ödeme isteği hazırla"""
        config = self.config
        
        xml_request = {
            'mid': config['merchant_id'],
            'tid': config['terminal_id'],
            'sale': {
                'orderID': order['id'],
                'amount': self.format_amount(order['amount']),
                'currencyCode': self.map_currency(order.get('currency', 'TRY')),
                'installment': self.format_installment(order.get('installment', 1)) or '00',
                'ccno': card['number'],
                'expDate': f"{card['year']}{card['month']}",
                'cvc': card['cvv'],
            }
        }

        xml_string = XmlUtils.dict_to_xml({'posnetRequest': xml_request}, root_name='posnetRequest')

        return {
            'url':  config['payment_api_url'],
            'data': {'xmldata': xml_string},
            'headers': {'Content-Type': 'application/x-www-form-urlencoded'}
        }

    def parse_payment_response(self, response):
        """Ödeme yanıtını parse et"""
        xml_response = response.text
        parsed = XmlUtils.xml_to_dict(xml_response)
        
        if 'posnetResponse' in parsed:
            data = parsed['posnetResponse']
            approved = data.get('approved') == '1'
            
            return {
                'approved': approved,
                'order_id': order.get('id'),
                'auth_code': data.get('authCode'),
                'host_ref_num': data.get('hostlogkey'),
                'error_code': data.get('respCode'),
                'error_message': data.get('respText'),
            }
        
        return {'approved': False, 'error_message': 'Geçersiz yanıt formatı'}

    def _create_mac(self, config):
        """MAC oluştur (PosNet için)"""
        mac_str = f"{config['client_id']};{config['terminal_id']}"
        return CryptoUtils.base64_encode(CryptoUtils.sha256_hash(mac_str))

    def prepare_cancel_request(self, order):
        """İptal isteği hazırla"""
        config = self.config
        
        xml_request = {
            'mid': config['merchant_id'],
            'tid': config['terminal_id'],
            'reverse': {
                'transaction':  'sale',
                'hostLogKey': order.get('host_ref_num'),
                'authCode': order.get('auth_code'),
            }
        }

        xml_string = XmlUtils.dict_to_xml({'posnetRequest':  xml_request}, root_name='posnetRequest')

        return {
            'url': config['payment_api_url'],
            'data': {'xmldata': xml_string},
            'headers': {'Content-Type': 'application/x-www-form-urlencoded'}
        }

    def prepare_refund_request(self, order, amount=None):
        """İade isteği hazırla"""
        config = self.config
        refund_amount = amount if amount else order['amount']
        
        xml_request = {
            'mid': config['merchant_id'],
            'tid': config['terminal_id'],
            'return': {
                'amount': self.format_amount(refund_amount),
                'currencyCode': self.map_currency(order.get('currency', 'TRY')),
                'hostLogKey': order.get('host_ref_num'),
            }
        }

        xml_string = XmlUtils.dict_to_xml({'posnetRequest':  xml_request}, root_name='posnetRequest')

        return {
            'url': config['payment_api_url'],
            'data': {'xmldata': xml_string},
            'headers': {'Content-Type': 'application/x-www-form-urlencoded'}
        }