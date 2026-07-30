# -*- coding: utf-8 -*-
"""
mydata/invoice_xml.py

Κατασκευή του επίσημου XML InvoicesDoc για αποστολή παραστατικών στο
myDATA (ΑΑΔΕ) και parsing του ResponseDoc που επιστρέφει.

Το επίσημο συμβόλαιο του /SendInvoices είναι XML (namespace
http://www.aade.gr/myDATA/invoice/v1.0), ΟΧΙ JSON — βλ. τεκμηρίωση ΑΑΔΕ.
Η σειρά των στοιχείων ακολουθεί το XSD (sequence) και έχει σημασία.

Καθαρό Python module (χωρίς Django imports) ώστε να είναι εύκολα testable.
"""
import xml.etree.ElementTree as ET
from decimal import Decimal
from typing import Dict, List

INVOICE_NS = 'http://www.aade.gr/myDATA/invoice/v1.0'

# Τρόπος πληρωμής myDATA: 5 = Επί πιστώσει (ασφαλές default για τιμολόγια)
DEFAULT_PAYMENT_METHOD = 5


def _fmt_amount(value) -> str:
    """Ποσά με 2 δεκαδικά, όπως απαιτεί το myDATA."""
    return f"{Decimal(value):.2f}"


def _sub(parent, tag, text=None):
    # Όλα τα elements ρητά στο namespace του myDATA — με register_namespace('')
    # το output βγαίνει με default xmlns χωρίς prefixes, όπως το περιμένει η ΑΑΔΕ
    el = ET.SubElement(parent, f'{{{INVOICE_NS}}}{tag}')
    if text is not None:
        el.text = str(text)
    return el


def build_invoices_doc(invoices: List[Dict]) -> str:
    """
    Χτίζει το XML InvoicesDoc από λίστα από invoice dicts.

    Κάθε dict έχει τη μορφή:
    {
        'issuer_vat': '123456783',
        'counterpart_vat': '999863881',       # προαιρετικό (B2C: κενό)
        'series': 'Α', 'aa': '101',
        'issue_date': date(2026, 7, 30),
        'invoice_type': '2.1',
        'currency': 'EUR',
        'payment_method': 5,                   # προαιρετικό
        'lines': [
            {'line_number': 1, 'net_value': Decimal('100.00'),
             'vat_category': 1, 'vat_amount': Decimal('24.00')},
        ],
        'total_net': Decimal('100.00'),
        'total_vat': Decimal('24.00'),
        'total_gross': Decimal('124.00'),
    }
    """
    if not invoices:
        raise ValueError('Δεν δόθηκαν παραστατικά για αποστολή')

    ET.register_namespace('', INVOICE_NS)
    root = ET.Element(f'{{{INVOICE_NS}}}InvoicesDoc')

    for inv in invoices:
        invoice_el = _sub(root, 'invoice')

        # --- issuer (η σειρά των στοιχείων ακολουθεί το XSD) ---
        issuer = _sub(invoice_el, 'issuer')
        _sub(issuer, 'vatNumber', inv['issuer_vat'])
        _sub(issuer, 'country', 'GR')
        _sub(issuer, 'branch', 0)

        # --- counterpart (μόνο όταν υπάρχει ΑΦΜ αντισυμβαλλόμενου) ---
        if inv.get('counterpart_vat'):
            counterpart = _sub(invoice_el, 'counterpart')
            _sub(counterpart, 'vatNumber', inv['counterpart_vat'])
            _sub(counterpart, 'country', 'GR')
            _sub(counterpart, 'branch', 0)

        # --- invoiceHeader ---
        header = _sub(invoice_el, 'invoiceHeader')
        _sub(header, 'series', inv['series'])
        _sub(header, 'aa', inv['aa'])
        _sub(header, 'issueDate', inv['issue_date'].strftime('%Y-%m-%d'))
        _sub(header, 'invoiceType', inv['invoice_type'])
        _sub(header, 'currency', inv.get('currency', 'EUR'))

        # --- paymentMethods ---
        payment = _sub(invoice_el, 'paymentMethods')
        detail = _sub(payment, 'paymentMethodDetails')
        _sub(detail, 'type', inv.get('payment_method', DEFAULT_PAYMENT_METHOD))
        _sub(detail, 'amount', _fmt_amount(inv['total_gross']))

        # --- invoiceDetails (γραμμές) ---
        if not inv.get('lines'):
            raise ValueError(
                f"Το παραστατικό {inv.get('series')}/{inv.get('aa')} δεν έχει γραμμές"
            )
        for line in inv['lines']:
            details = _sub(invoice_el, 'invoiceDetails')
            _sub(details, 'lineNumber', line['line_number'])
            _sub(details, 'netValue', _fmt_amount(line['net_value']))
            _sub(details, 'vatCategory', line['vat_category'])
            _sub(details, 'vatAmount', _fmt_amount(line['vat_amount']))

        # --- invoiceSummary ---
        summary = _sub(invoice_el, 'invoiceSummary')
        _sub(summary, 'totalNetValue', _fmt_amount(inv['total_net']))
        _sub(summary, 'totalVatAmount', _fmt_amount(inv['total_vat']))
        _sub(summary, 'totalWithheldAmount', '0.00')
        _sub(summary, 'totalFeesAmount', '0.00')
        _sub(summary, 'totalStampDutyAmount', '0.00')
        _sub(summary, 'totalOtherTaxesAmount', '0.00')
        _sub(summary, 'totalDeductionsAmount', '0.00')
        _sub(summary, 'totalGrossValue', _fmt_amount(inv['total_gross']))

    return ET.tostring(root, encoding='unicode')


