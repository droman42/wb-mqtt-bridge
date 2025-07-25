#!/usr/bin/env python3
import argparse
import base64
import time
from typing import List, Any, Optional

import broadlink
from broadlink.const import DEFAULT_PORT
from broadlink.exceptions import ReadError, StorageError
from broadlink.remote import data_to_pulses, pulses_to_data

TIMEOUT = 30


def auto_int(x):
    return int(x, 0)


def format_pulses(pulses: List[int]) -> str:
    """Format pulses."""
    return " ".join(
        f"+{pulse}" if i % 2 == 0 else f"-{pulse}"
        for i, pulse in enumerate(pulses)
    )


def parse_pulses(data: List[str]) -> List[int]:
    """Parse pulses."""
    return [abs(int(s)) for s in data]


def main() -> None:
    """Main entry point for broadlink CLI."""
    parser = argparse.ArgumentParser(fromfile_prefix_chars='@')
    parser.add_argument("--device", help="device definition as 'type host mac'")
    parser.add_argument("--type", type=auto_int, default=0x2712, help="type of device")
    parser.add_argument("--host", help="host address")
    parser.add_argument("--mac", help="mac address (hex reverse), as used by python-broadlink library")
    parser.add_argument("--temperature", action="store_true", help="request temperature from device")
    parser.add_argument("--humidity", action="store_true", help="request humidity from device")
    parser.add_argument("--energy", action="store_true", help="request energy consumption from device")
    parser.add_argument("--check", action="store_true", help="check current power state")
    parser.add_argument("--checknl", action="store_true", help="check current nightlight state")
    parser.add_argument("--turnon", action="store_true", help="turn on device")
    parser.add_argument("--turnoff", action="store_true", help="turn off device")
    parser.add_argument("--turnnlon", action="store_true", help="turn on nightlight on the device")
    parser.add_argument("--turnnloff", action="store_true", help="turn off nightlight on the device")
    parser.add_argument("--switch", action="store_true", help="switch state from on to off and off to on")
    parser.add_argument("--send", action="store_true", help="send command")
    parser.add_argument("--sensors", action="store_true", help="check all sensors")
    parser.add_argument("--learn", action="store_true", help="learn command")
    parser.add_argument("--rflearn", action="store_true", help="rf scan learning")
    parser.add_argument("--frequency", type=float, help="specify radiofrequency for learning")
    parser.add_argument("--learnfile", help="save learned command to a specified file")
    parser.add_argument("--durations", action="store_true",
                        help="use durations in micro seconds instead of the Broadlink format")
    parser.add_argument("--convert", action="store_true", help="convert input data to durations")
    parser.add_argument("--joinwifi", nargs=2, help="Args are SSID PASSPHRASE to configure Broadlink device with")
    parser.add_argument("data", nargs='*', help="Data to send or convert")
    args = parser.parse_args()

    # Define dev as None initially
    dev: Optional[Any] = None

    if args.device:
        values = args.device.split()
        devtype = int(values[0], 0)
        host = values[1]
        mac = bytearray.fromhex(values[2])
    elif args.mac:
        devtype = args.type
        host = args.host
        mac = bytearray.fromhex(args.mac)

    if args.host or args.device:
        dev = broadlink.gendevice(devtype, (host, DEFAULT_PORT), mac)
        dev.auth()

    if args.joinwifi:
        broadlink.setup(args.joinwifi[0], args.joinwifi[1], 4)

    if args.convert:
        data = bytearray.fromhex(''.join(args.data))
        pulses = data_to_pulses(data)
        print(format_pulses(pulses))

    # Only proceed with device operations if dev is initialized
    if dev is not None:
        if args.temperature:
            if hasattr(dev, "check_temperature"):
                print(dev.check_temperature())
            else:
                print("Device does not support temperature checking")
        if args.humidity:
            if hasattr(dev, "check_humidity"):
                print(dev.check_humidity())
            else:
                print("Device does not support humidity checking")
        if args.energy:
            if hasattr(dev, "get_energy"):
                print(dev.get_energy())
            else:
                print("Device does not support energy consumption checking")
        if args.sensors:
            if hasattr(dev, "check_sensors"):
                data = dev.check_sensors()
                for key in data:
                    print("{} {}".format(key, data[key]))
            else:
                print("Device does not support sensor checking")
        if args.send:
            data = (
                pulses_to_data(parse_pulses(args.data))
                if args.durations
                else bytes.fromhex(''.join(args.data))
            )
            if hasattr(dev, "send_data"):
                dev.send_data(data)
            else:
                print("Device does not support sending data")
        if args.learn or (args.learnfile and not args.rflearn):
            if not hasattr(dev, "enter_learning") or not hasattr(dev, "check_data"):
                print("Device does not support learning mode")
            else:
                dev.enter_learning()
                print("Learning...")
                start = time.time()
                while time.time() - start < TIMEOUT:
                    time.sleep(1)
                    try:
                        data = dev.check_data()
                    except (ReadError, StorageError):
                        continue
                    else:
                        break
                else:
                    print("No data received...")
                    exit(1)

                print("Packet found!")
                raw_fmt = data.hex()
                base64_fmt = base64.b64encode(data).decode('ascii')
                pulse_fmt = format_pulses(data_to_pulses(data))

                print("Raw:", raw_fmt)
                print("Base64:", base64_fmt)
                print("Pulses:", pulse_fmt)

                if args.learnfile:
                    print("Saving to {}".format(args.learnfile))
                    with open(args.learnfile, "w") as text_file:
                        text_file.write(pulse_fmt if args.durations else raw_fmt)
        if args.check:
            if hasattr(dev, "check_power"):
                if dev.check_power():
                    print('* ON *')
                else:
                    print('* OFF *')
            else:
                print("Device does not support power checking")
        if args.checknl:
            if hasattr(dev, "check_nightlight"):
                if dev.check_nightlight():
                    print('* ON *')
                else:
                    print('* OFF *')
            else:
                print("Device does not support nightlight checking")
        if args.turnon:
            if hasattr(dev, "set_power") and hasattr(dev, "check_power"):
                dev.set_power(True)
                if dev.check_power():
                    print('== Turned * ON * ==')
                else:
                    print('!! Still OFF !!')
            else:
                print("Device does not support power control")
        if args.turnoff:
            if hasattr(dev, "set_power") and hasattr(dev, "check_power"):
                dev.set_power(False)
                if dev.check_power():
                    print('!! Still ON !!')
                else:
                    print('== Turned * OFF * ==')
            else:
                print("Device does not support power control")
        if args.turnnlon:
            if hasattr(dev, "set_nightlight") and hasattr(dev, "check_nightlight"):
                dev.set_nightlight(True)
                if dev.check_nightlight():
                    print('== Turned * ON * ==')
                else:
                    print('!! Still OFF !!')
            else:
                print("Device does not support nightlight control")
        if args.turnnloff:
            if hasattr(dev, "set_nightlight") and hasattr(dev, "check_nightlight"):
                dev.set_nightlight(False)
                if dev.check_nightlight():
                    print('!! Still ON !!')
                else:
                    print('== Turned * OFF * ==')
            else:
                print("Device does not support nightlight control")
        if args.switch:
            if hasattr(dev, "check_power") and hasattr(dev, "set_power"):
                if dev.check_power():
                    dev.set_power(False)
                    print('* Switch to OFF *')
                else:
                    dev.set_power(True)
                    print('* Switch to ON *')
            else:
                print("Device does not support power control")
        if args.rflearn:
            if not hasattr(dev, "sweep_frequency") or not hasattr(dev, "check_frequency") or not hasattr(dev, "find_rf_packet") or not hasattr(dev, "check_data"):
                print("Device does not support RF learning")
            else:
                if args.frequency:
                    frequency = args.frequency
                    print("Press the button you want to learn, a short press...")
                else:
                    dev.sweep_frequency()
                    print("Detecting radiofrequency, press and hold the button to learn...")

                    start = time.time()
                    while time.time() - start < TIMEOUT:
                        time.sleep(1)
                        locked, frequency = dev.check_frequency()
                        if locked:
                            break
                    else:
                        print("Radiofrequency not found")
                        dev.cancel_sweep_frequency()
                        exit(1)

                    print("Radiofrequency detected: {}MHz".format(frequency))
                    print("You can now let go of the button")

                    input("Press enter to continue...")

                    print("Press the button again, now a short press.")

                dev.find_rf_packet(frequency)

                start = time.time()
                while time.time() - start < TIMEOUT:
                    time.sleep(1)
                    try:
                        data = dev.check_data()
                    except (ReadError, StorageError):
                        continue
                    else:
                        break
                else:
                    print("No data received...")
                    exit(1)

                print("Packet found!")
                raw_fmt = data.hex()
                base64_fmt = base64.b64encode(data).decode('ascii')
                pulse_fmt = format_pulses(data_to_pulses(data))

                print("Raw:", raw_fmt)
                print("Base64:", base64_fmt)
                print("Pulses:", pulse_fmt)

                if args.learnfile:
                    print("Saving to {}".format(args.learnfile))
                    with open(args.learnfile, "w") as text_file:
                        text_file.write(pulse_fmt if args.durations else raw_fmt)


if __name__ == "__main__":
    main()
