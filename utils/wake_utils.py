# utils/wake_utils.py

from colorama import Back, Fore, Style
import time

try:
    import RPi.GPIO as GPIO
    IS_PI = True
except ImportError:
    IS_PI = False
    prfx = Back.BLACK + Fore.GREEN + time.strftime("%H:%M:%S", time.gmtime()) + Back.RESET + Fore.WHITE + Style.BRIGHT
    print(prfx + Fore.YELLOW + " ⚠ RPi.GPIO nicht gefunden – GPIO wird deaktiviert (du bist nicht auf einem Raspberry Pi)." + Fore.WHITE)

import time


def _log(message: str):
    """Helper for consistent timestamped logging."""
    prfx = Back.BLACK + Fore.GREEN + time.strftime("%H:%M:%S", time.gmtime()) + Back.RESET + Fore.WHITE + Style.BRIGHT
    print(prfx + " " + Fore.YELLOW + message + Fore.WHITE)


def power_on_server():
    """Simuliert oder aktiviert den Power-Pin auf einem Raspberry Pi."""

    if not IS_PI:
        _log(" ⚠ GPIO-Funktion übersprungen (nicht auf Raspberry Pi).")
        return "GPIO nicht verfügbar – Testmodus aktiv."

    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(18, GPIO.OUT)

        # Power-Pin 1 Sekunde triggern
        GPIO.output(18, GPIO.HIGH)
        time.sleep(1)
        GPIO.output(18, GPIO.LOW)

        GPIO.cleanup()

        _log(" ✅ Server wurde über GPIO eingeschaltet.")
        return "Server wurde über GPIO eingeschaltet."

    except Exception as e:
        _log(f"❌ GPIO Fehler: {e}")
        return f"GPIO Fehler: {e}"


def is_server_online():
    """Pinge den Server."""
    import subprocess

    try:
        result = subprocess.run(
            ["ping", "-c", "1", "192.168.188.150"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        online = result.returncode == 0
        _log(f"Server online: {online}")
        return online

    except Exception as e:
        _log(f"❌ Fehler beim Prüfen des Servers: {e}")
        return False
