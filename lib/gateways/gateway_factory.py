# -*- coding: utf-8 -*-

import logging

_logger = logging.getLogger(__name__)


class GatewayFactory:
    """Gateway factory sınıfı - Doğru gateway'i oluşturur"""
    
    GATEWAY_MAP = {
        'akbank_pos': 'odoo.addons.mews_pos.lib.gateways.akbank_gateway.AkbankGateway',
        'estv3_pos': 'odoo.addons.mews_pos.lib.gateways.estpos_gateway.EstPosGateway',
        'estpos':  'odoo.addons.mews_pos.lib.gateways.estpos_gateway.EstPosGateway',
        'garanti_pos': 'odoo.addons.mews_pos.lib.gateways.garanti_gateway.GarantiGateway',
        'posnet': 'odoo.addons.mews_pos.lib.gateways.posnet_gateway.PosNetGateway',
        'posnet_v1': 'odoo.addons.mews_pos.lib.gateways.posnet_gateway.PosNetGateway',
        'payfor':  'odoo.addons.mews_pos.lib.gateways.payfor_gateway.PayForGateway',
        'payflex_mpi': 'odoo.addons.mews_pos.lib.gateways.payflex_gateway.PayFlexGateway',
        'payflex_common': 'odoo.addons.mews_pos.lib.gateways.payflex_gateway.PayFlexGateway',
        'interpos': 'odoo.addons.mews_pos.lib.gateways.interpos_gateway.InterPosGateway',
        'kuveyt_pos': 'odoo.addons.mews_pos.lib.gateways.kuveyt_gateway.KuveytPosGateway',
        'tosla':  'odoo.addons.mews_pos.lib.gateways.tosla_gateway.ToslaGateway',
        'param_pos': 'odoo.addons.mews_pos.lib.gateways.estpos_gateway.EstPosGateway',
        'vakif_katilim': 'odoo.addons.mews_pos.lib.gateways.payflex_gateway.PayFlexGateway',
    }
    
    @staticmethod
    def create(gateway_type, config):
        """
        Gateway oluştur
        
        Args:
            gateway_type (str): Gateway tipi
            config (dict): Gateway konfigürasyonu
            
        Returns:
            BaseGateway: İlgili gateway instance
        """
        gateway_class_path = GatewayFactory.GATEWAY_MAP.get(gateway_type)
        
        if not gateway_class_path:
            _logger.error(f"Desteklenmeyen gateway tipi: {gateway_type}")
            raise ValueError(f"Desteklenmeyen gateway tipi:  {gateway_type}")
        
        # Dynamic import
        module_path, class_name = gateway_class_path.rsplit('.', 1)
        
        try:
            import importlib
            module = importlib.import_module(module_path)
            gateway_class = getattr(module, class_name)
            
            _logger.info(f"Gateway oluşturuluyor: {gateway_type}")
            return gateway_class(config)
            
        except (ImportError, AttributeError) as e:
            _logger.error(f"Gateway yüklenirken hata: {str(e)}")
            raise ValueError(f"Gateway yüklenemedi: {gateway_type}")
    
    @staticmethod
    def get_supported_gateways():
        """Desteklenen gateway listesini döndür"""
        return list(GatewayFactory.GATEWAY_MAP.keys())
    
    @staticmethod
    def is_supported(gateway_type):
        """Gateway'in desteklenip desteklenmediğini kontrol et"""
        return gateway_type in GatewayFactory.GATEWAY_MAP