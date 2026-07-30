# -*- coding: utf-8 -*-
"""
mydata/invoice_xml.py

Κατασκευή του επίσημου XML InvoicesDoc για αποστολή παραστατικών στο
myDATA (ΑΑΔΕ) και parsing του ResponseDoc που επιστρέφει.

Το επίσημο συμβόλαιο του /SendInvoices είναι XML (namespace
http://www.aade.gr/myDATA/invoice/v1.0), ΟΧΙ JSON — βλ. τεκμηρίωση ΑΑΔΕ.
Η σειρά των στοιχείων ακολουθεί το XSD (sequence) και έχει σημασία.
Όταν ο υποβάλλων είναι ο εκδότης, κάθε γραμμή απαιτεί χαρακτηρισμό
εσόδων (incomeClassification, namespace icls) και το invoiceSummary
τους συγκεντρωτικούς χαρακτηρισμούς.

Καθαρό Python module (χωρίς Django imports) ώστε να είναι εύκολα testable.
"""
import html
import xml.etree.ElementTree as ET
from collections import OrderedDict
from decimal import Decimal
from typing import Dict, List

INVOICE_NS = 'http://www.aade.gr/myDATA/invoice/v1.0'
ICLS_NS = 'https://www.aade.gr/myDATA/incomeClassificaton/v1.0'

# Τρόπος πληρωμής myDATA: 5 = Επί πιστώσει (ασφαλές default για τιμολόγια)
DEFAULT_PAYMENT_METHOD = 5

# Default χαρακτηρισμοί εσόδων ανά τύπο παραστατικού (κατηγορία, τύπος Ε3).
# category1_1 = Έσοδα από πώληση εμπορευμάτων, category1_3 = παροχή υπηρεσιών.
# Ε3_561_001 = Πωλήσεις αγαθών και υπηρεσιών (χονδρικές).
DEFAULT_CLASSIFICATIONS = {
    '1.1': ('category1_1', 'E3_561_001'),
    '1.2': ('category1_1', 'E3_561_005'),   # ενδοκοινοτικές
    '1.3': ('category1_1', 'E3_561_006'),   # τρίτες χώρες
    '2.1': ('category1_3', 'E3_561_001'),
    '5.1': ('category1_1', 'E3_561_001'),   # πιστωτικά: ίδιος χαρακτηρισμός
    '5.2': ('category1_1', 'E3_561_001'),
}

# Τύποι με υποχρεωτικό correlatedInvoices (συσχετιζόμενα πιστωτικά)
CORRELATED_REQUIRED_TYPES = ('5.1',)

# Τύποι που απαιτούν αντισυμβαλλόμενο ΕΚΤΟΣ Ελλάδας
FOREIGN_COUNTERPART_TYPES = ('1.2', '1.3')


def _fmt_amount(value) -> str:
    """Ποσά με 2 δεκαδικά, όπως απαιτεί το myDATA."""
    return f"{Decimal(value):.2f}"


def _sub(parent, tag, text=None, ns=INVOICE_NS):
    # Όλα τα elements ρητά σε namespace — με register_namespace το output
    # βγαίνει με default xmlns / icls prefix όπως το περιμένει η ΑΑΔΕ
    el = ET.SubElement(parent, f'{{{ns}}}{tag}')
    if text is not None:
        el.text = str(text)
    return el


def _classification_for(inv, line):
    """(classificationCategory, classificationType) γραμμής — override ή default."""
    category = line.get('classification_category')
    cls_type = line.get('classification_type')
    if category and cls_type:
        return category, cls_type
    default = DEFAULT_CLASSIFICATIONS.get(inv['invoice_type'])
    if not default:
        raise ValueError(
            f"Δεν υπάρχει default χαρακτηρισμός εσόδων για τύπο "
            f"{inv['invoice_type']} — δώσε classification_category/type στη γραμμή"
        )
    return category or default[0], cls_type or default[1]


def _validate_invoice(inv):
    label = f"{inv.get('series')}/{inv.get('aa')}"
    if not inv.get('lines'):
        raise ValueError(f'Το παραστατικό {label} δεν έχει γραμμές')
    if not inv.get('counterpart_vat'):
        # Όλοι οι υποστηριζόμενοι τύποι (1.x/2.1/5.x) είναι B2B
        raise ValueError(
            f"Το παραστατικό {label} τύπου {inv['invoice_type']} "
            f'απαιτεί ΑΦΜ αντισυμβαλλόμενου'
        )
    country = inv.get('counterpart_country', 'GR')
    if inv['invoice_type'] in FOREIGN_COUNTERPART_TYPES and country == 'GR':
        raise ValueError(
            f"Ο τύπος {inv['invoice_type']} αφορά παραδόσεις εκτός Ελλάδας — "
            f'όρισε χώρα αντισυμβαλλόμενου (counterpart_country)'
        )
    if inv['invoice_type'] in CORRELATED_REQUIRED_TYPES and not inv.get('correlated_marks'):
        raise ValueError(
            f'Το πιστωτικό {label} (τύπος 5.1) απαιτεί MARK συσχετιζόμενου '
            f'παραστατικού (correlated_mark)'
        )
    for line in inv['lines']:
        if int(line['vat_category']) == 7 and not line.get('vat_exemption_category'):
            raise ValueError(
                f"Η γραμμή {line['line_number']} του {label} έχει κατηγορία ΦΠΑ 7 "
                f'(Χωρίς ΦΠΑ) — απαιτείται κατηγορία εξαίρεσης (vatExemptionCategory)'
            )


