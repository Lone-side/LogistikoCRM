import { useState } from 'react';
import { DoorOpen, Loader2, WifiOff, Check } from 'lucide-react';
import { usePulseDoor, useDoorStatus } from '../hooks/useDoor';

export default function DoorButton() {
  const { data: status, isLoading: isCheckingStatus } = useDoorStatus();
  const pulseDoor = usePulseDoor();
  const [showSuccess, setShowSuccess] = useState(false);

  const handleClick = async () => {
    try {
      // Use pulse mode for electric door locks (momentary on/off)
      await pulseDoor.mutateAsync(undefined);
      setShowSuccess(true);
      setTimeout(() => setShowSuccess(false), 2000);
    } catch {
      // Error is handled by the mutation
    }
  };

  const isOffline = status && !status.online;
  const isLoading = pulseDoor.isPending || isCheckingStatus;

  // Determine button state and styling
  let buttonStyle = 'bg-brand-600 hover:bg-brand-700 text-white';
  let icon = <DoorOpen size={18} />;
  let label = 'Πόρτα';

  if (isOffline) {
    buttonStyle = 'bg-gray-400 text-white cursor-not-allowed';
    icon = <WifiOff size={18} />;
    label = 'Offline';
  } else if (showSuccess) {
    buttonStyle = 'bg-green-500 text-white';
    icon = <Check size={18} />;
    label = 'Άνοιξε!';
  } else if (isLoading) {
    buttonStyle = 'bg-blue-500 text-white opacity-70 cursor-wait';
    icon = <Loader2 size={18} className="animate-spin" />;
    label = '...';
  } else if (pulseDoor.isError) {
    buttonStyle = 'bg-red-500 hover:bg-red-600 text-white';
  }

  return (
    <button
      onClick={handleClick}
      disabled={isLoading || isOffline}
      className={`
        flex items-center gap-2 px-3 py-2 rounded-lg font-medium text-sm
        transition-all duration-200
        ${buttonStyle}
        ${isLoading || isOffline ? '' : 'active:scale-95'}
      `}
      title={isOffline ? 'Η συσκευή είναι offline' : 'Άνοιγμα πόρτας'}
    >
      {icon}
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}
