"""Fresh Windows endpoint identity, independent of PortAudio's cached list."""


def endpoint_snapshot():
    import comtypes
    from pycaw.pycaw import AudioUtilities
    comtypes.CoInitialize()
    try:
        enumerator = AudioUtilities.GetDeviceEnumerator()
        result = {}
        for label, direction in (("system", 0), ("microphone", 1)):
            try:
                device = AudioUtilities.CreateDevice(enumerator.GetDefaultAudioEndpoint(direction, 1))
                result[label] = (device.id, device.FriendlyName)
            except Exception:
                result[label] = None
        devices = AudioUtilities.GetAllDevices(device_state=1)
        result["active"] = tuple(sorted((device.id, device.FriendlyName) for device in devices))
        return result
    finally:
        comtypes.CoUninitialize()