def build_invoices_doc(invoices: List[Dict]) -> str:
    """
    Χτίζει το XML InvoicesDoc από λίστα από invoice dicts.

    Κάθε dict έχει τη μορφή:
    {
        'issuer_vat': '123456783',
        'counterpart_vat': '999863881',
        'counterpart_country': 'GR',           # προαιρετικό
        'series': 'Α', 'aa': '101',
        'issue_date': date(2026, 7, 30),
        'invoice_type': '2.1',
        'currency': 'EUR',
        'payment_method': 5,                   # προαιρετικό
        'correlated_marks': [400000000000001], # για πιστωτικά 5.1
        'lines': [
            {'line_number': 1, 'net_value': Decimal('100.00'),
             'vat_category': 1, 'vat_amount': Decimal('24.00'),
             'vat_exemption_category': None,     # υποχρεωτικό για κατηγορία 7
             'classification_category': None,    # προαιρετικό override
             'classification_type': None},
        ],
        'total_net': Decimal('100.00'),
        'total_vat': Decimal('24.00'),
        'total_gross': Decimal('124.00'),
    }
    """
    if not invoices:
        raise ValueError('Δεν δόθηκαν παραστατικά για αποστολή')

    ET.register_namespace('', INVOICE_NS)
    ET.register_namespace('icls', ICLS_NS)
    root = ET.Element(f'{{{INVOICE_NS}}}InvoicesDoc')

    for inv in invoices:
        _validate_invoice(inv)
        invoice_el = _sub(root, 'invoice')

        # --- issuer (η σειρά των στοιχείων ακολουθεί το XSD) ---
        issuer = _sub(invoice_el, 'issuer')
        _sub(issuer, 'vatNumber', inv['issuer_vat'])
        _sub(issuer, 'country', 'GR')
        _sub(issuer, 'branch', 0)

        # --- counterpart ---
        counterpart = _sub(invoice_el, 'counterpart')
        _sub(counterpart, 'vatNumber', inv['counterpart_vat'])
        _sub(counterpart, 'country', inv.get('counterpart_country', 'GR'))
        _sub(counterpart, 'branch', 0)

        # --- invoiceHeader ---
        header = _sub(invoice_el, 'invoiceHeader')
        _sub(header, 'series', inv['series'])
        _sub(header, 'aa', inv['aa'])
        _sub(header, 'issueDate', inv['issue_date'].strftime('%Y-%m-%d'))
        _sub(header, 'invoiceType', inv['invoice_type'])
        _sub(header, 'currency', inv.get('currency', 'EUR'))
        for mark in inv.get('correlated_marks') or []:
            _sub(header, 'correlatedInvoices', mark)

        # --- paymentMethods ---
        payment = _sub(invoice_el, 'paymentMethods')
        detail = _sub(payment, 'paymentMethodDetails')
        _sub(detail, 'type', inv.get('payment_method', DEFAULT_PAYMENT_METHOD))
        _sub(detail, 'amount', _fmt_amount(inv['total_gross']))

        # --- invoiceDetails (γραμμές) + συγκέντρωση χαρακτηρισμών ---
        summary_cls = OrderedDict()   # (category, type) -> Decimal
        for line in inv['lines']:
            details = _sub(invoice_el, 'invoiceDetails')
            _sub(details, 'lineNumber', line['line_number'])
            _sub(details, 'netValue', _fmt_amount(line['net_value']))
            _sub(details, 'vatCategory', line['vat_category'])
            _sub(details, 'vatAmount', _fmt_amount(line['vat_amount']))
            if line.get('vat_exemption_category'):
                _sub(details, 'vatExemptionCategory', line['vat_exemption_category'])

            # Χαρακτηρισμός εσόδων γραμμής (υποχρεωτικός όταν υποβάλλει ο εκδότης)
            category, cls_type = _classification_for(inv, line)
            cls_el = _sub(details, 'incomeClassification')
            _sub(cls_el, 'classificationType', cls_type, ns=ICLS_NS)
            _sub(cls_el, 'classificationCategory', category, ns=ICLS_NS)
            _sub(cls_el, 'amount', _fmt_amount(line['net_value']), ns=ICLS_NS)
            key = (category, cls_type)
            summary_cls[key] = summary_cls.get(key, Decimal('0')) + Decimal(line['net_value'])

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
        for (category, cls_type), amount in summary_cls.items():
            cls_el = _sub(summary, 'incomeClassification')
            _sub(cls_el, 'classificationType', cls_type, ns=ICLS_NS)
            _sub(cls_el, 'classificationCategory', category, ns=ICLS_NS)
            _sub(cls_el, 'amount', _fmt_amount(amount), ns=ICLS_NS)

    return ET.tostring(root, encoding='unicode')


def _strip_ns(tag: str) -> str:
    return tag.split('}', 1)[1] if '}' in tag else tag


def _unwrap_wcf_string(xml_text: str) -> str:
    """
    Κάποια endpoints της ΑΑΔΕ (WCF) τυλίγουν το XML σε <string>...</string>
    με HTML-escaped περιεχόμενο. Το ξετυλίγουμε πριν το parsing.
    """
    stripped = xml_text.lstrip()
    if stripped.startswith('<string'):
        try:
            wrapper = ET.fromstring(stripped)
        except ET.ParseError:
            return xml_text
        if wrapper.text and wrapper.text.strip():
            return html.unescape(wrapper.text)
    return xml_text


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
    xml_text = _unwrap_wcf_string(xml_text)
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
