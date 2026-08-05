# -*- coding: utf-8 -*-
"""
Γύρος 20/21 — διόρθωση του αποτελέσματος του 10020 για legacy duplicates.

Το 10020 έδωσε `legacy-{id}` slot ΜΟΝΟ στο duplicate current row. Οι
προηγούμενες εκδόσεις της ίδιας version chain έμειναν σε slot='' — άρα η
ακμή current→previous έγινε cross-key, και μια μελλοντική διαγραφή του
current με προαγωγή της προηγούμενης θα συγκρουόταν με το κύριο slot=''.

Αυτό το migration:
1. Εντοπίζει (με στοχευμένα queries, ΟΧΙ full table scan) τα «αμφίβολα»
   rows: όσα έχουν ήδη slot `legacy-%` από το 10020, και τα current rows
   των logical keys που έχουν >1 current (GROUP BY ... HAVING στη βάση).
2. Διατρέχει ΜΟΝΟ τα components αυτών των seeds (πίσω μέσω
   previous_version και εμπρός μέσω των children) με ΑΣΦΑΛΗ iterative
   BFS και visited-set cycle guard — καμία recursion, κανένα φόρτωμα
   ολόκληρου του πίνακα στη μνήμη.
3. Εφαρμόζει το ΙΔΙΟ slot σε όλα τα μέλη της chain (deterministic: το slot
   που αντιστοιχεί στο μικρότερο id της chain, `legacy-{min_id}`).
4. Δεν ακολουθεί ποτέ ακμή προς άλλον client (malformed cross-client edge):
   η διάσχιση σταματά εκεί και η chain σημειώνεται ως «αμφίβολη».

ΑΣΦΑΛΕΙΑ ΕΝΑΝΤΙ CONSTRAINT VIOLATION (Γύρος 21 — P0):
Ένα component μπορεί να περιέχει ΠΑΝΩ ΑΠΟ ΕΝΑ `is_current=True` row —
π.χ. branching chain όπου δύο παιδιά του ίδιου root είναι και τα δύο
current, ή ancestor+descendant που έμειναν και οι δύο current. Το 10020
έχει ήδη δώσει σε αυτά ΔΙΑΦΟΡΕΤΙΚΑ slots, ώστε να ισχύουν τα unique
constraints. Αν το 10021 τους έδινε κοινό slot θα παραβίαζε το
`uniq_current_doc_*` και το migrate θα σταματούσε με IntegrityError στη
μέση του deployment.

Πολιτική: **component με >1 current ΔΕΝ αγγίζεται καθόλου.** Δεν
μαντεύουμε ποιο branch είναι το σωστό — διατηρείται η constraint-safe
κατάσταση του 10020 και η χειροκίνητη διόρθωση καθοδηγείται από τα
findings του `audit_clientdocument_invariants` (`branching-chain`,
`multiple-current-in-chain`, `cross-key-previous-version`,
`legacy-slot-needs-review`).

ΠΟΛΙΤΙΚΗ ΕΠΙΛΟΓΗΣ ΚΥΡΙΟΥ SLOT (trade-off, τεκμηριωμένο):
Το migration ΔΕΝ μπορεί να γνωρίζει ποιο legacy document είναι το
«πραγματικό» κύριο έγγραφο του γραφείου — το μικρότερο id δεν το
αποδεικνύει. Επιλέγεται η ΑΣΦΑΛΕΣΤΕΡΗ πολιτική: **όλες** οι chains ενός
αμφίβολου (duplicate) logical key παίρνουν legacy slot και το slot=''
μένει ΕΛΕΥΘΕΡΟ για το επόμενο επιβεβαιωμένο office upload. Έτσι κανένα
μελλοντικό version/replace δεν μπορεί να χτυπήσει κατά λάθος το λάθος
legacy document. Κόστος: το πρώτο νέο upload στο key δημιουργεί νέο v1
αντί να γίνει version πάνω σε υπάρχον — αποδεκτό, γιατί το ποιο ήταν το
σωστό «προηγούμενο» είναι ούτως ή άλλως άγνωστο και πρέπει να
επιβεβαιωθεί χειροκίνητα (βλ. audit finding legacy-slot-needs-review).
"""
from django.db import migrations
from django.db.models import Count

# Πόσα ids ανά query κατά τη διάσχιση (bounded memory/SQL size)
_CHUNK = 500

