# mydata/client.py
"""
myDATA API Client για AADE (ΑΑΔΕ Ηλεκτρονικά Βιβλία)
Documentation: https://www.aade.gr/mydata

Enhanced version με:
- Retry logic με exponential backoff
- Rate limiting (2 req/sec)
- RequestVatInfo με pagination
- Proper XML parsing
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Generator, Any, Union
from dataclasses import dataclass
from decimal import Decimal
import logging
import time
import functools

logger = logging.getLogger(__name__)


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class MyDataAPIError(Exception):
    """Base exception για myDATA API errors"""
    def __init__(self, message: str, status_code: int = None, response_text: str = None):
        self.message = message
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(self.message)


class MyDataAuthError(MyDataAPIError):
    """401/403 - Authentication/Authorization errors"""
    pass


class MyDataRateLimitError(MyDataAPIError):
    """429 - Too Many Requests"""
    pass


class MyDataValidationError(MyDataAPIError):
    """400 - Bad Request / Validation errors"""
    pass


class MyDataServerError(MyDataAPIError):
    """5xx - Server errors (retriable)"""
    pass


class MyDataCredentialsNotFoundError(Exception):
    """Ο πελάτης δεν έχει myDATA credentials"""
    def __init__(self, client_afm: str):
        self.client_afm = client_afm
        self.message = f"Δεν υπάρχουν myDATA credentials για τον πελάτη με ΑΦΜ: {client_afm}. Παρακαλώ καταχωρήστε τα."
        super().__init__(self.message)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class VatInfoRecord:
    """Εγγραφή από RequestVatInfo response"""
    mark: int
    is_cancelled: bool
    issue_date: date
    rec_type: int  # 1=Εκροές, 2=Εισροές
    inv_type: str  # Τύπος παραστατικού (1.1, 2.1, etc)
    vat_category: int  # 1-8
    vat_exemption_category: Optional[str]
    net_value: Decimal
    vat_amount: Decimal
    counter_vat_number: Optional[str]
    vat_offset_amount: Optional[Decimal]
    deductions_amount: Optional[Decimal]
    expense_category: str = ''

    @property
    def is_income(self) -> bool:
        """Εκροές (έσοδα)"""
        return self.rec_type == 1

    @property
    def is_expense(self) -> bool:
        """Εισροές (έξοδα)"""
        return self.rec_type == 2

    @property
    def vat_rate_display(self) -> str:
        """Human-readable VAT rate"""
        rates = {
            1: '24%', 2: '13%', 3: '6%', 4: '17%',
            5: '9%', 6: '4%', 7: '0%', 8: 'Χωρίς ΦΠΑ'
        }
        return rates.get(self.vat_category, 'Άγνωστο')


@dataclass
class PaginationInfo:
    """Pagination info από myDATA response"""
    has_more: bool
    next_partition_key: Optional[str] = None
    next_row_key: Optional[str] = None


# =============================================================================
# DECORATORS
# =============================================================================

def retry_with_backoff(
    max_retries: int = 4,
    base_delay: float = 1.0,
    max_delay: float = 16.0,
    retriable_exceptions: tuple = (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        MyDataServerError,
        MyDataRateLimitError,
    )
):
    """
    Decorator για retry με exponential backoff.

    Delays: 1s, 2s, 4s, 8s (max 16s)
    Retries μόνο σε network errors και 429/5xx
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retriable_exceptions as e:
                    last_exception = e

                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logger.warning(
                            f"myDATA API retry {attempt + 1}/{max_retries} "
                            f"after {delay}s delay. Error: {str(e)}"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"myDATA API failed after {max_retries} retries: {str(e)}"
                        )
                except (MyDataAuthError, MyDataValidationError):
                    # Δεν κάνουμε retry σε auth/validation errors
                    raise

            raise last_exception
        return wrapper
    return decorator


class RateLimiter:
    """
    Simple rate limiter για API calls.
    Default: 2 requests per second
    """
    def __init__(self, requests_per_second: float = 2.0):
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0

    def wait(self):
        """Wait if needed to respect rate limit"""
        now = time.time()
        elapsed = now - self.last_request_time

        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            time.sleep(sleep_time)

        self.last_request_time = time.time()


