# -*- coding: utf-8 -*-
"""
Γύρος 20 — διόρθωση του αποτελέσματος του 10020 για legacy duplicates.

Το 10020 έδωσε `legacy-{id}` slot ΜΟΝΟ στο duplicate current row. Οι
προηγούμενες εκδόσεις της ίδιας version chain έμειναν σε slot='' — άρα η
ακμή current→previous έγινε cross-key, και μια μελλοντική διαγραφή του
current με προαγωγή της προηγούμενης θα συγκρουόταν με το κύριο slot=''.

Αυτό το migration:
1. Εντοπίζει κάθε chain που περιέχει row με slot που αρχίζει από 'legacy-'.
2. Διατρέχει ΟΛΟΚΛΗΡΗ τη chain (και προς τα πίσω μέσω previous_version και
   προς τα εμπρός μέσω των children) με ΑΣΦΑΛΗ iterative traversal και
   visited-set cycle guard — καμία recursion.
3. Εφαρμόζει το ΙΔΙΟ slot σε όλα τα μέλη της chain (deterministic: το slot
   που αντιστοιχεί στο μικρότερο id της chain, `legacy-{min_id}`).
4. Δεν ακολουθεί ποτέ ακμή προς άλλον client (malformed cross-client edge):
   η διάσχιση σταματά εκεί και η chain σημειώνεται ως «αμφίβολη».
5. Malformed/cyclic/cross-client chains ΔΕΝ «διορθώνονται» σιωπηλά —
   παίρνουν και αυτές legacy slot (ώστε να μην παραβιάζουν το constraint)
   αλλά αναφέρονται από το audit command ως legacy-slot-needs-review.

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


def _fix_legacy_chains(apps, schema_editor):
    ClientDocument = apps.get_model('accounting', 'ClientDocument')

    rows = {
        r['id']: r
        for r in ClientDocument.objects.values(
            'id', 'previous_version_id', 'client_id', 'slot',
            'document_category', 'year', 'month', 'obligation_id',
            'is_current').order_by('id')
    }
    if not rows:
        return

    children = {}
    for doc_id, r in rows.items():
        prev = r['previous_version_id']
        if prev is not None:
            children.setdefault(prev, []).append(doc_id)

    # 1) Κάθε logical key (αγνοώντας slot) με >1 current rows είναι
    # «αμφίβολο»: ΟΛΕΣ οι chains του παίρνουν legacy slot, το '' μένει
    # ελεύθερο (βλ. πολιτική στο docstring).
    key_currents = {}
    for r in rows.values():
        if r['is_current']:
            key = (r['client_id'], r['document_category'], r['year'],
                   r['month'], r['obligation_id'])
            key_currents.setdefault(key, []).append(r['id'])

    seed_ids = set()
    for key, ids in key_currents.items():
        if len(ids) > 1:
            seed_ids.update(ids)
    # Επιπλέον seeds: ό,τι ήδη έχει legacy slot από το 10020
    for r in rows.values():
        if (r['slot'] or '').startswith('legacy-'):
            seed_ids.add(r['id'])

    if not seed_ids:
        return

    # 2) Iterative traversal ΟΛΟΚΛΗΡΗΣ της chain κάθε seed (πίσω+εμπρός),
    # με visited guard (cycle safe) και χωρίς cross-client ακμές.
    assigned = {}          # doc_id -> slot
    globally_seen = set()
    for seed in sorted(seed_ids):
        if seed in globally_seen:
            continue
        component = set()
        stack = [seed]
        client_id = rows[seed]['client_id']
        while stack:
            node = stack.pop()
            if node in component:
                continue          # cycle guard
            component.add(node)
            prev = rows[node]['previous_version_id']
            if prev is not None and prev in rows \
                    and prev not in component \
                    and rows[prev]['client_id'] == client_id:
                stack.append(prev)
            for child in children.get(node, []):
                if child in rows and child not in component \
                        and rows[child]['client_id'] == client_id:
                    stack.append(child)
        globally_seen |= component
        slot_value = f'legacy-{min(component)}'
        for node in component:
            assigned[node] = slot_value

    # 3) Deterministic εφαρμογή (ταξινομημένα ids· idempotent ως προς το
    # τελικό αποτέλεσμα — δεύτερη εκτέλεση δίνει τα ίδια slots)
    for doc_id in sorted(assigned):
        if rows[doc_id]['slot'] != assigned[doc_id]:
            ClientDocument.objects.filter(pk=doc_id).update(
                slot=assigned[doc_id])


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '10020_clientdocument_slot_and_current_constraints'),
    ]

    operations = [
        migrations.RunPython(_fix_legacy_chains, migrations.RunPython.noop),
    ]
