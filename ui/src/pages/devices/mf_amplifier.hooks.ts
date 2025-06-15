import { useState, useEffect } from 'react';
import { WirenboardIRStateState, defaultWirenboardIRStateState } from '../../types/generated/WirenboardIRState.state';
import { useDeviceState } from '../../hooks/useDeviceState';

export function useWirenboardIRState(deviceId: string = 'mf_amplifier') {
  const [state, setState] = useState<WirenboardIRStateState>(defaultWirenboardIRStateState);
  const { subscribeToState, updateState } = useDeviceState(deviceId);

  useEffect(() => {
    const subscription = subscribeToState((newState: Partial<WirenboardIRStateState>) => {
      setState(prevState => ({ ...prevState, ...newState }));
    });

    return subscription.unsubscribe;
  }, [deviceId, subscribeToState]);

  const updateField = <K extends keyof WirenboardIRStateState>(
    field: K, 
    value: WirenboardIRStateState[K]
  ) => {
    setState(prevState => ({ ...prevState, [field]: value }));
    updateState({ [field]: value });
  };

  return {
    state,
    updateField,
    setState: (newState: Partial<WirenboardIRStateState>) => {
      setState(prevState => ({ ...prevState, ...newState }));
      updateState(newState);
    }
  };
}