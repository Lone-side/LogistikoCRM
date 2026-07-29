#!/bin/bash
# Πλήρης αρχική εγκατάσταση LogistikoCRM για development (Linux/Mac)
# Χρήση: ./setup_dev.sh
# Μετά την ολοκλήρωση: source venv/bin/activate && python manage.py runserver

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "🚀 Αρχική εγκατάσταση LogistikoCRM"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Έλεγχος Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Δεν βρέθηκε python3. Εγκατέστησε Python 3.10+ και ξαναδοκίμασε.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python: $(python3 --version)${NC}"

# 2. Virtual environment
if [ ! -d "venv" ]; then
    echo -e "${BLUE}📦 Δημιουργία virtual environment...${NC}"
    python3 -m venv venv
fi
source venv/bin/activate
echo -e "${GREEN}✅ Virtual environment ενεργό${NC}"

# 3. Dependencies
echo -e "${BLUE}📦 Εγκατάσταση dependencies (μπορεί να πάρει λίγα λεπτά)...${NC}"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo -e "${GREEN}✅ Dependencies εγκαταστάθηκαν${NC}"

# 4. .env από το σωστό template
if [ ! -f ".env" ]; then
    if [ -f ".env.development" ]; then
        cp .env.development .env
        echo -e "${GREEN}✅ Δημιουργήθηκε .env από το .env.development${NC}"
    else
        echo -e "${YELLOW}⚠️  Δεν βρέθηκε .env.development — συνέχεια χωρίς .env (DEBUG defaults)${NC}"
    fi
else
    echo -e "${GREEN}✅ Το .env υπάρχει ήδη${NC}"
fi

# 5. Βάση δεδομένων — Η ΣΕΙΡΑ ΕΧΕΙ ΣΗΜΑΣΙΑ (migrate → createcachetable → setupdata)
echo -e "${BLUE}🗄️  Εκτέλεση migrations...${NC}"
python manage.py migrate

echo -e "${BLUE}🗄️  Δημιουργία cache table...${NC}"
python manage.py createcachetable

# Το setupdata φτιάχνει groups/fixtures + superuser IamSUPER.
# ΠΡΟΣΟΧΗ: όχι createsuperuser πριν από αυτό — χαλάει τα pk των groups.
echo -e "${BLUE}👤 Αρχικοποίηση δεδομένων (groups + superuser IamSUPER)...${NC}"
echo -e "${YELLOW}⚠️  ΣΗΜΕΙΩΣΕ τον κωδικό (PASSWORD) που θα εμφανιστεί παρακάτω!${NC}"
python manage.py setupdata

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Η εγκατάσταση ολοκληρώθηκε!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}Εκκίνηση server:${NC}"
echo "   source venv/bin/activate"
echo "   python manage.py runserver"
echo ""
echo -e "${BLUE}URLs:${NC}"
echo "   • Admin: http://localhost:8000/el/456-admin/"
echo "   • CRM:   http://localhost:8000/el/123/"
echo ""
echo -e "${BLUE}Σύνδεση:${NC} χρήστης IamSUPER (ο κωδικός τυπώθηκε παραπάνω στα SUPERUSER Credentials)"
echo ""
echo -e "${YELLOW}💡 Για Django + React μαζί: ./start_dev.sh${NC}"
