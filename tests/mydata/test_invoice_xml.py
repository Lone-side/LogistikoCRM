# -*- coding: utf-8 -*-
"""
Tests για το mydata/invoice_xml.py — κατασκευή InvoicesDoc XML
και parsing του ResponseDoc της ΑΑΔΕ.
"""
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from mydata.invoice_xml import (
    ICLS_NS,
    INVOICE_NS,
    build_invoices_doc,
    parse_response_doc,
)



NS = {'m': INVOICE_NS}


def find(el, path):
    """Namespace-aware find: 'invoice/issuer' -> 'm:invoice/m:issuer'."""
    return el.find('/'.join(f'm:{p}' for p in path.split('/')), NS)


def findall(el, path):
    return el.findall('/'.join(f'm:{p}' for p in path.split('/')), NS)


def sample_invoice(**overrides):
    inv = {
        'issuer_vat': '123456783',
        'counterpart_vat': '999863881',
        'series': 'Α',
        'aa': '101',
        'issue_date': date(2026, 7, 30),
        'invoice_type': '2.1',
        'lines': [
            {'line_number': 1, 'net_value': Decimal('100.00'),
             'vat_category': 1, 'vat_amount': Decimal('24.00')},
            {'line_number': 2, 'net_value': Decimal('50.00'),
             'vat_category': 2, 'vat_amount': Decimal('6.50')},
        ],
        'total_net': Decimal('150.00'),
        'total_vat': Decimal('30.50'),
        'total_gross': Decimal('180.50'),
    }
    inv.update(overrides)
    return inv


class BuildInvoicesDocTest(SimpleTestCase):
    def _parse(self, xml_text):
        return ET.fromstring(xml_text)

    def test_namespace_and_structure(self):
        root = self._parse(build_invoices_doc([sample_invoice()]))
        self.assertEqual(root.tag, f'{{{INVOICE_NS}}}InvoicesDoc')
        invoice = find(root, 'invoice')
        self.assertIsNotNone(invoice)
        # Σειρά στοιχείων κατά το XSD sequence
        children = [child.tag.split('}', 1)[1] for child in invoice]
        self.assertEqual(children[0], 'issuer')
        self.assertEqual(children[1], 'counterpart')
        self.assertEqual(children[2], 'invoiceHeader')
        self.assertEqual(children[3], 'paymentMethods')
        self.assertEqual(children[-1], 'invoiceSummary')

    def test_header_and_amount_formatting(self):
        root = self._parse(build_invoices_doc([sample_invoice()]))
        invoice = find(root, 'invoice')
        header = find(invoice, 'invoiceHeader')
        self.assertEqual(find(header, 'series').text, 'Α')
        self.assertEqual(find(header, 'aa').text, '101')
        self.assertEqual(find(header, 'issueDate').text, '2026-07-30')
        self.assertEqual(find(header, 'invoiceType').text, '2.1')
        self.assertEqual(find(header, 'currency').text, 'EUR')

        summary = find(invoice, 'invoiceSummary')
        self.assertEqual(find(summary, 'totalNetValue').text, '150.00')
        self.assertEqual(find(summary, 'totalVatAmount').text, '30.50')
        self.assertEqual(find(summary, 'totalGrossValue').text, '180.50')

        details = findall(invoice, 'invoiceDetails')
        self.assertEqual(len(details), 2)
        self.assertEqual(find(details[0], 'netValue').text, '100.00')
        self.assertEqual(find(details[0], 'vatCategory').text, '1')
        self.assertEqual(find(details[1], 'vatAmount').text, '6.50')

    def test_issuer_and_counterpart(self):
        root = self._parse(build_invoices_doc([sample_invoice()]))
        invoice = find(root, 'invoice')
        self.assertEqual(find(invoice, 'issuer/vatNumber').text, '123456783')
        self.assertEqual(find(invoice, 'issuer/country').text, 'GR')
        self.assertEqual(find(invoice, 'counterpart/vatNumber').text, '999863881')

    def test_missing_counterpart_raises(self):
        # Όλοι οι υποστηριζόμενοι τύποι είναι B2B — χωρίς ΑΦΜ αντισυμβαλλόμενου
        # το παραστατικό θα απορριπτόταν από την ΑΑΔΕ, οπότε κόβεται τοπικά
        with self.assertRaises(ValueError):
            build_invoices_doc([sample_invoice(counterpart_vat='')])

    def test_income_classification_per_line_and_summary(self):
        # Τύπος 2.1 (υπηρεσίες) → default category1_3 / E3_561_001
        root = self._parse(build_invoices_doc([sample_invoice()]))
        invoice = find(root, 'invoice')
        details = findall(invoice, 'invoiceDetails')
        icls = {'i': ICLS_NS}
        for d, expected_amount in zip(details, ('100.00', '50.00')):
            cls_el = find(d, 'incomeClassification')
            self.assertIsNotNone(cls_el)
            self.assertEqual(
                cls_el.find('i:classificationCategory', icls).text, 'category1_3'
            )
            self.assertEqual(
                cls_el.find('i:classificationType', icls).text, 'E3_561_001'
            )
            self.assertEqual(cls_el.find('i:amount', icls).text, expected_amount)
        # Συγκεντρωτικά στο summary: ένα ζεύγος, άθροισμα 150.00
        summary = find(invoice, 'invoiceSummary')
        summary_cls = findall(summary, 'incomeClassification')
        self.assertEqual(len(summary_cls), 1)
        self.assertEqual(summary_cls[0].find('i:amount', icls).text, '150.00')

    def test_vat_category_7_requires_exemption(self):
        lines = [{'line_number': 1, 'net_value': Decimal('100.00'),
                  'vat_category': 7, 'vat_amount': Decimal('0.00')}]
        with self.assertRaises(ValueError) as ctx:
            build_invoices_doc([sample_invoice(
                lines=lines, total_net=Decimal('100.00'),
                total_vat=Decimal('0.00'), total_gross=Decimal('100.00'),
            )])
        self.assertIn('εξαίρεσης', str(ctx.exception))

        lines[0]['vat_exemption_category'] = 3
        root = self._parse(build_invoices_doc([sample_invoice(
            lines=lines, total_net=Decimal('100.00'),
            total_vat=Decimal('0.00'), total_gross=Decimal('100.00'),
        )]))
        detail = find(root, 'invoice/invoiceDetails')
        self.assertEqual(find(detail, 'vatExemptionCategory').text, '3')

    def test_credit_5_1_requires_correlated_mark(self):
        with self.assertRaises(ValueError) as ctx:
            build_invoices_doc([sample_invoice(invoice_type='5.1')])
        self.assertIn('συσχετιζόμεν', str(ctx.exception).lower())

        root = self._parse(build_invoices_doc([sample_invoice(
            invoice_type='5.1', correlated_marks=[400000000000001],
        )]))
        header = find(root, 'invoice/invoiceHeader')
        self.assertEqual(find(header, 'correlatedInvoices').text, '400000000000001')

    def test_intra_community_type_requires_foreign_country(self):
        with self.assertRaises(ValueError):
            build_invoices_doc([sample_invoice(invoice_type='1.2')])
        root = self._parse(build_invoices_doc([sample_invoice(
            invoice_type='1.2', counterpart_country='DE',
        )]))
        self.assertEqual(
            find(root, 'invoice/counterpart/country').text, 'DE'
        )

    def test_no_lines_raises(self):
        with self.assertRaises(ValueError):
            build_invoices_doc([sample_invoice(lines=[])])

    def test_empty_list_raises(self):
        with self.assertRaises(ValueError):
            build_invoices_doc([])


