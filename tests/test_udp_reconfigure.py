"""Regressions for a UDP destination left enabled across a restore reboot."""
import unittest
from unittest import mock

from shelly_ota import logwatch


class UdpReconfigureTests(unittest.TestCase):
    def exercise(self, previous, fail_enable=False):
        changes = []
        def rpc_call(addr, method, params=None, **auth):
            if method == 'Sys.GetConfig':
                return {'debug': {'udp': {'addr': previous}}}
            destination = params['config']['debug']['udp']['addr']
            changes.append(destination)
            if fail_enable and len(changes) == 2:
                raise RuntimeError('enable failed')
            return {}
        with mock.patch.object(logwatch.rpc, 'call', side_effect=rpc_call), \
             mock.patch.object(logwatch.socket, 'socket'), \
             mock.patch.object(logwatch.threading, 'Thread'):
            try:
                with logwatch.udp_log('device.invalid', '127.0.0.1', 9514, lambda line: None):
                    if previous == '127.0.0.1:9514':
                        self.assertEqual(changes[:2], [None, previous],
                                         'An unchanged destination does not emit the startup slot line')
            except RuntimeError:
                if not fail_enable:
                    raise
        return changes

    def test_same_destination_is_reinitialized_and_restored(self):
        self.assertEqual(self.exercise('127.0.0.1:9514'),
                         [None, '127.0.0.1:9514', '127.0.0.1:9514'])

    def test_different_destination_does_not_need_disable(self):
        self.assertEqual(self.exercise('127.0.0.2:9514'),
                         ['127.0.0.1:9514', '127.0.0.2:9514'])

    def test_previously_disabled_log_stays_disabled_afterwards(self):
        self.assertEqual(self.exercise(None), ['127.0.0.1:9514', None])

    def test_previous_destination_restored_if_reenable_fails(self):
        self.assertEqual(self.exercise('127.0.0.1:9514', fail_enable=True),
                         [None, '127.0.0.1:9514', '127.0.0.1:9514'])
