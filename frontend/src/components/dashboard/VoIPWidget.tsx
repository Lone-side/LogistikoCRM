import { Link } from 'react-router-dom';
import { Phone, PhoneIncoming, PhoneOutgoing, PhoneMissed, Ticket, ArrowRight, RefreshCw } from 'lucide-react';
import { useCalls } from '../../hooks/useVoIP';
import { useTickets } from '../../hooks/useTickets';
import { useEffect, useState, useRef } from 'react';
import { useToast } from '../../hooks/useToast';

/**
 * VoIP Dashboard Widget
 * Shows today's call statistics and open tickets with auto-refresh
 */
export default function VoIPWidget() {
  const [lastRefresh, setLastRefresh] = useState(new Date());
  const { addToast } = useToast();
  const previousTicketIds = useRef<Set<number>>(new Set());

  // Get today's date in YYYY-MM-DD format
  const today = new Date().toISOString().split('T')[0];

  // Fetch today's calls
  const {
    data: callsData,
    isLoading: callsLoading,
    refetch: refetchCalls
  } = useCalls({
    date_from: today,
    date_to: today,
    page_size: 100
  });

  // Fetch open tickets
  const {
    data: ticketsData,
    isLoading: ticketsLoading,
    refetch: refetchTickets
  } = useTickets({
    open_only: true,
    page_size: 5
  });

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      refetchCalls();
      refetchTickets();
      setLastRefresh(new Date());
    }, 30000);

    return () => clearInterval(interval);
  }, [refetchCalls, refetchTickets]);

  // Detect new missed call tickets and show toast
  useEffect(() => {
    if (!ticketsData?.results) return;

    const currentTicketIds = new Set(ticketsData.results.map(t => t.id));

    // Find new tickets (tickets that weren't in the previous set)
    const newTickets = ticketsData.results.filter(
      t => !previousTicketIds.current.has(t.id) && t.call
    );

    // Only show toast if we've already loaded data once (not initial load)
    if (previousTicketIds.current.size > 0 && newTickets.length > 0) {
      newTickets.forEach(ticket => {
        addToast({
          type: 'missed-call',
          title: 'Νέο Ticket από αναπάντητη κλήση',
          message: ticket.call?.phone_number
            ? `${ticket.call.phone_number}${ticket.client ? ` - ${ticket.client.eponimia}` : ''}`
            : ticket.title,
          duration: 8000,
        });
      });
    }

    // Update the reference
    previousTicketIds.current = currentTicketIds;
  }, [ticketsData?.results, addToast]);

  // Calculate stats from today's calls
  const stats = callsData?.stats || {
    total: 0,
    incoming: 0,
    outgoing: 0,
    missed: 0,
    today: 0
  };

  const openTicketsCount = ticketsData?.stats?.open || 0;
  const inProgressCount = ticketsData?.stats?.in_progress || 0;
  const recentTickets = ticketsData?.results?.slice(0, 3) || [];

  const isLoading = callsLoading || ticketsLoading;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Phone className="w-5 h-5 text-blue-600" />
          <h3 className="text-lg font-semibold text-gray-900">Τηλεφωνία</h3>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">
            {lastRefresh.toLocaleTimeString('el-GR', { hour: '2-digit', minute: '2-digit' })}
          </span>
          {isLoading && (
            <RefreshCw className="w-4 h-4 text-gray-400 animate-spin" />
          )}
        </div>
      </div>

      {/* Today's Calls Stats */}
      <div className="grid grid-cols-4 gap-3 mb-4">
        <div className="text-center p-2 bg-gray-50 rounded-lg">
          <div className="flex items-center justify-center mb-1">
            <Phone className="w-4 h-4 text-gray-600" />
          </div>
          <div className="text-xl font-bold text-gray-900">{stats.today}</div>
          <div className="text-xs text-gray-500">Σήμερα</div>
        </div>

        <div className="text-center p-2 bg-green-50 rounded-lg">
          <div className="flex items-center justify-center mb-1">
            <PhoneIncoming className="w-4 h-4 text-green-600" />
          </div>
          <div className="text-xl font-bold text-green-600">{stats.incoming}</div>
          <div className="text-xs text-gray-500">Εισερχ.</div>
        </div>

        <div className="text-center p-2 bg-blue-50 rounded-lg">
          <div className="flex items-center justify-center mb-1">
            <PhoneOutgoing className="w-4 h-4 text-blue-600" />
          </div>
          <div className="text-xl font-bold text-blue-600">{stats.outgoing}</div>
          <div className="text-xs text-gray-500">Εξερχ.</div>
        </div>

        <div className="text-center p-2 bg-red-50 rounded-lg">
          <div className="flex items-center justify-center mb-1">
            <PhoneMissed className="w-4 h-4 text-red-600" />
          </div>
          <div className="text-xl font-bold text-red-600">{stats.missed}</div>
          <div className="text-xs text-gray-500">Αναπάντ.</div>
        </div>
      </div>

      {/* Divider */}
      <div className="border-t border-gray-100 my-4" />

      {/* Open Tickets Section */}
      <div className="mb-3">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Ticket className="w-4 h-4 text-orange-500" />
            <span className="text-sm font-medium text-gray-700">Ανοιχτά Tickets</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 bg-orange-100 text-orange-700 text-xs font-medium rounded-full">
              {openTicketsCount + inProgressCount}
            </span>
          </div>
        </div>

        {/* Recent Tickets List */}
        {recentTickets.length > 0 ? (
          <div className="space-y-2">
            {recentTickets.map((ticket) => (
              <div
                key={ticket.id}
                className="flex items-center justify-between p-2 bg-gray-50 rounded-lg text-sm"
              >
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-gray-900 truncate">
                    {ticket.title}
                  </div>
                  {ticket.client && (
                    <div className="text-xs text-gray-500 truncate">
                      {ticket.client.eponimia}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2 ml-2">
                  <span className={`px-1.5 py-0.5 text-xs rounded ${
                    ticket.priority === 'urgent' ? 'bg-red-100 text-red-700' :
                    ticket.priority === 'high' ? 'bg-orange-100 text-orange-700' :
                    'bg-gray-100 text-gray-600'
                  }`}>
                    {ticket.priority === 'urgent' ? 'Επείγον' :
                     ticket.priority === 'high' ? 'Υψηλή' :
                     ticket.priority === 'medium' ? 'Μεσαία' : 'Χαμηλή'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-3 text-sm text-gray-500">
            Δεν υπάρχουν ανοιχτά tickets
          </div>
        )}
      </div>

      {/* Quick Links */}
      <div className="flex gap-2 mt-4">
        <Link
          to="/calls"
          className="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-blue-50 text-blue-600 text-sm font-medium rounded-lg hover:bg-blue-100 transition-colors"
        >
          Κλήσεις
          <ArrowRight className="w-4 h-4" />
        </Link>
        <Link
          to="/tickets"
          className="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-orange-50 text-orange-600 text-sm font-medium rounded-lg hover:bg-orange-100 transition-colors"
        >
          Tickets
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  );
}
