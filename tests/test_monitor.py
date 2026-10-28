import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import requests

from predoc_tracker.monitor import run_monitor
from predoc_tracker.notify import Alert, send_receipt, send_telegram
from predoc_tracker.match import MatchResult
from predoc_tracker.parse import parse_opportunities
from predoc_tracker.settings import AppConfig, NotificationConfig
from test_parser import SAMPLE_HTML


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.state = Path(self.directory.name) / 'state.json'
        self.receipt = Path(self.directory.name) / 'receipt.json'
        self.config = AppConfig(notifications=NotificationConfig(channels=['telegram']))
        self.record = parse_opportunities(SAMPLE_HTML)[0]
        self.environment = patch.dict(os.environ, {
            'PREDOC_TELEGRAM_BOT_TOKEN': 'test-token', 'PREDOC_TELEGRAM_CHAT_ID': 'test-chat',
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)

    @patch('predoc_tracker.monitor.fetch_page')
    @patch('predoc_tracker.monitor.parse_opportunities')
    @patch('predoc_tracker.monitor.send_telegram')
    def test_partial_failure_retries_only_unsent_then_sends_updates(self, send, parse, fetch):
        fetch.return_value = SimpleNamespace(html='fixture')
        other = replace(self.record, opportunity_id='other')
        parse.return_value = [self.record, other]
        send.side_effect = [None, RuntimeError('delivery failed')]
        self.receipt.write_text('{}')
        with self.assertRaises(RuntimeError):
            run_monitor(self.config, self.state, receipt_path=self.receipt)
        self.assertFalse(self.receipt.exists())
        self.assertEqual(json.loads(self.state.read_text()), {
            self.record.opportunity_id: self.record.content_hash,
        })
        send.reset_mock(side_effect=True)
        run_monitor(self.config, self.state)
        self.assertEqual(send.call_count, 1)
        send.reset_mock()
        run_monitor(self.config, self.state)
        send.assert_not_called()
        parse.return_value = [replace(self.record, content_hash='changed')]
        run_monitor(self.config, self.state)
        self.assertEqual(send.call_args.args[0][0].event_type, 'updated')
        self.assertNotIn('other', json.loads(self.state.read_text()))

    @patch('predoc_tracker.monitor.fetch_page')
    def test_empty_parse_preserves_state(self, fetch):
        self.state.write_text('{"existing": "hash"}')
        fetch.return_value = SimpleNamespace(html='<html></html>')
        with self.assertRaisesRegex(RuntimeError, 'No listings parsed'):
            run_monitor(self.config, self.state)
        self.assertEqual(json.loads(self.state.read_text()), {'existing': 'hash'})

    @patch('predoc_tracker.monitor.send_telegram')
    @patch('predoc_tracker.monitor.fetch_page')
    def test_preview_does_not_send_or_create_state(self, fetch, send):
        fetch.return_value = SimpleNamespace(html=SAMPLE_HTML)
        run_monitor(self.config, self.state, notify=False, receipt_path=self.receipt)
        send.assert_not_called()
        self.assertFalse(self.state.exists())
        self.assertFalse(self.receipt.exists())

    @patch('predoc_tracker.monitor.send_telegram')
    @patch('predoc_tracker.monitor.fetch_page')
    def test_receipt_summary_counts_alerts_then_records_zero_on_repeat(self, fetch, send):
        fetch.return_value = SimpleNamespace(html=SAMPLE_HTML)
        run_monitor(self.config, self.state, receipt_path=self.receipt)
        summary = json.loads(self.receipt.read_text())
        self.assertEqual(summary['observed_count'], 1)
        self.assertEqual(summary['alert_count'], 1)
        self.assertIn('completed_at', summary)
        self.assertEqual(summary['version'], '0.0.2')
        send.reset_mock()
        run_monitor(self.config, self.state, receipt_path=self.receipt)
        self.assertEqual(json.loads(self.receipt.read_text())['alert_count'], 0)
        send.assert_not_called()

    @patch('predoc_tracker.monitor.save_state', side_effect=OSError('disk full'))
    @patch('predoc_tracker.monitor.fetch_page')
    def test_state_save_failure_does_not_leave_success_receipt(self, fetch, save):
        fetch.return_value = SimpleNamespace(html=SAMPLE_HTML)
        self.state.write_text(json.dumps({self.record.opportunity_id: self.record.content_hash}))
        self.receipt.write_text('{}')
        with self.assertRaises(OSError):
            run_monitor(self.config, self.state, receipt_path=self.receipt)
        self.assertFalse(self.receipt.exists())


class TelegramTests(unittest.TestCase):
    @patch('predoc_tracker.notify.send_telegram_message')
    def test_receipt_reports_zero_alerts_and_bogota_time(self, send):
        send_receipt({
            'observed_count': 159, 'alert_count': 0,
            'completed_at': '2026-10-27T13:00:00+00:00', 'version': '0.0.2',
        }, bot_token_env='TEST_TOKEN', chat_id_env='TEST_CHAT')
        text = send.call_args.args[0]
        self.assertIn('Checked: 159 postings', text)
        self.assertIn('New or updated alerts sent: 0', text)
        self.assertIn('2026-10-27 08:00 (Bogotá)', text)
        self.assertIn('App version: 0.0.2', text)

    @patch('predoc_tracker.notify.time.sleep')
    @patch('predoc_tracker.notify.requests.post')
    def test_rate_limit_retries_and_paces(self, post, sleep):
        post.side_effect = [
            SimpleNamespace(status_code=429, json=lambda: {'parameters': {'retry_after': 5}}),
            SimpleNamespace(status_code=200, json=lambda: {'ok': True}),
        ]
        alert = Alert('new', 'Job', '', '', '', '', MatchResult(True, 1, []))
        with patch.dict(os.environ, {'TEST_TOKEN': 'secret', 'TEST_CHAT': 'chat'}):
            send_telegram([alert], bot_token_env='TEST_TOKEN', chat_id_env='TEST_CHAT')
        self.assertEqual(post.call_count, 2)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [6, 3.2])

    @patch('predoc_tracker.notify.requests.post')
    def test_connection_error_does_not_expose_token(self, post):
        post.side_effect = requests.ConnectionError('URL includes secret')
        alert = Alert('new', 'Job', '', '', '', '', MatchResult(True, 1, []))
        with patch.dict(os.environ, {'TEST_TOKEN': 'secret', 'TEST_CHAT': 'chat'}):
            with self.assertRaises(RuntimeError) as raised:
                send_telegram([alert], bot_token_env='TEST_TOKEN', chat_id_env='TEST_CHAT')
        self.assertNotIn('secret', str(raised.exception))
