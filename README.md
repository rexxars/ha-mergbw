# MeRGBW for Home Assistant

[![Tests](https://github.com/rexxars/ha-mergbw/actions/workflows/tests.yml/badge.svg)](https://github.com/rexxars/ha-mergbw/actions/workflows/tests.yml)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Home Assistant custom component for MeRGBW Bluetooth LED lights. Control your MeRGBW wall panels, LED strips, bulbs, and ceiling lights directly from Home Assistant.

## Supported Devices

This integration _theoretically_ supports a wide range of MeRGBW Bluetooth LED devices, including:

- Hexagon Lights / Letters Lights (Type 1)
- RGB Line/Strip (Type 2)
- Star Lights (Type 3)
- Handle Lights (Type 4)
- Sunset Lights (Type 5)
- Bulb (Type 6)
- Ceiling Lights Colorful (Type 7)
- Ceiling Lights RGB (Type 8)

However, I only have access to the Hexagon Lights, so those are the only ones actually tested in real life.

## Features

- Automatic device discovery via Bluetooth
- Power on/off control
- RGB color control
- Brightness control
- State restoration after Home Assistant restart

## Requirements

- Home Assistant 2024.1.0 or newer
- Bluetooth adapter supported by Home Assistant
- MeRGBW Bluetooth LED device

## Installation

### HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rexxars&repository=ha-mergbw&category=Integration)

### HACS (Manual)

1. Open HACS in Home Assistant
2. Click the three dots in the top right corner
3. Select "Custom repositories"
4. Add `https://github.com/rexxars/ha-mergbw` with category "Integration"
5. Click "Add"
6. Search for "MeRGBW" and install it
7. Restart Home Assistant

### Manual Installation

1. Download the latest release from GitHub
2. Copy the `custom_components/mergbw` folder to your Home Assistant `custom_components` directory
3. Restart Home Assistant

## Configuration

Once installed, MeRGBW devices should be automatically discovered if they are powered on and within Bluetooth range.

1. Go to **Settings** > **Devices & Services**
2. Look for discovered MeRGBW devices, or click **Add Integration** and search for "MeRGBW"
3. Follow the setup wizard

### Device Binding (Types 1 & 4 only)

Letters Lights and Handle Lights require a one-time binding process:
1. When prompted during setup, press and hold any button on the device for 3 seconds
2. The device will confirm binding and complete setup

## Troubleshooting

### Device not discovered

- Ensure the device is powered on (plugged in)
- Check that your Bluetooth adapter is working in Home Assistant
- Move the device closer to your Home Assistant server
- Try power cycling the device

### Connection issues

- MeRGBW devices only support one active connection at a time
- Close the official MeRGBW app if it's connected to the device
- Check Home Assistant logs for detailed error messages

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

MIT © [Espen Hovlandsdal](https://espen.codes/)

## Disclaimer

This is an unofficial integration and is not affiliated with MeRGBW or their manufacturers. Use at your own risk.