_FIELDS = ('id', 'previous_version_id', 'client_id', 'slot', 'is_current')


def _rows_by_ids(manager, ids):
    """Φόρτωση συγκεκριμένων rows σε chunks."""
    out = {}
    ids = list(ids)
    for i in range(0, len(ids), _CHUNK):
        for r in manager.filter(pk__in=ids[i:i + _CHUNK]).values(*_FIELDS):
            out[r['id']] = r
    return out


def _children_of(manager, ids):
    """Τα rows που δείχνουν (previous_version) σε κάποιο από τα ids."""
    out = {}
    ids = list(ids)
    for i in range(0, len(ids), _CHUNK):
        for r in manager.filter(
                previous_version_id__in=ids[i:i + _CHUNK]).values(*_FIELDS):
            out[r['id']] = r
    return out


def _collect_seed_ids(manager):
    """
    Στοχευμένος εντοπισμός αμφίβολων rows — ΧΩΡΙΣ full table load:
    (α) ό,τι έχει ήδη legacy slot από το 10020,
    (β) τα current rows των logical keys με >1 current (GROUP BY στη βάση).
    """
    seeds = set(manager.filter(slot__startswith='legacy-')
                .values_list('id', flat=True))

    dup_keys = (manager.filter(is_current=True)
                .values('client_id', 'document_category', 'year', 'month',
                        'obligation_id')
                .annotate(n=Count('id')).filter(n__gt=1))
    for key in dup_keys:
        seeds.update(
            manager.filter(
                is_current=True,
                client_id=key['client_id'],
                document_category=key['document_category'],
                year=key['year'], month=key['month'],
                obligation_id=key['obligation_id'],
            ).values_list('id', flat=True)
        )
    return seeds


def _fix_legacy_chains(apps, schema_editor):
    ClientDocument = apps.get_model('accounting', 'ClientDocument')
    manager = ClientDocument.objects

    seed_ids = _collect_seed_ids(manager)
    if not seed_ids:
        return

    known = _rows_by_ids(manager, seed_ids)
    assigned = {}          # doc_id -> slot
    globally_seen = set()

    for seed in sorted(seed_ids):
        if seed in globally_seen:
            continue
        client_id = known[seed]['client_id']
        component = {seed}
        frontier = {seed}
        # Iterative BFS (cycle safe μέσω του `component` visited set),
        # bounded στα rows του συγκεκριμένου component
        while frontier:
            prev_ids = {known[n]['previous_version_id'] for n in frontier
                        if known[n]['previous_version_id'] is not None}
            prev_ids -= component
            parents = _rows_by_ids(manager, prev_ids) if prev_ids else {}
            kids = _children_of(manager, frontier)

            next_frontier = set()
            for row in list(parents.values()) + list(kids.values()):
                node = row['id']
                if node in component:
                    continue
                # ΠΟΤΕ cross-client traversal
                if row['client_id'] != client_id:
                    continue
                known[node] = row
                component.add(node)
                next_frontier.add(node)
            frontier = next_frontier

        globally_seen |= component

        # === Γύρος 21 (P0): component με >1 current ΔΕΝ αγγίζεται ===
        # Το 10020 του έχει ήδη δώσει constraint-safe διαφορετικά slots·
        # κοινό slot εδώ θα παραβίαζε το uniq_current_doc_* και θα
        # τερμάτιζε το migrate με IntegrityError. Ποιο branch είναι το
        # σωστό δεν είναι γνωστό — το αναφέρει το audit command.
        currents = [n for n in component if known[n]['is_current']]
        if len(currents) > 1:
            continue

        slot_value = f'legacy-{min(component)}'
        for node in component:
            assigned[node] = slot_value

    # Deterministic εφαρμογή (ταξινομημένα ids· idempotent ως προς το
    # τελικό αποτέλεσμα — δεύτερη εκτέλεση δίνει τα ίδια slots)
    for doc_id in sorted(assigned):
        if known[doc_id]['slot'] != assigned[doc_id]:
            manager.filter(pk=doc_id).update(slot=assigned[doc_id])


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '10020_clientdocument_slot_and_current_constraints'),
    ]

    operations = [
        migrations.RunPython(_fix_legacy_chains, migrations.RunPython.noop),
    ]