def _strip_ns(tag: str) -> str:
    return tag.split('}', 1)[1] if '}' in tag else tag


def parse_response_doc(xml_text: str) -> List[Dict]:
    """
    Parsing του ResponseDoc της ΑΑΔΕ (SendInvoices / CancelInvoice).

    Επιστρέφει λίστα από dicts, ένα ανά <response>:
    {
        'index': 1,
        'status_code': 'Success' | 'ValidationError' | ...,
        'invoice_uid': '...' or None,
        'invoice_mark': 400001234567890 or None,
        'cancellation_mark': ... or None,
        'errors': [{'code': '...', 'message': '...'}],
    }

    Raises ValueError για μη-parseable ή άδειο response.
    """
    if not xml_text or not isinstance(xml_text, str):
        raise ValueError('Κενή απάντηση από το myDATA')
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f'Μη αναγνώσιμη απάντηση myDATA: {exc}') from exc

    results = []
    for resp in root.iter():
        if _strip_ns(resp.tag) != 'response':
            continue
        item = {
            'index': None,
            'status_code': None,
            'invoice_uid': None,
            'invoice_mark': None,
            'cancellation_mark': None,
            'errors': [],
        }
        for child in resp:
            tag = _strip_ns(child.tag)
            text = (child.text or '').strip()
            if tag == 'index' and text:
                item['index'] = int(text)
            elif tag == 'statusCode':
                item['status_code'] = text
            elif tag == 'invoiceUid':
                item['invoice_uid'] = text or None
            elif tag == 'invoiceMark' and text:
                item['invoice_mark'] = int(text)
            elif tag == 'cancellationMark' and text:
                item['cancellation_mark'] = int(text)
            elif tag == 'errors':
                for err in child:
                    if _strip_ns(err.tag) != 'error':
                        continue
                    error = {'code': None, 'message': None}
                    for field in err:
                        ftag = _strip_ns(field.tag)
                        if ftag == 'code':
                            error['code'] = (field.text or '').strip()
                        elif ftag == 'message':
                            error['message'] = (field.text or '').strip()
                    item['errors'].append(error)
        results.append(item)

    if not results:
        raise ValueError('Το ResponseDoc δεν περιέχει κανένα <response>')
    return results
