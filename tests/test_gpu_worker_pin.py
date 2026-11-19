"""Tests for konkrd's placement of msm's gpu-worker thread on SM8550. Run:
    python3 -m unittest tests.test_gpu_worker_pin
"""
import importlib.machinery
import importlib.util
import io
import os
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
loader = importlib.machinery.SourceFileLoader("konkrd", os.path.join(ROOT, "sm8650-overlay/usr/lib/konkr/konkrd"))
spec = importlib.util.spec_from_loader("konkrd", loader)
k = importlib.util.module_from_spec(spec)
loader.exec_module(k)

# SM8550: three A510s, four middle cores, one X3.
CAPS = {0: 222, 1: 222, 2: 222, 3: 657, 4: 657, 5: 657, 6: 657, 7: 1024}
FREQS = {0: 2016000, 1: 2016000, 2: 2016000, 3: 2803200, 4: 2803200, 5: 2803200, 6: 2803200, 7: 3187200}
KTHREAD = 0x00208040  # PF_KTHREAD | PF_NOFREEZE | PF_FORKNOEXEC, as msm's kthread worker has
USER = 0x00400100     # PF_RANDOMIZE | PF_SUPERPRIV: an ordinary process


def stat(pid, comm, flags):
    return b"%d (%s) S 2 0 0 0 -1 %d 0 0 0 0 0 0 0 0 -51 0 1 0 220 0 0" % (pid, comm, flags)


class GpuWorkerPin(unittest.TestCase):
    def setUp(self):
        self.files = {f"/sys/devices/system/cpu/cpu{c}/cpu_capacity": str(v) for c, v in CAPS.items()}
        self.files.update({f"/sys/devices/system/cpu/cpu{c}/cpufreq/cpuinfo_max_freq": str(v)
                           for c, v in FREQS.items()})
        self.stats = {"/proc/1/stat": stat(1, b"systemd", USER),
                      "/proc/151/stat": stat(151, b"gpu-worker", KTHREAD),
                      "/proc/152/stat": stat(152, b"kworker/0:1H", KTHREAD)}
        self.cpus = list(CAPS)
        self.aff = {151: set(range(8))}
        self.set_calls = []

    def drop(self, cpu, attr):
        del self.files[f"/sys/devices/system/cpu/cpu{cpu}/{attr}"]

    def glob(self, pattern):
        if pattern.startswith("/sys/devices/system/cpu/"):
            return [f"/sys/devices/system/cpu/cpu{c}" for c in self.cpus]
        return list(self.stats)

    def setaffinity(self, pid, mask):
        self.set_calls.append((pid, set(mask)))
        self.aff[pid] = set(mask)

    def open_stat(self, path, mode="r", *a, **kw):
        if path not in self.stats:
            raise FileNotFoundError(path)
        return io.BytesIO(self.stats[path])

    def run_pin(self, sm8550=True):
        with mock.patch.object(k, "is_sm8550", return_value=sm8550), \
                mock.patch.object(k, "rd", side_effect=lambda p, d="": self.files.get(p, d)), \
                mock.patch.object(k, "open", side_effect=self.open_stat, create=True), \
                mock.patch.object(k.glob, "glob", side_effect=self.glob), \
                mock.patch.object(k.os, "sched_getaffinity", side_effect=lambda pid: set(self.aff[pid])), \
                mock.patch.object(k.os, "sched_setaffinity", side_effect=self.setaffinity), \
                mock.patch.object(k, "log"):
            k.pin_gpu_worker()

    def test_moves_to_the_middle_cores(self):
        self.run_pin()
        self.assertEqual(self.set_calls, [(151, {3, 4, 5, 6})])

    def test_leaves_a_placed_thread_alone(self):
        self.aff[151] = {3, 4, 5, 6}
        self.run_pin()
        self.assertEqual(self.set_calls, [])

    def test_other_socs_untouched(self):
        self.run_pin(sm8550=False)
        self.assertEqual(self.set_calls, [])

    def test_one_big_cluster_keeps_all_of_it(self):
        self.files["/sys/devices/system/cpu/cpu7/cpu_capacity"] = str(CAPS[3])
        self.run_pin()
        self.assertEqual(self.set_calls, [(151, {3, 4, 5, 6, 7})])

    def test_no_cpus_no_write(self):
        self.cpus = []
        self.run_pin()
        self.assertEqual(self.set_calls, [])

    def test_one_tier_no_write(self):
        for c in CAPS:
            self.files[f"/sys/devices/system/cpu/cpu{c}/cpu_capacity"] = "1024"
        self.aff[151] = {0}
        self.run_pin()
        self.assertEqual(self.set_calls, [])

    def test_no_thread_no_write(self):
        del self.stats["/proc/151/stat"]
        self.run_pin()
        self.assertEqual(self.set_calls, [])

    def test_user_process_with_the_name_left_alone(self):
        self.stats["/proc/151/stat"] = stat(151, b"gpu-worker", USER)
        self.run_pin()
        self.assertEqual(self.set_calls, [])

    def test_non_utf8_name_does_not_stop_the_pass(self):
        self.stats = {"/proc/90/stat": stat(90, b"\xff\xfe bad", USER), **self.stats}
        self.run_pin()
        self.assertEqual(self.set_calls, [(151, {3, 4, 5, 6})])

    def test_unreadable_capacity_ranks_all_by_frequency(self):
        self.drop(7, "cpu_capacity")
        self.run_pin()
        self.assertEqual(self.set_calls, [(151, {3, 4, 5, 6})])

    def test_unreadable_little_capacity_stays_off_the_wifi_cores(self):
        # A per-CPU fallback would rank CPU0 by kHz against the others'
        # capacities, put it in the big set and the mask on {0,3,4,5,6}.
        self.drop(0, "cpu_capacity")
        self.run_pin()
        self.assertEqual(self.set_calls, [(151, {3, 4, 5, 6})])

    def test_unreadable_middle_capacity_ranks_all_by_frequency(self):
        self.drop(3, "cpu_capacity")
        self.run_pin()
        self.assertEqual(self.set_calls, [(151, {3, 4, 5, 6})])

    def test_no_ranking_no_write(self):
        self.drop(7, "cpu_capacity")
        self.drop(7, "cpufreq/cpuinfo_max_freq")
        self.run_pin()
        self.assertEqual(self.set_calls, [])

    def test_no_ranking_for_a_little_core_no_write(self):
        self.drop(0, "cpu_capacity")
        self.drop(1, "cpufreq/cpuinfo_max_freq")
        self.run_pin()
        self.assertEqual(self.set_calls, [])


if __name__ == "__main__":
    unittest.main()
