# -*- coding: utf-8 -*-
"""
accounting/gsis_client.py
Author: Claude
Description: GSIS API Client για αναζήτηση στοιχείων με ΑΦΜ.

Χρησιμοποιεί το SOAP Web Service RgWsPublic2 της ΑΑΔΕ:
https://www1.gsis.gr/wsaade/RgWsPublic2/RgWsPublic2

Απαιτεί "Ειδικούς Κωδικούς Λήψης Στοιχείων" από την ΑΑΔΕ.
"""

import logging
import requests
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from xml.etree import ElementTree as ET
from accounting.services.access import mask_pii_value

logger = logging.getLogger(__name__)


# GSIS SOAP Endpoint
GSIS_WSDL_URL = "https://www1.gsis.gr/wsaade/RgWsPublic2/RgWsPublic2"

# XML Namespaces (from working AADE script)
NAMESPACES = {
    'env': 'http://www.w3.org/2003/05/soap-envelope',
    'srvc': 'http://rgwspublic2/RgWsPublic2Service',
    'rg': 'http://rgwspublic2/RgWsPublic2',
}


@dataclass
class AFMInfo:
    """Αποτέλεσμα αναζήτησης ΑΦΜ από GSIS."""
    afm: str
    doy: str
    doy_descr: str
    onomasia: str  # Επωνυμία
    legal_form: str  # Νομική μορφή
    legal_form_descr: str
    deactivation_flag: bool  # Απενεργοποιημένο
    deactivation_flag_descr: str
    firm_flag: bool  # Είναι επιχείρηση
    firm_flag_descr: str
    registration_date: Optional[str]  # Ημ/νία έναρξης
    stop_date: Optional[str]  # Ημ/νία διακοπής

    # Διεύθυνση έδρας
    postal_address: str
    postal_address_no: str
    postal_zip_code: str
    postal_area: str

    # Δραστηριότητες
    activities: List[Dict[str, Any]]

    # Raw data
    raw_data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Επιστρέφει τα δεδομένα ως dictionary."""
        return {
            'afm': self.afm,
            'doy': self.doy,
            'doy_descr': self.doy_descr,
            'onomasia': self.onomasia,
            'legal_form': self.legal_form,
            'legal_form_descr': self.legal_form_descr,
            'deactivation_flag': self.deactivation_flag,
            'deactivation_flag_descr': self.deactivation_flag_descr,
            'firm_flag': self.firm_flag,
            'firm_flag_descr': self.firm_flag_descr,
            'registration_date': self.registration_date,
            'stop_date': self.stop_date,
            'postal_address': self.postal_address,
            'postal_address_no': self.postal_address_no,
            'postal_zip_code': self.postal_zip_code,
            'postal_area': self.postal_area,
            'activities': self.activities,
        }


class GSISError(Exception):
    """Exception για σφάλματα GSIS API."""
    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class GSISClient:
    """
    Client για το GSIS Web Service RgWsPublic2.

    Χρήση:
        client = GSISClient(afm='123456789', username='...', password='...')
        info = client.lookup_afm('987654321')
    """

    def __init__(self, afm: str, username: str, password: str):
        """
        Αρχικοποίηση του client.

        Args:
            afm: ΑΦΜ του λογιστή (για afm_called_by)
            username: Ειδικός κωδικός λήψης στοιχείων - Username
            password: Ειδικός κωδικός λήψης στοιχείων - Password
        """
        self.afm = afm
        self.username = username
        self.password = password
        self.session = requests.Session()

    def _build_soap_envelope(self, afm_called_by: str, afm_called_for: str) -> str:
        """
        Δημιουργεί το SOAP envelope για την αναζήτηση.

        Args:
            afm_called_by: ΑΦΜ του καλούντος (λογιστή)
            afm_called_for: ΑΦΜ προς αναζήτηση

        Returns:
            SOAP XML string
        """
        # Correct namespaces from working AADE script
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<env:Envelope xmlns:env="http://www.w3.org/2003/05/soap-envelope"
              xmlns:ns1="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
              xmlns:ns2="http://rgwspublic2/RgWsPublic2Service"
              xmlns:ns3="http://rgwspublic2/RgWsPublic2">
    <env:Header>
        <ns1:Security>
            <ns1:UsernameToken>
                <ns1:Username>{self.username}</ns1:Username>
                <ns1:Password>{self.password}</ns1:Password>
            </ns1:UsernameToken>
        </ns1:Security>
    </env:Header>
    <env:Body>
        <ns2:rgWsPublic2AfmMethod>
            <ns2:INPUT_REC>
                <ns3:afm_called_by>{afm_called_by}</ns3:afm_called_by>
                <ns3:afm_called_for>{afm_called_for}</ns3:afm_called_for>
            </ns2:INPUT_REC>
        </ns2:rgWsPublic2AfmMethod>
    </env:Body>
</env:Envelope>'''

    def _parse_response(self, xml_response: str) -> AFMInfo:
        """
        Αναλύει την XML απάντηση του GSIS.

        Args:
            xml_response: XML string από το GSIS

        Returns:
            AFMInfo object με τα στοιχεία

        Raises:
            GSISError: Αν υπάρχει σφάλμα στην απάντηση
        """
        try:
            root = ET.fromstring(xml_response)
        except ET.ParseError as e:
            logger.error(f"Failed to parse GSIS XML response: {e}")
            raise GSISError(f"Σφάλμα ανάλυσης XML: {e}")

        # Helper function για να βρούμε text από element
        def get_text(element, tag: str, default: str = '') -> str:
            if element is None:
                return default
            el = element.find(tag, NAMESPACES)
            if el is None:
                # Try without namespace prefix
                el = element.find(f'.//{tag.split(":")[-1]}')
            if el is None:
                return default
            # Check for xsi:nil
            nil_attr = el.get('{http://www.w3.org/2001/XMLSchema-instance}nil')
            if nil_attr == 'true':
                return default
            return el.text or default

        # Βρες το result (from srvc namespace)
        result = root.find('.//srvc:result', NAMESPACES)
        if result is None:
            # Try without namespace
            result = root.find('.//{http://rgwspublic2/RgWsPublic2Service}result')
        if result is None:
            # Try to find any result element
            for elem in root.iter():
                if elem.tag.endswith('result'):
                    result = elem
                    break

        if result is None:
            logger.error(f"No result found in response: {xml_response[:500]}")
            raise GSISError("Δεν βρέθηκε αποτέλεσμα στην απάντηση")

        # Έλεγχος για error code
        error_code = None
        error_descr = None
        for elem in result.iter():
            if elem.tag.endswith('error_code') and elem.text:
                error_code = elem.text
            if elem.tag.endswith('error_descr') and elem.text:
                error_descr = elem.text

        if error_code:
            raise GSISError(error_descr or 'Άγνωστο σφάλμα', error_code)

        # Βρες το basic_rec
        basic_rec = None
        for elem in result.iter():
            if elem.tag.endswith('basic_rec'):
                basic_rec = elem
                break

        if basic_rec is None:
            raise GSISError("Δεν βρέθηκαν στοιχεία basic_rec")

        # Helper to get text from basic_rec
        def get_basic(tag: str, default: str = '') -> str:
            for elem in basic_rec.iter():
                if elem.tag.endswith(tag):
                    nil_attr = elem.get('{http://www.w3.org/2001/XMLSchema-instance}nil')
                    if nil_attr == 'true':
                        return default
                    return elem.text or default
            return default

        # Εξαγωγή βασικών στοιχείων
        afm = get_basic('afm')
        onomasia = get_basic('onomasia')
        doy = get_basic('doy')
        doy_descr = get_basic('doy_descr')
        legal_form = get_basic('legal_status_descr')  # Νομική μορφή
        legal_form_descr = get_basic('legal_status_descr')
        deactivation = get_basic('deactivation_flag', '1')
        deactivation_descr = get_basic('deactivation_flag_descr')
        firm_flag_str = get_basic('firm_flag_descr')
        postal_address = get_basic('postal_address')
        postal_address_no = get_basic('postal_address_no')
        postal_zip_code = get_basic('postal_zip_code')
        postal_area = get_basic('postal_area_description')
        registration_date = get_basic('regist_date')
        stop_date = get_basic('stop_date')

        # Debug logging for address fields
        logger.info(f"GSIS parsed address fields - postal_address: '{postal_address}', "
                    f"postal_address_no: '{postal_address_no}', "
                    f"postal_zip_code: '{postal_zip_code}', "
                    f"postal_area: '{postal_area}'")

        # Δραστηριότητες
        activities = []
        for elem in result.iter():
            if elem.tag.endswith('firm_act_tab'):
                for item in elem.iter():
                    if item.tag.endswith('item'):
                        act_data = {}
                        for child in item:
                            tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                            if child.text:
                                act_data[tag_name] = child.text
                        if act_data:
                            activities.append(act_data)

        # Raw data για debugging
        raw_data = {
            'xml_response': xml_response[:1000] if len(xml_response) > 1000 else xml_response
        }

        return AFMInfo(
            afm=afm,
            doy=doy,
            doy_descr=doy_descr,
            onomasia=onomasia,
            legal_form=legal_form,
            legal_form_descr=legal_form_descr,
            deactivation_flag=deactivation != '1',  # 1 = ενεργό, 2 = απενεργοποιημένο
            deactivation_flag_descr=deactivation_descr,
            firm_flag=firm_flag_str.lower() in ['ναι', 'yes', 'true', '1', 'επιτηδευματιασ'] if firm_flag_str else False,
            firm_flag_descr=firm_flag_str,
            registration_date=registration_date if registration_date else None,
            stop_date=stop_date if stop_date else None,
            postal_address=postal_address,
            postal_address_no=postal_address_no,
            postal_zip_code=postal_zip_code,
            postal_area=postal_area,
            activities=activities,
            raw_data=raw_data,
        )

    def lookup_afm(self, afm: str, afm_called_by: str = None) -> AFMInfo:
        """
        Αναζήτηση στοιχείων με ΑΦΜ.

        Args:
            afm: Το ΑΦΜ προς αναζήτηση
            afm_called_by: ΑΦΜ του καλούντος (optional, χρησιμοποιεί το username αν δεν δοθεί)

        Returns:
            AFMInfo με τα στοιχεία του ΑΦΜ

        Raises:
            GSISError: Αν υπάρχει σφάλμα
        """
        # Validation
        if not afm or len(afm) != 9 or not afm.isdigit():
            raise GSISError("Μη έγκυρο ΑΦΜ. Πρέπει να είναι 9 ψηφία.")

        # Αν δεν δόθηκε afm_called_by, χρησιμοποίησε το ΑΦΜ του λογιστή
        if not afm_called_by:
            afm_called_by = self.afm

        # Build SOAP request
        soap_envelope = self._build_soap_envelope(afm_called_by, afm)

        # SOAP 1.2 uses application/soap+xml, SOAPAction in Content-Type
        headers = {
            'Content-Type': 'application/soap+xml; charset=utf-8; action="http://gr/gsis/rgwspublic2/RgWsPublic2/rgWsPublic2AfmMethod"',
        }

        logger.info(f"Looking up AFM: {mask_pii_value(afm)}")

        try:
            # Authentication is in the SOAP Header (WS-Security), not HTTP Basic Auth
            response = self.session.post(
                GSIS_WSDL_URL,
                data=soap_envelope.encode('utf-8'),
                headers=headers,
                timeout=30,
            )

            logger.debug(f"GSIS Response status: {response.status_code}")

            if response.status_code == 401:
                raise GSISError("Σφάλμα αυθεντικοποίησης. Ελέγξτε τα credentials.")

            if response.status_code != 200:
                raise GSISError(f"HTTP Error: {response.status_code}")

            return self._parse_response(response.text)

        except requests.RequestException as e:
            logger.error(f"GSIS request failed: {e}")
            raise GSISError(f"Σφάλμα σύνδεσης με GSIS: {e}")

    def test_connection(self) -> bool:
        """
        Δοκιμάζει τη σύνδεση με το GSIS.

        Returns:
            True αν η σύνδεση είναι επιτυχής
        """
        try:
            # Δοκίμασε με ένα γνωστό ΑΦΜ (π.χ. ΔΕΗ)
            self.lookup_afm('090000045')
            return True
        except GSISError as e:
            # Αν το σφάλμα είναι authentication, η σύνδεση απέτυχε
            if 'αυθεντικοποίησης' in str(e).lower() or '401' in str(e):
                return False
            # Άλλα σφάλματα (π.χ. invalid AFM) σημαίνουν ότι η σύνδεση λειτουργεί
            return True
        except Exception:
            return False


def get_gsis_client():
    """
    Επιστρέφει GSISClient με τα credentials από τη βάση.

    Returns:
        GSISClient instance ή None αν δεν υπάρχουν credentials
    """
    from settings.models import GSISSettings

    settings = GSISSettings.get_settings()
    if not settings or not settings.is_active:
        return None

    return GSISClient(
        afm=settings.afm,
        username=settings.username,
        password=settings.password,
    )


def lookup_afm(afm: str) -> Optional[AFMInfo]:
    """
    Shortcut function για αναζήτηση ΑΦΜ.

    Args:
        afm: Το ΑΦΜ προς αναζήτηση

    Returns:
        AFMInfo ή None αν δεν υπάρχουν credentials

    Raises:
        GSISError: Αν υπάρχει σφάλμα
    """
    client = get_gsis_client()
    if not client:
        raise GSISError("Δεν έχουν ρυθμιστεί τα credentials GSIS.")

    return client.lookup_afm(afm)
