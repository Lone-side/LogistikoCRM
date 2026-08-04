# -*- coding: utf-8 -*-
"""
Έλεγχος ιστορικών ασυνεπειών στα ClientDocument rows.

Το model save guard δεν καλύπτει παλιά rows, QuerySet.update, bulk
operations ή direct SQL — αυτό το command σαρώνει τη βάση και αναφέρει:

1. document.client_id != obligation.client_id (cross-client edge)
2. document.client_id != previous_version.client_id (cross-client edge)
3. Κύκλους στο version graph (self-reference, 2-node, 3+ node) —
   iterative traversal με visited/visiting state, ΟΧΙ ακολούθηση
   previous_version χωρίς cycle guard
4. Περισσότερα από ένα current documents στην ίδια αλυσίδα/συστάδα
   (siblings, non-adjacent descendants — μέσω connected components)
5. Branching chains (δύο documents με το ίδιο previous_version)
6. Invalid version progression (doc.version != prev.version + 1)
7. Duplicate current rows στο ίδιο exact logical conflict key
   (client, document_category, year, month, obligation)

Report-only by design: ΔΕΝ γίνεται αυτόματη επανάθεση/διόρθωση — η
διόρθωση είναι χειροκίνητη (fail closed). Στα ευρήματα μπαίνουν ΜΟΝΟ
internal IDs — ποτέ ΑΦΜ ή ονόματα αρχείων.

Χρήση σε deployment checks: --fail-on-findings → exit code != 0 (CommandError).
"""
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db.models import F

from accounting.models import ClientDocument


