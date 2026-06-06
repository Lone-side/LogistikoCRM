# -*- coding: utf-8 -*-
"""
Regression: inventory correctness fixes
=======================================
1. StockMovement edit για ADJ κινήσεις διόρθωνε λάθος το stock (ο edit path δεν
   αντέστρεφε/εφάρμοζε το ADJ → μόνιμο drift).
2. InvoiceItem VAT/net δεν γινόταν quantize → τα invoice totals απέκλιναν από
   το άθροισμα των (στρογγυλοποιημένων) γραμμών.
3. Διαγραφή InvoiceItem δεν ξαναϋπολόγιζε τα invoice totals (post_delete).
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from inventory.models import Product, StockMovement, Invoice, InvoiceItem


def _product(code="P1", stock="0.000"):
    return Product.objects.create(
        code=code, name="Προϊόν", unit="piece",
        current_stock=Decimal(stock), min_stock=Decimal("0.000"),
        purchase_price=Decimal("1.00"), sale_price=Decimal("2.00"),
    )


class StockMovementAdjEditTest(TestCase):
    def test_editing_adj_movement_corrects_stock(self):
        p = _product(stock="10.000")
        # ADJ +5 → stock 15
        mv = StockMovement.objects.create(product=p, movement_type="ADJ", quantity=Decimal("5.000"))
        p.refresh_from_db()
        self.assertEqual(p.current_stock, Decimal("15.000"))

        # Edit το ADJ σε +2: undo old (+5 → -5) → 10, apply new (+2) → 12
        mv.quantity = Decimal("2.000")
        mv.save()
        p.refresh_from_db()
        self.assertEqual(p.current_stock, Decimal("12.000"))

    def test_changing_type_from_adj_to_out(self):
        p = _product(stock="10.000")
        mv = StockMovement.objects.create(product=p, movement_type="ADJ", quantity=Decimal("5.000"))
        p.refresh_from_db()
        self.assertEqual(p.current_stock, Decimal("15.000"))
        # ADJ(+5) → OUT(3): undo +5 → 10, apply OUT -3 → 7
        mv.movement_type = "OUT"
        mv.quantity = Decimal("3.000")
        mv.save()
        p.refresh_from_db()
        self.assertEqual(p.current_stock, Decimal("7.000"))


class InvoiceTotalsTest(TestCase):
    def _invoice(self, number="1"):
        return Invoice.objects.create(
            series="A", number=number, invoice_type="1.1",
            issue_date=date(2026, 5, 1), counterpart=None if False else self._cp(),
            counterpart_vat="123456789", counterpart_name="Πελάτης",
        )

    def _cp(self):
        from accounting.models import ClientProfile
        cp, _ = ClientProfile.objects.get_or_create(
            afm="123456783", defaults={"eponimia": "Π", "eidos_ipoxreou": "company"}
        )
        return cp

    def test_invoice_item_values_are_quantized(self):
        inv = self._invoice()
        # quantity 0.100 * unit_price 0.10 = 0.010 → net θα γίνει 0.01 (quantized)
        item = InvoiceItem.objects.create(
            invoice=inv, line_number=1, description="x",
            quantity=Decimal("0.100"), unit="piece", unit_price=Decimal("0.10"),
            vat_category=1,
        )
        item.refresh_from_db()
        self.assertEqual(item.net_value.as_tuple().exponent, -2)  # ακριβώς 2 δεκαδικά
        self.assertEqual(item.vat_amount.as_tuple().exponent, -2)

    def test_invoice_total_matches_sum_of_lines(self):
        inv = self._invoice()
        for i in range(3):
            InvoiceItem.objects.create(
                invoice=inv, line_number=i + 1, description="x",
                quantity=Decimal("1.000"), unit="piece", unit_price=Decimal("10.00"),
                vat_category=1,  # 24%
            )
        inv.refresh_from_db()
        lines = inv.items.all()
        self.assertEqual(inv.total_net, sum(l.net_value for l in lines))
        self.assertEqual(inv.total_vat, sum(l.vat_amount for l in lines))
        self.assertEqual(inv.total_gross, inv.total_net + inv.total_vat)

    def test_deleting_item_recalculates_totals(self):
        inv = self._invoice()
        a = InvoiceItem.objects.create(
            invoice=inv, line_number=1, description="a",
            quantity=Decimal("1.000"), unit="piece", unit_price=Decimal("10.00"),
            vat_category=1,
        )
        InvoiceItem.objects.create(
            invoice=inv, line_number=2, description="b",
            quantity=Decimal("1.000"), unit="piece", unit_price=Decimal("20.00"),
            vat_category=1,
        )
        inv.refresh_from_db()
        self.assertEqual(inv.total_net, Decimal("30.00"))
        # Διαγραφή της 1ης γραμμής → totals πρέπει να ξαναϋπολογιστούν (post_delete)
        a.delete()
        inv.refresh_from_db()
        self.assertEqual(inv.total_net, Decimal("20.00"))
        self.assertEqual(inv.total_vat, Decimal("4.80"))
        self.assertEqual(inv.total_gross, Decimal("24.80"))
