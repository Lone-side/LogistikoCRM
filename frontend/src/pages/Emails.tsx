import { Mail, Send, Inbox, FileText, Search, Plus } from 'lucide-react';
import { Button, Card } from '../components';

export default function Emails() {
  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Email</h1>
          <p className="text-gray-500 mt-1">Διαχείριση email και αυτοματοποιήσεις</p>
        </div>
        <Button>
          <Plus size={18} className="mr-2" />
          Νέο email
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-brand-100 rounded-lg flex items-center justify-center">
              <Inbox size={20} className="text-brand-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Εισερχόμενα</p>
              <p className="text-xl font-bold text-gray-900">156</p>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <Send size={20} className="text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Απεσταλμένα</p>
              <p className="text-xl font-bold text-gray-900">89</p>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-yellow-100 rounded-lg flex items-center justify-center">
              <FileText size={20} className="text-yellow-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Πρόχειρα</p>
              <p className="text-xl font-bold text-gray-900">3</p>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
              <Mail size={20} className="text-purple-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Προγραμματισμένα</p>
              <p className="text-xl font-bold text-gray-900">12</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Main Content */}
      <Card>
        {/* Search Bar */}
        <div className="p-4 border-b border-gray-200">
          <div className="relative">
            <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Αναζήτηση email..."
              className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            />
          </div>
        </div>

        {/* Empty State */}
        <div className="p-12">
          <div className="text-center">
            <div className="w-16 h-16 bg-brand-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Mail size={32} className="text-brand-600" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Διαχείριση Email
            </h3>
            <p className="text-gray-500 max-w-md mx-auto mb-6">
              Εδώ θα μπορείτε να διαχειρίζεστε τα email σας και να ρυθμίζετε αυτοματοποιήσεις
              για υπενθυμίσεις υποχρεώσεων. Η λειτουργία αυτή βρίσκεται υπό ανάπτυξη.
            </p>
            <Button>
              <Plus size={18} className="mr-2" />
              Δημιουργία email
            </Button>
          </div>
        </div>
      </Card>

      {/* Email Templates Section */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Πρότυπα Email</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="border border-gray-200 rounded-lg p-4 hover:border-brand-300 transition-colors cursor-pointer">
            <h4 className="font-medium text-gray-900 mb-1">Υπενθύμιση ΦΠΑ</h4>
            <p className="text-sm text-gray-500">Μηνιαία υπενθύμιση για υποβολή ΦΠΑ</p>
          </div>
          <div className="border border-gray-200 rounded-lg p-4 hover:border-brand-300 transition-colors cursor-pointer">
            <h4 className="font-medium text-gray-900 mb-1">Υπενθύμιση ΑΠΔ</h4>
            <p className="text-sm text-gray-500">Μηνιαία υπενθύμιση για υποβολή ΑΠΔ</p>
          </div>
          <div className="border border-gray-200 rounded-lg p-4 hover:border-brand-300 transition-colors cursor-pointer">
            <h4 className="font-medium text-gray-900 mb-1">Νέο έγγραφο</h4>
            <p className="text-sm text-gray-500">Ειδοποίηση για νέο έγγραφο</p>
          </div>
        </div>
      </Card>

      {/* Automation Settings */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Αυτοματοποιήσεις</h3>
        <div className="space-y-4">
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
            <div>
              <p className="font-medium text-gray-900">Μηνιαίες υπενθυμίσεις</p>
              <p className="text-sm text-gray-500">Αυτόματη αποστολή υπενθυμίσεων για υποχρεώσεις</p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" className="sr-only peer" />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-brand-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-brand-600"></div>
            </label>
          </div>
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
            <div>
              <p className="font-medium text-gray-900">Ειδοποίηση νέων εγγράφων</p>
              <p className="text-sm text-gray-500">Email όταν προστίθεται νέο έγγραφο</p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" className="sr-only peer" defaultChecked />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-brand-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-brand-600"></div>
            </label>
          </div>
        </div>
      </Card>
    </div>
  );
}