RESPONSE_SUCCESS = """<?xml version="1.0" encoding="utf-8"?>
<ResponseDoc xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <response>
    <index>1</index>
    <invoiceUid>ABC123DEF456</invoiceUid>
    <invoiceMark>400001234567890</invoiceMark>
    <statusCode>Success</statusCode>
  </response>
</ResponseDoc>"""

RESPONSE_ERROR = """<?xml version="1.0" encoding="utf-8"?>
<ResponseDoc>
  <response>
    <index>1</index>
    <statusCode>ValidationError</statusCode>
    <errors>
      <error>
        <message>Το ΑΦΜ του εκδότη δεν είναι έγκυρο</message>
        <code>101</code>
      </error>
      <error>
        <message>Λάθος άθροισμα ΦΠΑ</message>
        <code>203</code>
      </error>
    </errors>
  </response>
</ResponseDoc>"""

RESPONSE_CANCEL = """<?xml version="1.0" encoding="utf-8"?>
<ResponseDoc>
  <response>
    <index>1</index>
    <cancellationMark>400009999999999</cancellationMark>
    <statusCode>Success</statusCode>
  </response>
</ResponseDoc>"""


class ParseResponseDocTest(SimpleTestCase):
    def test_success_response(self):
        results = parse_response_doc(RESPONSE_SUCCESS)
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r['status_code'], 'Success')
        self.assertEqual(r['invoice_mark'], 400001234567890)
        self.assertEqual(r['invoice_uid'], 'ABC123DEF456')
        self.assertEqual(r['errors'], [])

    def test_error_response(self):
        r = parse_response_doc(RESPONSE_ERROR)[0]
        self.assertEqual(r['status_code'], 'ValidationError')
        self.assertIsNone(r['invoice_mark'])
        self.assertEqual(len(r['errors']), 2)
        self.assertEqual(r['errors'][0]['code'], '101')
        self.assertIn('ΑΦΜ', r['errors'][0]['message'])

    def test_cancellation_response(self):
        r = parse_response_doc(RESPONSE_CANCEL)[0]
        self.assertEqual(r['status_code'], 'Success')
        self.assertEqual(r['cancellation_mark'], 400009999999999)

    def test_invalid_xml_raises(self):
        with self.assertRaises(ValueError):
            parse_response_doc('not xml at all')

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            parse_response_doc('')

    def test_response_doc_without_responses_raises(self):
        with self.assertRaises(ValueError):
            parse_response_doc('<ResponseDoc></ResponseDoc>')

    def test_namespaced_response(self):
        # Κάποιες απαντήσεις έρχονται με default namespace
        xml = RESPONSE_SUCCESS.replace(
            '<ResponseDoc xmlns:xsd="http://www.w3.org/2001/XMLSchema">',
            '<ResponseDoc xmlns="http://www.aade.gr/myDATA/response/v1.0">',
        )
        r = parse_response_doc(xml)[0]
        self.assertEqual(r['status_code'], 'Success')
        self.assertEqual(r['invoice_mark'], 400001234567890)

    def test_wcf_string_wrapped_response(self):
        # Κάποια WCF endpoints τυλίγουν το XML σε <string> με escaped περιεχόμενο
        import html as html_mod
        wrapped = (
            '<string xmlns="http://schemas.microsoft.com/2003/10/Serialization/">'
            + html_mod.escape(RESPONSE_SUCCESS.split('?>', 1)[1])
            + '</string>'
        )
        r = parse_response_doc(wrapped)[0]
        self.assertEqual(r['status_code'], 'Success')
        self.assertEqual(r['invoice_mark'], 400001234567890)

    def test_roundtrip_build_then_wellformed(self):
        # Το built XML πρέπει να είναι well-formed και re-parseable
        xml = build_invoices_doc([sample_invoice(), sample_invoice(aa='102')])
        root = ET.fromstring(xml)
        self.assertEqual(len(findall(root, 'invoice')), 2)
