import unittest

import time_machine

import server.util as util


class TestLagMonitor(unittest.TestCase):
    def setUp(self):
        self.traveler = time_machine.travel(0)
        self.timer = self.traveler.start()

    def test_latency_history(self):
        lag_monitor = util.LatencyMonitor(bucket_size_s=60)
        lag_monitor.accumulate_latency(5)
        self.assertEqual(lag_monitor.bucket_latencies(), [])
        self.timer.shift(59)
        lag_monitor.accumulate_latency(5)
        self.assertEqual(lag_monitor.bucket_latencies(), [])
        self.timer.shift(2)
        lag_monitor.accumulate_latency(5)
        self.assertEqual(lag_monitor.bucket_latencies(), [10])
        self.timer.shift(60)
        lag_monitor.accumulate_latency(1)
        self.assertEqual(lag_monitor.bucket_latencies(), [10, 5])

    def test_bucket_timestamps(self):
        lag_monitor = util.LatencyMonitor(bucket_size_s=60)
        self.assertEqual(lag_monitor.bucket_timestamps(), [])
        self.timer.shift(30)
        lag_monitor.accumulate_latency(5)
        self.assertEqual(lag_monitor.bucket_timestamps(), [])
        self.timer.shift(30)
        lag_monitor.accumulate_latency(5)
        self.assertEqual(lag_monitor.bucket_timestamps(), [0])
        self.timer.shift(30)
        lag_monitor.accumulate_latency(5)
        self.timer.shift(30)
        # Accumulate latency to force previous bucket to be created.
        lag_monitor.accumulate_latency(1)
        # We need to compare timestamps approximately.
        timestamps = lag_monitor.bucket_timestamps()
        expected_timestamps = [0, 60]
        for i in range(len(timestamps)):
            self.assertAlmostEqual(timestamps[i], expected_timestamps[i], places=3)
        self.timer.shift(60)
        lag_monitor.accumulate_latency(1)
        expected_timestamps_2 = [0, 60, 120]
        for i in range(len(timestamps)):
            self.assertAlmostEqual(timestamps[i], expected_timestamps_2[i], places=3)
