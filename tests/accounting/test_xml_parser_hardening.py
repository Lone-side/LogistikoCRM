from django.test import SimpleTestCase

from accounting.gsis_client import GSISClient, GSISError
from mydata.client import MyDataAPIError, MyDataClient


MALICIOUS_XML = """<?xml version="1.0"?>
<!DOCTYPE root [<!ENTITY payload "EXPANDED">]>
<root><value>&payload;</value></root>
"""


class ExternalXmlParserHardeningTest(SimpleTestCase):
    def test_gsis_rejects_dtd_and_entities(self):
        client = GSISClient('000000000', 'test-user', 'test-password')
        with self.assertRaises(GSISError):
            client._parse_response(MALICIOUS_XML)

    def test_mydata_vat_parser_rejects_dtd_and_entities(self):
        client = MyDataClient('test-user', 'test-key', is_sandbox=True)
        with self.assertRaises(MyDataAPIError):
            client._parse_vat_info_response(MALICIOUS_XML)

    def test_legacy_mydata_parser_does_not_expand_entities(self):
        client = MyDataClient('test-user', 'test-key', is_sandbox=True)
        self.assertEqual(client.parse_invoice_response(MALICIOUS_XML), [])
