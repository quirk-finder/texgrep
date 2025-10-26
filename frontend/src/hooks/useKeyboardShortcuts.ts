import { useEffect } from 'react';

interface ShortcutHandlers {
  focusSearch: () => void;
  toggleRegex: () => void;
  selectNext: () => void;
  selectPrev: () => void;
  regexEnabled?: boolean;
}

export function useKeyboardShortcuts({ focusSearch, toggleRegex, selectNext, selectPrev, regexEnabled = true }: ShortcutHandlers) {
  useEffect(() => {
    function handle(event: KeyboardEvent) {
      if (event.defaultPrevented) return;
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        focusSearch();
      }
      if (event.altKey && event.key.toLowerCase() === 'r') {
        event.preventDefault();
        if (regexEnabled) {
          toggleRegex();
        }
      }
      if (!event.ctrlKey && !event.metaKey && !event.altKey) {
        if (event.key.toLowerCase() === 'j') {
          event.preventDefault();
          selectNext();
        }
        if (event.key.toLowerCase() === 'k') {
          event.preventDefault();
          selectPrev();
        }
      }
    }

    window.addEventListener('keydown', handle);
    return () => window.removeEventListener('keydown', handle);
  }, [focusSearch, toggleRegex, selectNext, selectPrev, regexEnabled]);
}
