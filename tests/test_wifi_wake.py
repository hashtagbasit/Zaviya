"""steamos-arm-wifi-wake's fast scan against a fake iw and nmcli: it has to probe
the SSID's real bytes, not the \\xNN text that "iw dev wlan0 link" prints.
    python3 -m unittest tests.test_wifi_wake
"""
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "steamos-overlay/usr/lib/steamos-arm/steamos-arm-wifi-wake")


def iw_escaped(raw: bytes) -> str:
    """The SSID as iw's print_ssid_escaped() writes it (iw dev wlan0 link)."""
    out = []
    for i, b in enumerate(raw):
        if 0x20 < b < 0x7f and b != 0x5c:
            out.append(chr(b))
        elif b == 0x20 and 0 < i < len(raw) - 1:
            out.append(" ")
        else:
            out.append("\\x%02x" % b)
    return "".join(out)


@unittest.skipUnless(shutil.which("bash"), "needs bash")
class FastScan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.t = self.tmp.name
        self.bin = os.path.join(self.t, "bin")
        os.makedirs(self.bin)
        self.args = os.path.join(self.t, "iw-args")
        # iw records its arguments NUL-separated; nmcli says wlan0 is connected.
        self.tool("iw", f'printf "%s\\0" "$@" >>"{self.args}"\n')
        self.tool("nmcli", 'echo "100 (connected)"\n')
        with open(SCRIPT, encoding="utf-8") as fh:
            body = fh.read()
        body = body.replace("/run/konkr/", self.t + "/")
        self.script = os.path.join(self.t, "steamos-arm-wifi-wake")
        with open(self.script, "w", encoding="utf-8") as fh:
            fh.write(body)

    def tearDown(self):
        self.tmp.cleanup()

    def tool(self, name, body):
        path = os.path.join(self.bin, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\n" + body)
        os.chmod(path, 0o755)

    def scan(self, last: str):
        with open(os.path.join(self.t, "wifi-last"), "w", encoding="utf-8") as fh:
            fh.write(last)
        open(os.path.join(self.t, "wifi-was-connected"), "w").close()
        env = dict(os.environ, PATH=f"{self.bin}:/usr/bin:/bin", LC_ALL="C.UTF-8")
        r = subprocess.run(["bash", self.script, "watch"], env=env, capture_output=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.args, "rb") as fh:
            return fh.read().split(b"\0")[:-1]

    def test_probes_the_raw_ssid(self):
        for raw in ("Home \U0001F40C".encode(), b"Caf\xc3\xa9", b" lead and trail ",
                    b'say "hi" it\'s', b"back\\slash\\x41", b"tab\there", b"line\nbreak",
                    b"plain", b"\xff\xfe not utf-8"):
            with self.subTest(raw=raw):
                if os.path.exists(self.args):
                    os.remove(self.args)
                args = self.scan(f"6375\n{iw_escaped(raw)}\n")
                self.assertEqual(args, [b"dev", b"wlan0", b"scan", b"trigger", b"freq", b"6375",
                                        b"ssid", raw])

    def test_nul_in_ssid_probes_the_channel(self):
        args = self.scan(f"5180\n{iw_escaped(b'a' + bytes(1) + b'b')}\n")
        self.assertEqual(args, [b"dev", b"wlan0", b"scan", b"trigger", b"freq", b"5180"])

    def test_no_scan_without_a_network(self):
        open(self.args, "w").close()
        self.assertEqual(self.scan("garbage\n\n"), [])
        with open(self.args, "rb") as fh:
            self.assertEqual(fh.read(), b"", "iw was called")


if __name__ == "__main__":
    unittest.main()
