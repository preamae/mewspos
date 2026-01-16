# -*- coding: utf-8 -*-

from .base_gateway import BaseGateway
from ..crypto_utils import CryptoUtils
import logging
from zeep import Client
from zeep.transports import Transport
from requests import Session

_logger = logging.getLogger(__name__)


class KuveytPosGateway(BaseGateway):
    """Kuveyt Türk POS Gateway (SOAP - Zeep kullanarak)"""

    def __init__(self, config):
        super().__init__(config)
        self.wsdl_url = config.get('wsdl_url', 'https://boatest.kuveytturk.com.tr/boa.virtualpos.services/Home/ThreeDModelProvisionGate?wsdl')
        
        # Zeep client oluştur
        session = Session()
        session.verify = True
        transport = Transport(session=session, timeout=self.timeout)
        self.client = Client(self.wsdl_url, transport=transport)

    def prepare_3d_request(self, order, card):
        """3D Secure isteği hazırla"""
        config = self.config
        
        # Hash oluştur
        hash_data = (
            f"{config['merchant_id']}{order['id']}"
            f"{self.format_amount(order['amount'], False)}"
            f"{order['success_url']}{order['fail_url']}"
            f"{config['username']}{config['password']}"
        )
        
        hash_value = CryptoUtils.sha256_hash(hash_data).upper()

        form_data = {
            'MerchantId': config['merchant_id'],
            'CustomerId': config['client_id'],
            'UserName': config['username'],
            'CardNumber': card['number'],
            'CardExpireDateYear': card['year'],
            'CardExpireDateMonth': card['month'],
            'CardCVV2': card['cvv'],
            'CardHolderName': card['name'],
            'OrderId': order['id'],
            'Amount': self.format_amount(order['amount'], False),
            'Currency': self.map_currency(order.get('currency', 'TRY')),
            'InstallmentCount': str(order.get('installment', 0)),
            'OkUrl': order['success_url'],
            'FailUrl': order['fail_url'],
            'HashData': hash_value,
            'MerchantOrderId': order['id'],
            'TransactionType': 'Sale',
        }

        return {
            'gateway_url': config['gateway_3d_url'],
            'method': 'POST',
            'inputs': form_data
        }

    def parse_3d_response(self, response_data):
        """3D yanıtını parse et (SOAP response)"""
        try:
            # SOAP servisini çağır
            md_status = response_data.get('MD Status', '0')
            
            if md_status == '1':
                # 3D doğrulama başarılı, provizyon al
                result = self.client.service.GetResult(
                    MerchantId=self.config['merchant_id'],
                    CustomerId=self.config['client_id'],
                    UserName=self.config['username'],
                    Password=self.config['password'],
                    MD=response_data.get('MD'),
                )
                
                approved = result.ResponseCode == '00'
                
                return {
                    'approved': approved,
                    'order_id': response_data.get('OrderId'),
                    'auth_code':  result.AuthCode if approved else None,
                    'host_ref_num': result.ProvisionNumber if approved else None,
                    'rrn': result.RRN if approved else None,
                    'md_status': md_status,
                    'error_code': result.ResponseCode,
                    'error_message': result.ResponseMessage,
                }
            else:
                return {
                    'approved': False,
                    'order_id': response_data.get('OrderId'),
                    'md_status': md_status,
                    'error_code': response_data.get('mdErrorMsg'),
                    'error_message': response_data.get('ErrMsg'),
                }
                
        except Exception as e: 
            _logger.error(f"Kuveyt SOAP hatası: {str(e)}")
            return {
                'approved': False,
                'error_message': f"SOAP hatası: {str(e)}"
            }

    def prepare_payment_request(self, order, card):
        """Non-secure ödeme isteği hazırla (SOAP)"""
        try:
            result = self.client.service.Sale(
                MerchantId=self.config['merchant_id'],
                CustomerId=self.config['client_id'],
                UserName=self.config['username'],
                Password=self.config['password'],
                CardNumber=card['number'],
                CardExpireDateYear=card['year'],
                CardExpireDateMonth=card['month'],
                CardCVV2=card['cvv'],
                CardHolderName=card['name'],
                OrderId=order['id'],
                Amount=self.format_amount(order['amount'], False),
                Currency=self.map_currency(order.get('currency', 'TRY')),
                InstallmentCount=str(order.get('installment', 0)),
            )
            
            return {
                'soap_result': result,
                'approved': result.ResponseCode == '00',
            }
            
        except Exception as e: 
            _logger.error(f"Kuveyt SOAP ödeme hatası: {str(e)}")
            return {
                'approved': False,
                'error_message': str(e)
            }

    def parse_payment_response(self, response):
        """SOAP yanıtını parse et"""
        if isinstance(response, dict) and 'soap_result' in response:
            result = response['soap_result']
            approved = result.ResponseCode == '00'
            
            return {
                'approved': approved,
                'order_id': result.OrderId if hasattr(result, 'OrderId') else None,
                'auth_code': result.AuthCode if approved else None,
                'host_ref_num': result.ProvisionNumber if approved else None,
                'rrn': result.RRN if approved else None,
                'error_code': result.ResponseCode,
                'error_message': result.ResponseMessage,
            }
        
        return response

    def prepare_cancel_request(self, order):
        """İptal isteği hazırla (SOAP)"""
        try:
            result = self.client.service.Reverse(
                MerchantId=self.config['merchant_id'],
                CustomerId=self.config['client_id'],
                UserName=self.config['username'],
                Password=self.config['password'],
                OrderId=order['id'],
                ProvisionNumber=order.get('host_ref_num'),
            )
            
            return {
                'soap_result': result,
                'approved': result.ResponseCode == '00',
            }
            
        except Exception as e: 
            _logger.error(f"Kuveyt SOAP iptal hatası: {str(e)}")
            return {
                'approved': False,
                'error_message': str(e)
            }

    def prepare_refund_request(self, order, amount=None):
        """İade isteği hazırla (SOAP)"""
        refund_amount = amount if amount else order['amount']
        
        try:
            result = self.client.service.PartialRefund(
                MerchantId=self.config['merchant_id'],
                CustomerId=self.config['client_id'],
                UserName=self.config['username'],
                Password=self.config['password'],
                OrderId=order['id'],
                Amount=self.format_amount(refund_amount, False),
                ProvisionNumber=order.get('host_ref_num'),
            )
            
            return {
                'soap_result': result,
                'approved': result.ResponseCode == '00',
            }
            
        except Exception as e:
            _logger.error(f"Kuveyt SOAP iade hatası: {str(e)}")
            return {
                'approved': False,
                'error_message': str(e)
            }