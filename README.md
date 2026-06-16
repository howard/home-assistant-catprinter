# Cat Printer for Home Assistant

Home Assistant integration for cheap
BLE thermal "cat printers" based on [rbaron/catprinter](https://github.com/rbaron/catprinter).

The printer is auto-discovered and can be used for printing images or text via notification service.

## Install

Add this repo to HACS and install it.

## Setup

Once discovered, the printer shows up in the Devices & Services section of the Home Assistant settings.

### Service fields

| Field       | Service                          | Default           | Notes |
| ----------- | -------------------------------- | ----------------- | ----- |
| `image`     | `print_image`                    | —                 | http(s) URL or allow-listed local path. |
| `dither`    | `print_image`                    | `floyd-steinberg` | `floyd-steinberg`, `mean-threshold`, or `none` (`none` needs a 384px-wide image). |
| `message`   | `print_text` / `send_message`    | —                 | Wrapped to the 384px paper width. |
| `font_size` | `print_text`                     | `24`              | Pixels (8–120). |
| `energy`    | both                             | `65535`           | Darkness, `0` (lightest) – `65535` (darkest). |

## Credits & license

- Printer protocol and original driver: [rbaron/catprinter](https://github.com/rbaron/catprinter) (MIT).
- This integration is MIT-licensed; see [LICENSE](LICENSE).