# =============================================================================
# MAIN CLIENT CLASS
# =============================================================================

class MyDataClient:
    """
    Client για το myDATA REST API της AADE.

    Υποστηρίζει:
    - RequestVatInfo (ΦΠΑ εισροών/εκροών)
    - RequestDocs (παραστατικά που έλαβες)
    - RequestTransmittedDocs (παραστατικά που έστειλες)
    - RequestMyIncome / RequestMyExpenses
    - SendInvoices / CancelInvoice

    Features:
    - Automatic retry με exponential backoff
    - Rate limiting (2 req/sec)
    - Pagination handling
    - Proper XML parsing
    """

    # API URLs
    PROD_BASE_URL = "https://mydatapi.aade.gr/myDATA"
    SANDBOX_BASE_URL = "https://mydataapidev.aade.gr"

    # VAT Categories reference
    VAT_CATEGORIES = {
        1: {'rate': 24, 'description': 'ΦΠΑ 24%'},
        2: {'rate': 13, 'description': 'ΦΠΑ 13%'},
        3: {'rate': 6, 'description': 'ΦΠΑ 6%'},
        4: {'rate': 17, 'description': 'ΦΠΑ 17%'},
        5: {'rate': 9, 'description': 'ΦΠΑ 9%'},
        6: {'rate': 4, 'description': 'ΦΠΑ 4%'},
        7: {'rate': 0, 'description': 'ΦΠΑ 0%'},
        8: {'rate': 0, 'description': 'Χωρίς ΦΠΑ'},
    }

    def __init__(
        self,
        user_id: str,
        subscription_key: str,
        is_sandbox: bool = False,
        requests_per_second: float = 2.0
    ):
        """
        Αρχικοποίηση client.

        Args:
            user_id: Το user_id από το TAXISnet (username για sandbox, ΑΦΜ για production)
            subscription_key: Το subscription key από την AADE
            is_sandbox: True για testing environment
            requests_per_second: Rate limit (default: 2 req/sec)
        """
        if not user_id or not subscription_key:
            raise ValueError("user_id και subscription_key είναι υποχρεωτικά")

        self.user_id = user_id
        self.subscription_key = subscription_key
        self.is_sandbox = is_sandbox
        self.base_url = self.SANDBOX_BASE_URL if is_sandbox else self.PROD_BASE_URL

        # Rate limiter
        self.rate_limiter = RateLimiter(requests_per_second)

        # Session με default headers
        self.session = requests.Session()
        self.session.headers.update({
            'aade-user-id': self.user_id,
            'Ocp-Apim-Subscription-Key': self.subscription_key,
            'Accept': 'application/xml',  # myDATA επιστρέφει κυρίως XML
        })

        logger.info(
            f"MyDataClient initialized - Environment: {'SANDBOX' if is_sandbox else 'PRODUCTION'}"
        )

    # =========================================================================
    # INTERNAL METHODS
    # =========================================================================

    def _raise_for_status(self, response: requests.Response):
        """Raise appropriate exception based on status code"""
        if response.status_code == 200:
            return

        error_text = response.text[:500] if response.text else "No response body"

        if response.status_code == 400:
            raise MyDataValidationError(
                f"Bad Request: {error_text}",
                status_code=400,
                response_text=error_text
            )
        elif response.status_code in (401, 403):
            raise MyDataAuthError(
                f"Authentication failed: {error_text}",
                status_code=response.status_code,
                response_text=error_text
            )
        elif response.status_code == 429:
            raise MyDataRateLimitError(
                "Rate limit exceeded",
                status_code=429,
                response_text=error_text
            )
        elif response.status_code >= 500:
            raise MyDataServerError(
                f"Server error: {error_text}",
                status_code=response.status_code,
                response_text=error_text
            )
        else:
            raise MyDataAPIError(
                f"HTTP {response.status_code}: {error_text}",
                status_code=response.status_code,
                response_text=error_text
            )

    @retry_with_backoff()
    def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Union[str, Dict]:
        """
        Helper για API requests με retry και rate limiting.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (π.χ. '/RequestVatInfo')
            **kwargs: Extra arguments για requests

        Returns:
            Response text (XML) ή dict (JSON)
        """
        # Rate limiting
        self.rate_limiter.wait()

        url = f"{self.base_url}{endpoint}"

        logger.debug(f"myDATA API Request: {method} {url}")
        if 'params' in kwargs:
            logger.debug(f"  Params: {kwargs['params']}")

        try:
            response = self.session.request(
                method,
                url,
                timeout=30,  # 30 second timeout
                **kwargs
            )

            self._raise_for_status(response)

            logger.info(f"myDATA API: {method} {endpoint} - Status {response.status_code}")

            if not response.content:
                return {}

            content_type = response.headers.get('Content-Type', '')

            if 'json' in content_type.lower():
                return response.json()
            else:
                # Return raw text (XML)
                return response.text

        except requests.exceptions.Timeout:
            logger.error(f"myDATA API Timeout: {method} {endpoint}")
            raise MyDataServerError("Request timeout", status_code=None)
        except requests.exceptions.RequestException as e:
            logger.error(f"myDATA API Network Error: {method} {endpoint} - {str(e)}")
            raise

    @staticmethod
    def _format_date(d: Union[date, datetime, None]) -> Optional[str]:
        """Format date to dd/MM/yyyy"""
        if d is None:
            return None
        if isinstance(d, datetime):
            d = d.date()
        return d.strftime('%d/%m/%Y')

    @staticmethod
    def _parse_date(date_str: str) -> Optional[date]:
        """Parse date from various formats"""
        if not date_str:
            return None

        # Try different formats (including ISO datetime with T)
        for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%d/%m/%Y', '%d-%m-%Y'):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        logger.warning(f"Could not parse date: {date_str}")
        return None

    @staticmethod
    def _parse_decimal(value: Any) -> Decimal:
        """Safely parse decimal from various types"""
        if value is None:
            return Decimal('0')
        try:
            return Decimal(str(value))
        except:
            return Decimal('0')

    @staticmethod
    def _parse_bool(value: Any) -> bool:
        """Parse boolean from string"""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes')
        return bool(value)

    @staticmethod
    def _get_xml_text(element: ET.Element, tag: str, default: str = None) -> Optional[str]:
        """Safely get text from XML element"""
        child = element.find(tag)
        if child is not None and child.text:
            return child.text.strip()
        return default

    # =========================================================================
    # REQUEST VAT INFO - ΚΥΡΙΑ ΜΕΘΟΔΟΣ ΓΙΑ ΦΠΑ
    # =========================================================================

    def request_vat_info(
        self,
        date_from: Union[date, datetime],
        date_to: Union[date, datetime],
        entity_vat_number: Optional[str] = None,
        grouped_per_day: bool = False
    ) -> Generator[VatInfoRecord, None, PaginationInfo]:
        """
        Λήψη πληροφοριών ΦΠΑ εισροών/εκροών.

        Generator που επιστρέφει VatInfoRecord objects.
        Χειρίζεται αυτόματα το pagination.

        Args:
            date_from: Από ημερομηνία (required)
            date_to: Έως ημερομηνία (required)
            entity_vat_number: ΑΦΜ οντότητας (για τρίτους)
            grouped_per_day: True για ομαδοποίηση ανά ημέρα

        Yields:
            VatInfoRecord objects

        Returns:
            PaginationInfo με τελική κατάσταση

        Example:
            >>> client = MyDataClient(user_id, key)
            >>> records = list(client.request_vat_info(
            ...     date_from=date(2025, 1, 1),
            ...     date_to=date(2025, 1, 31)
            ... ))
            >>> print(f"Fetched {len(records)} VAT records")
        """
        params = {
            'dateFrom': self._format_date(date_from),
            'dateTo': self._format_date(date_to),
        }

        if entity_vat_number:
            params['entityVatNumber'] = entity_vat_number

        if grouped_per_day:
            params['GroupedPerDay'] = 'true'

        next_partition_key = None
        next_row_key = None
        total_fetched = 0
        page = 0

        while True:
            page += 1

            # Add pagination params if we have them
            if next_partition_key:
                params['nextPartitionKey'] = next_partition_key
            if next_row_key:
                params['nextRowKey'] = next_row_key

            logger.info(f"RequestVatInfo - Page {page}, fetched so far: {total_fetched}")

            response = self._make_request('GET', '/RequestVatInfo', params=params)

            # Parse XML response
            records, pagination = self._parse_vat_info_response(response)

            for record in records:
                total_fetched += 1
                yield record

            logger.info(f"RequestVatInfo - Page {page} returned {len(records)} records")

            # Check if there are more pages
            if not pagination.has_more:
                logger.info(f"RequestVatInfo completed - Total: {total_fetched} records")
                return pagination

            # Update pagination params for next request
            next_partition_key = pagination.next_partition_key
            next_row_key = pagination.next_row_key

    def _parse_vat_info_response(
        self,
        response: str
    ) -> tuple[List[VatInfoRecord], PaginationInfo]:
        """
        Parse XML response από RequestVatInfo.

        Handles both formats:
        1. Detailed format with RecType, VatCategory, NetValue, VatAmount
        2. Summary format with Vat303 (εκροές), Vat333 (εισροές)

        Note: ΑΑΔΕ uses namespace, so we need to handle it.
        Also handles WCF-style double-encoded responses wrapped in <string> element.
        """
        import html

        records = []
        pagination = PaginationInfo(has_more=False)

        if not response or not isinstance(response, str):
            return records, pagination

        # Handle WCF-style double-encoded response
        # Response may be wrapped in: <string xmlns="...">HTML-encoded XML</string>
        if response.strip().startswith('<string'):
            try:
                # Parse the wrapper
                wrapper_root = ET.fromstring(response)
                # Get the text content (HTML-encoded XML)
                inner_xml = wrapper_root.text
                if inner_xml:
                    # Decode HTML entities (&lt; -> <, &gt; -> >, etc.)
                    response = html.unescape(inner_xml)
                    logger.debug("Decoded WCF-wrapped response")
            except ET.ParseError:
                pass  # Fall through to normal parsing

        try:
            root = ET.fromstring(response)
        except ET.ParseError as e:
            logger.error(f"XML Parse Error in VatInfo response: {e}")
            logger.debug(f"Response preview: {response[:500]}")
            return records, pagination

        # Define namespace (ΑΑΔΕ uses this)
        ns = {'aade': 'http://www.aade.gr/myDATA/invoice/v1.0'}

        # Try with namespace first, then without
        vat_info_elements = root.findall('aade:VatInfo', ns)
        if not vat_info_elements:
            vat_info_elements = root.findall('VatInfo')
        if not vat_info_elements:
            # Try finding all elements with local name VatInfo
            vat_info_elements = [elem for elem in root.iter() if elem.tag.endswith('VatInfo')]

        # === DEBUG LOGGING: Δες τι επιστρέφει το API ===
        print(f"[DEBUG] RequestVatInfo: Found {len(vat_info_elements)} VatInfo elements")
        for i, vat_elem in enumerate(vat_info_elements[:5]):  # Πρώτα 5 για debugging
            xml_str = ET.tostring(vat_elem, encoding='unicode')
            print(f"[DEBUG] VatInfo[{i}] RAW XML:\n{xml_str}")
            # Έλεγχος για RecType field
            rec_type_check = self._get_xml_text_flexible(vat_elem, 'RecType', ns)
            vat303_check = self._get_xml_text_flexible(vat_elem, 'Vat303', ns)
            vat333_check = self._get_xml_text_flexible(vat_elem, 'Vat333', ns)
            print(f"[DEBUG] VatInfo[{i}] Fields: RecType={rec_type_check}, Vat303={vat303_check}, Vat333={vat333_check}")
        # === END DEBUG LOGGING ===

        # Parse continuation token (pagination) - try both with and without namespace
        continuation = root.find('aade:continuationToken', ns)
        if continuation is None:
            continuation = root.find('continuationToken')

        if continuation is not None:
            next_partition = self._get_xml_text_flexible(continuation, 'nextPartitionKey', ns)
            next_row = self._get_xml_text_flexible(continuation, 'nextRowKey', ns)

            if next_partition or next_row:
                pagination = PaginationInfo(
                    has_more=True,
                    next_partition_key=next_partition,
                    next_row_key=next_row
                )

        # Parse VatInfo elements
        for vat_elem in vat_info_elements:
            try:
                # Get Mark (try both cases)
                mark_str = self._get_xml_text_flexible(vat_elem, 'Mark', ns)
                if not mark_str:
                    mark_str = self._get_xml_text_flexible(vat_elem, 'mark', ns)
                mark = int(mark_str) if mark_str else 0

                # Get IsCancelled
                is_cancelled_str = self._get_xml_text_flexible(vat_elem, 'IsCancelled', ns)
                if not is_cancelled_str:
                    is_cancelled_str = self._get_xml_text_flexible(vat_elem, 'isCancelled', ns)
                is_cancelled = self._parse_bool(is_cancelled_str or 'false')

                # Get IssueDate
                issue_date_str = self._get_xml_text_flexible(vat_elem, 'IssueDate', ns)
                if not issue_date_str:
                    issue_date_str = self._get_xml_text_flexible(vat_elem, 'issueDate', ns)
                issue_date = self._parse_date(issue_date_str) if issue_date_str else None

                # ΕΚΡΟΕΣ (Έσοδα/Πωλήσεις):
                #   Vat303 = Καθαρή αξία εκροών
                #   Vat333 = ΦΠΑ εκροών
                vat303 = self._get_xml_text_flexible(vat_elem, 'Vat303', ns)
                vat333 = self._get_xml_text_flexible(vat_elem, 'Vat333', ns)

                has_ekroes = vat303 or vat333

                if has_ekroes:
                    net_value = self._parse_decimal(vat303) if vat303 else Decimal('0')
                    vat_amount = self._parse_decimal(vat333) if vat333 else Decimal('0')

                    record = VatInfoRecord(
                        mark=mark,
                        is_cancelled=is_cancelled,
                        issue_date=issue_date,
                        rec_type=1,
                        inv_type='ΕΚΡΟΕΣ',
                        vat_category=1,
                        vat_exemption_category='',
                        net_value=net_value,
                        vat_amount=vat_amount,
                        counter_vat_number='',
                        vat_offset_amount=None,
                        deductions_amount=None,
                    )
                    records.append(record)

                # ΕΙΣΡΟΕΣ — όλοι οι κωδικοί ΑΑΔΕ (361-366 / 381-386)
                eisroes_categories = [
                    ('361', '381'),  # Εμπορεύματα & Α' Ύλες
                    ('362', '382'),  # Πάγια
                    ('363', '383'),  # Λοιπές Δαπάνες
                    ('364', '384'),  # Ενδοκοιν. Εμπορεύματα
                    ('365', '385'),  # Ενδοκοιν. Πάγια
                    ('366', '386'),  # Ενδοκοιν. Λοιπές Δαπάνες
                ]

                eisroes_sub_idx = 0
                for net_code, vat_code in eisroes_categories:
                    net_val = self._get_xml_text_flexible(vat_elem, f'Vat{net_code}', ns)
                    vat_val = self._get_xml_text_flexible(vat_elem, f'Vat{vat_code}', ns)
                    net_unclass = self._get_xml_text_flexible(vat_elem, f'VatUnclassified{net_code}', ns)
                    vat_unclass = self._get_xml_text_flexible(vat_elem, f'VatUnclassified{vat_code}', ns)

                    cat_net = Decimal('0')
                    cat_vat = Decimal('0')
                    if net_val:
                        cat_net += self._parse_decimal(net_val)
                    if net_unclass:
                        cat_net += self._parse_decimal(net_unclass)
                    if vat_val:
                        cat_vat += self._parse_decimal(vat_val)
                    if vat_unclass:
                        cat_vat += self._parse_decimal(vat_unclass)

                    if cat_net or cat_vat:
                        eisroes_sub_idx += 1
                        record = VatInfoRecord(
                            mark=mark + eisroes_sub_idx if mark and (has_ekroes or eisroes_sub_idx > 1) else mark,
                            is_cancelled=is_cancelled,
                            issue_date=issue_date,
                            rec_type=2,
                            inv_type=f'ΕΙΣΡΟΕΣ_{net_code}',
                            vat_category=1,
                            vat_exemption_category='',
                            net_value=cat_net,
                            vat_amount=cat_vat,
                            counter_vat_number='',
                            vat_offset_amount=None,
                            deductions_amount=None,
                            expense_category=net_code,
                        )
                        records.append(record)

                # Skip records with no VAT data (empty invoices/cancelled)

            except Exception as e:
                logger.error(f"Error parsing VatInfo element: {e}")
                logger.debug(f"Element: {ET.tostring(vat_elem, encoding='unicode')[:500]}")
                continue

        return records, pagination

    def _get_xml_text_flexible(self, elem, tag: str, ns: dict) -> Optional[str]:
        """Get text from XML element, trying with namespace and without."""
        # Try with namespace
        child = elem.find(f'aade:{tag}', ns)
        if child is not None and child.text:
            return child.text.strip()

        # Try without namespace
        child = elem.find(tag)
        if child is not None and child.text:
            return child.text.strip()

        # Try finding by local name (handles any namespace)
        for c in elem:
            if c.tag.endswith(tag) or c.tag == tag:
                if c.text:
                    return c.text.strip()

        return None

    def fetch_all_vat_info(
        self,
        date_from: Union[date, datetime],
        date_to: Union[date, datetime],
        entity_vat_number: Optional[str] = None,
        grouped_per_day: bool = False
    ) -> List[VatInfoRecord]:
        """
        Convenience method: Fetch all VAT info records as a list.

        Για μικρό αριθμό records. Για μεγάλα datasets χρησιμοποίησε
        το generator request_vat_info() για memory efficiency.

        Returns:
            List[VatInfoRecord]
        """
        return list(self.request_vat_info(
            date_from=date_from,
            date_to=date_to,
            entity_vat_number=entity_vat_number,
            grouped_per_day=grouped_per_day
        ))

    # =========================================================================
    # REQUEST MY INCOME / EXPENSES
    # =========================================================================

    def request_my_income(
        self,
        date_from: Union[date, datetime],
        date_to: Union[date, datetime],
        counter_vat_number: Optional[str] = None,
        entity_vat_number: Optional[str] = None,
        inv_type: Optional[str] = None
    ) -> Generator[Dict, None, PaginationInfo]:
        """
        Λήψη σύνοψης εσόδων.

        Args:
            date_from: Από ημερομηνία (required)
            date_to: Έως ημερομηνία (required)
            counter_vat_number: ΑΦΜ αντισυμβαλλόμενου
            entity_vat_number: ΑΦΜ οντότητας
            inv_type: Τύπος παραστατικού

        Yields:
            Dict με income data
        """
        params = {
            'dateFrom': self._format_date(date_from),
            'dateTo': self._format_date(date_to),
        }

        if counter_vat_number:
            params['counterVatNumber'] = counter_vat_number
        if entity_vat_number:
            params['entityVatNumber'] = entity_vat_number
        if inv_type:
            params['invType'] = inv_type

        next_partition_key = None
        next_row_key = None

        while True:
            if next_partition_key:
                params['nextPartitionKey'] = next_partition_key
            if next_row_key:
                params['nextRowKey'] = next_row_key

            response = self._make_request('GET', '/RequestMyIncome', params=params)
            records, pagination = self._parse_income_expense_response(response, 'income')

            for record in records:
                yield record

            if not pagination.has_more:
                return pagination

            next_partition_key = pagination.next_partition_key
            next_row_key = pagination.next_row_key

    def request_my_expenses(
        self,
        date_from: Union[date, datetime],
        date_to: Union[date, datetime],
        counter_vat_number: Optional[str] = None,
        entity_vat_number: Optional[str] = None,
        inv_type: Optional[str] = None
    ) -> Generator[Dict, None, PaginationInfo]:
        """
        Λήψη σύνοψης εξόδων.

        Args:
            date_from: Από ημερομηνία (required)
            date_to: Έως ημερομηνία (required)
            counter_vat_number: ΑΦΜ αντισυμβαλλόμενου
            entity_vat_number: ΑΦΜ οντότητας
            inv_type: Τύπος παραστατικού

        Yields:
            Dict με expense data
        """
        params = {
            'dateFrom': self._format_date(date_from),
            'dateTo': self._format_date(date_to),
        }

        if counter_vat_number:
            params['counterVatNumber'] = counter_vat_number
        if entity_vat_number:
            params['entityVatNumber'] = entity_vat_number
        if inv_type:
            params['invType'] = inv_type

        next_partition_key = None
        next_row_key = None

        while True:
            if next_partition_key:
                params['nextPartitionKey'] = next_partition_key
            if next_row_key:
                params['nextRowKey'] = next_row_key

            response = self._make_request('GET', '/RequestMyExpenses', params=params)
            records, pagination = self._parse_income_expense_response(response, 'expenses')

            for record in records:
                yield record

            if not pagination.has_more:
                return pagination

            next_partition_key = pagination.next_partition_key
            next_row_key = pagination.next_row_key

    def _parse_income_expense_response(
        self,
        response: str,
        response_type: str
    ) -> tuple[List[Dict], PaginationInfo]:
        """Parse XML response από RequestMyIncome/RequestMyExpenses"""
        records = []
        pagination = PaginationInfo(has_more=False)

        if not response or not isinstance(response, str):
            return records, pagination

        try:
            root = ET.fromstring(response)
        except ET.ParseError as e:
            logger.error(f"XML Parse Error in {response_type} response: {e}")
            return records, pagination

        # Parse continuation token
        continuation = root.find('continuationToken')
        if continuation is not None:
            next_partition = self._get_xml_text(continuation, 'nextPartitionKey')
            next_row = self._get_xml_text(continuation, 'nextRowKey')

            if next_partition or next_row:
                pagination = PaginationInfo(
                    has_more=True,
                    next_partition_key=next_partition,
                    next_row_key=next_row
                )

        # Parse income/expense elements
        tag_name = 'incomeInfo' if response_type == 'income' else 'expensesInfo'
        for elem in root.findall(tag_name):
            record = {}
            for child in elem:
                record[child.tag] = child.text
            records.append(record)

        return records, pagination

    # =========================================================================
    # REQUEST DOCS (EXISTING METHODS - ENHANCED)
    # =========================================================================

    def request_docs(
        self,
        date_from: Optional[Union[date, datetime]] = None,
        date_to: Optional[Union[date, datetime]] = None,
        mark: Optional[int] = None,
        counter_vat_number: Optional[str] = None,
        inv_type: Optional[str] = None,
        max_mark: Optional[int] = None
    ) -> str:
        """
        Λήψη παραστατικών που έχεις ΛΑΒΕΙ (από προμηθευτές).

        Args:
            date_from: Από ημερομηνία
            date_to: Έως ημερομηνία
            mark: Συγκεκριμένο MARK (ξεκινάμε από 0 για όλα)
            counter_vat_number: ΑΦΜ εκδότη
            inv_type: Τύπος παραστατικού
            max_mark: Μέγιστο mark για pagination

        Returns:
            XML response string
        """
        params = {}

        if mark is not None:
            params['mark'] = mark
        else:
            params['mark'] = 0

        if date_from:
            params['dateFrom'] = self._format_date(date_from)
        if date_to:
            params['dateTo'] = self._format_date(date_to)
        if counter_vat_number:
            params['counterVatNumber'] = counter_vat_number
        if inv_type:
            params['invType'] = inv_type
        if max_mark:
            params['maxMark'] = max_mark

        return self._make_request('GET', '/RequestDocs', params=params)

    def request_transmitted_docs(
        self,
        date_from: Optional[Union[date, datetime]] = None,
        date_to: Optional[Union[date, datetime]] = None,
        mark: Optional[int] = None,
        max_mark: Optional[int] = None
    ) -> str:
        """
        Λήψη παραστατικών που έχεις ΣΤΕΙΛΕΙ (εκδώσει).

        Args:
            date_from: Από ημερομηνία
            date_to: Έως ημερομηνία
            mark: Συγκεκριμένο MARK
            max_mark: Μέγιστο mark για pagination

        Returns:
            XML response string
        """
        params = {}

        if mark is not None:
            params['mark'] = mark

        if date_from:
            params['dateFrom'] = self._format_date(date_from)
        if date_to:
            params['dateTo'] = self._format_date(date_to)
        if max_mark:
            params['maxMark'] = max_mark

        return self._make_request('GET', '/RequestTransmittedDocs', params=params)

    # =========================================================================
    # SEND / CANCEL INVOICES
    # =========================================================================

    def send_invoices(self, invoices_data: List[Dict]) -> Dict:
        """
        Αποστολή παραστατικών στο myDATA.

        Args:
            invoices_data: List με invoice objects

        Returns:
            Dict με response (περιέχει MARK για κάθε παραστατικό)
        """
        self.session.headers['Content-Type'] = 'application/json'
        payload = {"invoices": invoices_data}
        return self._make_request('POST', '/SendInvoices', json=payload)

    def cancel_invoice(self, mark: int) -> Dict:
        """
        Ακύρωση παραστατικού.

        Args:
            mark: Το MARK του παραστατικού προς ακύρωση

        Returns:
            Dict με response
        """
        self.session.headers['Content-Type'] = 'application/json'
        payload = {
            "cancellationMark": mark,
            "cancellationDate": self._format_date(datetime.now())
        }
        return self._make_request('POST', '/CancelInvoice', json=payload)

    # =========================================================================
    # LEGACY PARSER (για backwards compatibility)
    # =========================================================================

    def parse_invoice_response(self, response) -> List[Dict]:
        """
        Parse response από RequestDocs/RequestTransmittedDocs.
        Supports both JSON and XML responses.

        LEGACY METHOD - Kept for backwards compatibility

        Returns:
            List με normalized invoices
        """
        invoices = []

        if isinstance(response, str):
            # XML response
            ns = {'ns': 'http://www.aade.gr/myDATA/invoice/v1.0'}

            try:
                root = ET.fromstring(response)

                for inv_elem in root.findall('.//ns:invoice', ns):
                    issuer = inv_elem.find('.//ns:issuer', ns)
                    issuer_vat = None
                    if issuer is not None:
                        vat_elem = issuer.find('ns:vatNumber', ns)
                        if vat_elem is not None:
                            issuer_vat = vat_elem.text

                    counterpart = inv_elem.find('.//ns:counterpart', ns)
                    counterpart_vat = None
                    if counterpart is not None:
                        vat_elem = counterpart.find('ns:vatNumber', ns)
                        if vat_elem is not None:
                            counterpart_vat = vat_elem.text

                    header = inv_elem.find('.//ns:invoiceHeader', ns)
                    if header is None:
                        continue

                    def get_text(parent, tag):
                        elem = parent.find(f'ns:{tag}', ns)
                        return elem.text if elem is not None else ''

                    summary = inv_elem.find('.//ns:invoiceSummary', ns)
                    total_net = total_vat = total_gross = 0
                    if summary is not None:
                        total_net = float(get_text(summary, 'totalNetValue') or 0)
                        total_vat = float(get_text(summary, 'totalVatAmount') or 0)
                        total_gross = float(get_text(summary, 'totalGrossValue') or 0)

                    invoices.append({
                        'mark': None,
                        'uid': None,
                        'issuer_vat': issuer_vat,
                        'counterpart_vat': counterpart_vat,
                        'series': get_text(header, 'series'),
                        'aa': get_text(header, 'aa'),
                        'issue_date': get_text(header, 'issueDate'),
                        'invoice_type': get_text(header, 'invoiceType'),
                        'total_net': total_net,
                        'total_vat': total_vat,
                        'total_gross': total_gross,
                        'details': []
                    })

            except ET.ParseError as e:
                logger.error(f"XML Parse Error: {e}")
                return []

        elif isinstance(response, dict) and 'invoices' in response:
            # JSON response
            for inv in response['invoices']:
                invoices.append({
                    'mark': inv.get('mark'),
                    'uid': inv.get('uid'),
                    'issuer_vat': inv.get('issuer', {}).get('vatNumber'),
                    'counterpart_vat': inv.get('counterpart', {}).get('vatNumber'),
                    'series': inv.get('invoiceHeader', {}).get('series'),
                    'aa': inv.get('invoiceHeader', {}).get('aa'),
                    'issue_date': inv.get('invoiceHeader', {}).get('issueDate'),
                    'invoice_type': inv.get('invoiceHeader', {}).get('invoiceType'),
                    'total_net': inv.get('invoiceSummary', {}).get('totalNetValue'),
                    'total_vat': inv.get('invoiceSummary', {}).get('totalVatAmount'),
                    'total_gross': inv.get('invoiceSummary', {}).get('totalGrossValue'),
                    'details': inv.get('invoiceDetails', [])
                })

        return invoices
