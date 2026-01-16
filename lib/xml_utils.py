# -*- coding: utf-8 -*-

from lxml import etree
import logging

_logger = logging.getLogger(__name__)


class XmlUtils:
    """XML işleme yardımcı sınıfı"""

    @staticmethod
    def dict_to_xml(data, root_name='root'):
        """Dictionary'yi XML'e çevir"""
        root = etree.Element(root_name)
        XmlUtils._build_xml(root, data)
        return etree.tostring(root, encoding='utf-8', xml_declaration=True, pretty_print=True).decode('utf-8')

    @staticmethod
    def _build_xml(parent, data):
        """Recursive XML oluşturucu"""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list):
                    for item in value:
                        element = etree.SubElement(parent, key)
                        XmlUtils._build_xml(element, item)
                elif isinstance(value, dict):
                    element = etree.SubElement(parent, key)
                    XmlUtils._build_xml(element, value)
                else: 
                    element = etree.SubElement(parent, key)
                    element.text = str(value) if value is not None else ''
        else:
            parent.text = str(data) if data is not None else ''

    @staticmethod
    def xml_to_dict(xml_string):
        """XML'i dictionary'ye çevir"""
        try:
            root = etree.fromstring(xml_string.encode('utf-8'))
            return XmlUtils._parse_xml_element(root)
        except Exception as e:
            _logger.error(f"XML parse hatası: {str(e)}")
            return {}

    @staticmethod
    def _parse_xml_element(element):
        """XML element'ini parse et"""
        result = {}
        
        # Attributes
        if element.attrib:
            result['@attributes'] = dict(element.attrib)
        
        # Text content
        if element.text and element.text.strip():
            if len(element) == 0:
                return element.text.strip()
            result['#text'] = element.text.strip()
        
        # Child elements
        for child in element: 
            child_data = XmlUtils._parse_xml_element(child)
            
            if child.tag in result:
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_data)
            else:
                result[child.tag] = child_data
        
        return result

    @staticmethod
    def create_soap_envelope(body_content, namespace=None):
        """SOAP envelope oluştur"""
        SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"
        
        envelope = etree.Element(
            "{%s}Envelope" % SOAP_ENV,
            nsmap={'soapenv': SOAP_ENV}
        )
        
        body = etree.SubElement(envelope, "{%s}Body" % SOAP_ENV)
        
        if namespace:
            body_elem = etree.SubElement(body, body_content, nsmap={'ns': namespace})
        else:
            body.append(etree.fromstring(body_content))
        
        return etree.tostring(envelope, encoding='utf-8', xml_declaration=True).decode('utf-8')

    @staticmethod
    def parse_soap_response(xml_string):
        """SOAP response'u parse et"""
        try: 
            root = etree.fromstring(xml_string.encode('utf-8'))
            
            # SOAP Body'yi bul
            namespaces = {
                'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
                'soap12': 'http://www.w3.org/2003/05/soap-envelope'
            }
            
            body = root.find('.//soap:Body', namespaces)
            if body is None:
                body = root.find('.//soap12:Body', namespaces)
            
            if body is not None:
                # İlk child element'i al
                for child in body:
                    return XmlUtils._parse_xml_element(child)
            
            return XmlUtils._parse_xml_element(root)
        except Exception as e:
            _logger.error(f"SOAP response parse hatası: {str(e)}")
            return {}