class Command(BaseCommand):
    help = ("Αναφέρει ClientDocument rows που παραβιάζουν τα cross-client/"
            "version-graph invariants (report-only, χειροκίνητη διόρθωση)")

    def add_arguments(self, parser):
        parser.add_argument(
            '--fail-on-findings', action='store_true',
            help='Exit με σφάλμα αν βρεθούν ασυνέπειες (για CI/deploy checks)',
        )

    def handle(self, *args, **options):
        findings = []

        # 1. Cross-client obligation
        for doc in (ClientDocument.objects
                    .filter(obligation__isnull=False)
                    .exclude(obligation__client_id=F('client_id'))
                    .values('id', 'client_id', 'obligation_id',
                            'obligation__client_id')):
            findings.append(
                f"cross-client-obligation: document id={doc['id']} "
                f"client id={doc['client_id']} ↔ obligation "
                f"id={doc['obligation_id']} (client id="
                f"{doc['obligation__client_id']})"
            )

        # 2. Cross-client previous_version
        for doc in (ClientDocument.objects
                    .filter(previous_version__isnull=False)
                    .exclude(previous_version__client_id=F('client_id'))
                    .values('id', 'client_id', 'previous_version_id',
                            'previous_version__client_id')):
            findings.append(
                f"cross-client-previous-version: document id={doc['id']} "
                f"client id={doc['client_id']} ↔ previous id="
                f"{doc['previous_version_id']} (client id="
                f"{doc['previous_version__client_id']})"
            )

        # === Version graph: φόρτωση σε μνήμη για ασφαλή ανάλυση ===
        rows = list(ClientDocument.objects.values(
            'id', 'previous_version_id', 'is_current', 'version',
            'client_id', 'document_category', 'year', 'month',
            'obligation_id', 'slot').order_by('id'))
        prev_of = {r['id']: r['previous_version_id'] for r in rows}
        info = {r['id']: r for r in rows}

        # 3. Κύκλοι: iterative traversal με τρι-κατάστατο visited
        # (0=unvisited, 1=visiting, 2=done) — cycle guard, όχι recursion
        state = {}
        cycle_nodes = set()
        for start in prev_of:
            if state.get(start):
                continue
            path = []
            node = start
            while node is not None and node in prev_of:
                st = state.get(node, 0)
                if st == 2:
                    break
                if st == 1:
                    # Κύκλος: όλα τα nodes από την πρώτη εμφάνιση του node
                    idx = path.index(node)
                    cycle_nodes.update(path[idx:])
                    break
                state[node] = 1
                path.append(node)
                node = prev_of[node]
            for n in path:
                state[n] = 2
        for n in sorted(cycle_nodes):
            findings.append(f"version-graph-cycle: document id={n}")

        # 5. Branching: δύο (ή περισσότερα) docs με ίδιο previous_version
        children = defaultdict(list)
        for doc_id, prev_id in prev_of.items():
            if prev_id is not None:
                children[prev_id].append(doc_id)
        for prev_id, kids in sorted(children.items()):
            if len(kids) > 1:
                findings.append(
                    f"branching-chain: previous id={prev_id} έχει "
                    f"{len(kids)} διαδόχους ids={sorted(kids)}"
                )

        # 4. Πολλαπλά current στην ίδια συστάδα (connected component του
        # previous_version graph) — καλύπτει siblings ΚΑΙ non-adjacent
        # descendants. Union-find πάνω στα edges (χωρίς recursion).
        parent = {}

        def find(x):
            root = x
            while parent.get(root, root) != root:
                root = parent[root]
            while parent.get(x, x) != x:
                parent[x], x = root, parent[x]
            return root

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for doc_id, prev_id in prev_of.items():
            if prev_id is not None and prev_id in info:
                union(doc_id, prev_id)
        comp_current = defaultdict(list)
        for r in rows:
            if r['is_current']:
                comp_current[find(r['id'])].append(r['id'])
        for comp, currents in sorted(comp_current.items()):
            if len(currents) > 1:
                findings.append(
                    f"multiple-current-in-chain: ids={sorted(currents)}"
                )

        # 6. Invalid version progression
        for doc_id, prev_id in sorted(prev_of.items()):
            if prev_id is None or prev_id not in info or doc_id in cycle_nodes:
                continue
            if info[doc_id]['version'] != info[prev_id]['version'] + 1:
                findings.append(
                    f"invalid-version-progression: document id={doc_id} "
                    f"(v{info[doc_id]['version']}) ← previous id={prev_id} "
                    f"(v{info[prev_id]['version']})"
                )

        # 7. Duplicate current rows στο exact logical conflict key (με slot)
        by_key = defaultdict(list)
        for r in rows:
            if r['is_current']:
                key = (r['client_id'], r['document_category'], r['year'],
                       r['month'], r['obligation_id'], r['slot'])
                by_key[key].append(r['id'])
        for key, ids in sorted(by_key.items()):
            if len(ids) > 1:
                findings.append(
                    f"duplicate-current-for-key: client id={key[0]} "
                    f"category={key[1]} {key[3]}/{key[2]} obligation "
                    f"id={key[4]} slot={key[5]!r} → ids={sorted(ids)}"
                )

        # 8. Cross-key previous_version edge: η προηγούμενη έκδοση πρέπει
        # να ανήκει στο ΙΔΙΟ exact logical key (client/category/year/
        # month/obligation/slot)
        def _key(r):
            return (r['client_id'], r['document_category'], r['year'],
                    r['month'], r['obligation_id'], r['slot'])

        for doc_id, prev_id in sorted(prev_of.items()):
            if prev_id is None or prev_id not in info:
                continue
            if _key(info[doc_id]) != _key(info[prev_id]):
                findings.append(
                    f"cross-key-previous-version: document id={doc_id} ← "
                    f"previous id={prev_id} (διαφορετικό logical key)"
                )

        # 9. Per-component ανάλυση: zero current, root version != 1,
        # duplicate version numbers, current που δεν είναι terminal,
        # πολλαπλά roots
        comp_members = defaultdict(list)
        for r in rows:
            comp_members[find(r['id'])].append(r['id'])
        has_child = set(children.keys())
        for comp, members in sorted(comp_members.items()):
            member_rows = [info[m] for m in members]
            currents = [r['id'] for r in member_rows if r['is_current']]
            # Zero-current component (chain χωρίς current)
            if len(members) >= 1 and not currents:
                findings.append(
                    f"chain-without-current: ids={sorted(members)}")
            # Current που δεν είναι terminal node (έχει descendants)
            for cid in currents:
                if cid in has_child:
                    findings.append(
                        f"current-not-terminal: document id={cid} έχει "
                        f"νεότερες εκδόσεις")
            # Roots: nodes χωρίς previous (ή previous εκτός DB)
            roots = [r['id'] for r in member_rows
                     if not prev_of.get(r['id'])
                     or prev_of[r['id']] not in info]
            if len(members) > 1 and len(roots) > 1:
                findings.append(
                    f"multiple-roots-in-chain: ids={sorted(roots)}")
            # Root version != 1 (π.χ. orphaned chain μετά από διαγραφή root)
            for rid in roots:
                if len(members) > 1 and info[rid]['version'] != 1 \
                        and rid not in cycle_nodes:
                    findings.append(
                        f"root-version-not-1: document id={rid} "
                        f"(v{info[rid]['version']})")
            # Duplicate version numbers στην ίδια chain
            seen_versions = defaultdict(list)
            for r in member_rows:
                seen_versions[r['version']].append(r['id'])
            if len(members) > 1:
                for v, ids in sorted(seen_versions.items()):
                    if len(ids) > 1:
                        findings.append(
                            f"duplicate-version-in-chain: v{v} → "
                            f"ids={sorted(ids)}")

        # 10. Legacy slots από τα migrations 10020/10021: ΔΕΝ θεωρούνται
        # καθαρά — απαιτούν χειροκίνητη ταξινόμηση/επιβεβαίωση ποιο
        # έγγραφο είναι το πραγματικό κύριο του key. Μία γραμμή ΑΝΑ
        # component (όχι ανά row) για deterministic, μη-θορυβώδες output.
        legacy_components = defaultdict(list)
        for r in rows:
            if (r['slot'] or '').startswith('legacy-'):
                legacy_components[find(r['id'])].append(r['id'])
        for comp, ids in sorted(
                legacy_components.items(), key=lambda kv: min(kv[1])):
            findings.append(
                f"legacy-slot-needs-review: chain ids={sorted(ids)} — "
                f"απαιτείται χειροκίνητη επιβεβαίωση ότι το slot είναι "
                f"σωστό (migration 10020/10021 μετέφερε αμφίβολα duplicate "
                f"currents σε legacy slot· το κύριο slot παραμένει ελεύθερο)"
            )

        if not findings:
            self.stdout.write(self.style.SUCCESS(
                'Κανένα invariant finding — όλα τα ClientDocument συνεπή.'))
            return

        self.stdout.write(self.style.WARNING(
            f'Βρέθηκαν {len(findings)} ασυνέπειες (χειροκίνητη διόρθωση):'))
        for line in findings:
            self.stdout.write(f'  - {line}')

        if options['fail_on_findings']:
            raise CommandError(
                f'{len(findings)} ClientDocument invariant findings')
